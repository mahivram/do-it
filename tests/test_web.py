import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from automation.web import (
    AgentJobs,
    AgentRequestHandler,
    LoopbackAgentServer,
    _python_source_snapshot,
    _serve_with_reload,
    _loopback_origin,
    validate_request,
)


class WebRequestValidationTests(unittest.TestCase):
    def test_accepts_provider_settings_and_trims_prompt(self):
        prompt, settings = validate_request(
            {
                "prompt": "  Open Notepad  ",
                "provider": "freellm",
                "config": {
                    "apiKey": " local-key ",
                    "baseUrl": "http://127.0.0.1:31415/v1",
                },
            }
        )

        self.assertEqual(prompt, "Open Notepad")
        self.assertEqual(settings["api_key"], "local-key")
        self.assertEqual(settings["provider"], "freellm")

    def test_allows_empty_browser_key_for_backend_environment_configuration(self):
        _, settings = validate_request(
            {
                "prompt": "List windows",
                "provider": "openrouter",
                "config": {
                    "apiKey": "",
                    "model": "model-from-env",
                    "baseUrl": "https://router.example/v1",
                },
            }
        )
        self.assertEqual(settings["api_key"], "")

    def test_rejects_empty_oversized_and_unsupported_requests(self):
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            validate_request({"prompt": " ", "provider": "gemini", "config": {}})
        with self.assertRaisesRegex(ValueError, "characters or fewer"):
            validate_request(
                {
                    "prompt": "x" * 20_001,
                    "provider": "gemini",
                    "config": {},
                }
            )
        with self.assertRaisesRegex(ValueError, "supported provider"):
            validate_request({"prompt": "hello", "provider": "unknown", "config": {}})
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            validate_request(
                {
                    "prompt": "hello",
                    "provider": "gemini",
                    "config": {"apiKey": "", "baseUrl": "https://invalid.example"},
                }
            )

    def test_rejects_non_loopback_http_provider_urls(self):
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            validate_request(
                {
                    "prompt": "hello",
                    "provider": "openrouter",
                    "config": {
                        "apiKey": "",
                        "model": "test",
                        "baseUrl": "http://router.example/v1",
                    },
                }
            )

    def test_allows_only_explicit_loopback_origins(self):
        self.assertTrue(_loopback_origin("http://127.0.0.1:5173", 8000))
        self.assertTrue(_loopback_origin("http://localhost:8000", 8000))
        self.assertFalse(_loopback_origin("https://attacker.example", 8000))
        self.assertFalse(_loopback_origin("http://localhost", 8000))
        self.assertFalse(_loopback_origin("null", 8000))


class PythonHotReloadTests(unittest.TestCase):
    def test_source_snapshot_tracks_project_python_files_but_skips_generated_dirs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "automation").mkdir()
            (root / "automation" / "agent.py").write_text("value = 1", encoding="utf-8")
            (root / "frontend").mkdir()
            (root / "frontend" / "config.py").write_text("ignored = True", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_agent.py").write_text("ignored = True", encoding="utf-8")
            (root / "web.py").write_text("value = 2", encoding="utf-8")

            before = _python_source_snapshot(root)
            (root / "automation" / "agent.py").write_text("value = 10", encoding="utf-8")

            after = _python_source_snapshot(root)

        self.assertEqual({item[0] for item in before}, {"automation/agent.py", "web.py"})
        self.assertNotEqual(before, after)

    def test_reload_supervisor_restarts_child_when_source_changes(self):
        class FakeProcess:
            def __init__(self):
                self.running = True
                self.terminated = False
                self.waited = False

            def poll(self):
                return None if self.running else 0

            def terminate(self):
                self.terminated = True
                self.running = False

            def wait(self):
                self.waited = True
                return 0

        initial = (("web.py", 1, 10),)
        changed = (("web.py", 2, 10),)
        first_process = FakeProcess()
        second_process = FakeProcess()
        with (
            patch("automation.web._python_source_snapshot", return_value=initial),
            patch(
                "automation.web._wait_for_python_source_change",
                side_effect=[changed, KeyboardInterrupt],
            ),
            patch(
                "automation.web.subprocess.Popen",
                side_effect=[first_process, second_process],
            ) as start_process,
        ):
            _serve_with_reload("127.0.0.1", 8000)

        self.assertEqual(start_process.call_count, 2)
        command = start_process.call_args_list[0].args[0]
        self.assertEqual(command[0], sys.executable)
        self.assertEqual(
            command[1:],
            [
                str(Path(__file__).resolve().parents[1] / "web.py"),
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
        )
        self.assertEqual(
            start_process.call_args_list[0].kwargs["cwd"],
            Path(__file__).resolve().parents[1],
        )
        self.assertTrue(first_process.terminated)
        self.assertTrue(first_process.waited)
        self.assertTrue(second_process.terminated)
        self.assertTrue(second_process.waited)


class AgentJobTests(unittest.TestCase):
    def wait_for_status(self, jobs, job_id, expected_status):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            job = jobs.get(job_id)
            if job["status"] == expected_status:
                return job
            time.sleep(0.01)
        self.fail(f"Agent job did not reach {expected_status}")

    @patch("automation.web.run_agent_request")
    def test_runs_agent_and_exposes_tool_progress_without_provider_secrets(
        self, run_agent
    ):
        def complete(_prompt, provider_config, confirmation_handler, on_tool_event):
            on_tool_event({"name": "get_active_windows", "status": "running"})
            on_tool_event({"name": "get_active_windows", "status": "completed"})
            self.assertEqual(provider_config["api_key"], "private-key")
            return {"response": "There are no open windows.", "tools": []}

        run_agent.side_effect = complete
        jobs = AgentJobs()
        job_id = jobs.create(
            "List windows",
            {"provider": "gemini", "api_key": "private-key", "model": "test"},
        )
        job = self.wait_for_status(jobs, job_id, "completed")

        self.assertEqual(job["response"], "There are no open windows.")
        self.assertEqual(
            job["tools"],
            [{"name": "get_active_windows", "status": "completed"}],
        )
        self.assertNotIn("private-key", json.dumps(job))

    @patch("automation.web.run_agent_request")
    def test_waits_for_explicit_confirmation_and_resumes_agent(self, run_agent):
        def request_approval(
            _prompt, provider_config, confirmation_handler, on_tool_event
        ):
            approved = confirmation_handler("Restart Windows")
            return {"response": f"Approved: {approved}", "tools": []}

        run_agent.side_effect = request_approval
        jobs = AgentJobs()
        job_id = jobs.create("Restart my PC", {"provider": "gemini"})
        pending = self.wait_for_status(jobs, job_id, "waiting_confirmation")
        confirmation_id = pending["confirmation"]["id"]

        self.assertTrue(
            jobs.confirm(job_id, confirmation_id, approved=False)
        )
        completed = self.wait_for_status(jobs, job_id, "completed")
        self.assertEqual(completed["response"], "Approved: False")
        self.assertFalse(jobs.confirm(job_id, confirmation_id, approved=True))


class LocalHttpApiTests(unittest.TestCase):
    def setUp(self):
        self.server = LoopbackAgentServer(("127.0.0.1", 0), AgentRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=3
        )

    def tearDown(self):
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def test_health_endpoint_only_accepts_local_origins(self):
        self.connection.request(
            "GET",
            "/api/health",
            headers={"Origin": f"http://127.0.0.1:{self.server.server_port}"},
        )
        response = self.connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"status": "ok"})

        self.connection.request(
            "GET",
            "/api/health",
            headers={"Origin": "https://attacker.example"},
        )
        response = self.connection.getresponse()
        self.assertEqual(response.status, 403)

    @patch("automation.web.JOBS.create", return_value="job-123")
    def test_job_endpoint_validates_and_queues_prompt(self, create_job):
        body = json.dumps(
            {
                "prompt": "Open Notepad",
                "provider": "gemini",
                "config": {"apiKey": "test-key", "model": "test-model"},
            }
        )
        self.connection.request(
            "POST",
            "/api/jobs",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.server.server_port}",
            },
        )
        response = self.connection.getresponse()
        payload = json.loads(response.read())

        self.assertEqual(response.status, 202)
        self.assertEqual(payload, {"id": "job-123", "status": "queued"})
        create_job.assert_called_once_with(
            "Open Notepad",
            {"provider": "gemini", "api_key": "test-key", "model": "test-model"},
        )

    @patch("automation.web.JOBS.confirm", return_value=True)
    def test_confirmation_endpoint_forwards_explicit_decision(self, confirm):
        self.connection.request(
            "POST",
            "/api/jobs/job-123/confirmation",
            body=json.dumps({"confirmationId": "approval-456", "approved": False}),
            headers={
                "Content-Type": "application/json",
                "Origin": f"http://127.0.0.1:{self.server.server_port}",
            },
        )
        response = self.connection.getresponse()

        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(response.read()), {"status": "decision_received"})
        confirm.assert_called_once_with("job-123", "approval-456", False)

    def test_serves_built_frontend_and_spa_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dist = Path(temp_dir) / "dist"
            dist.mkdir()
            (dist / "index.html").write_text("<main>local agent</main>", encoding="utf-8")
            with patch("automation.web.FRONTEND_DIST", dist):
                for path in ("/", "/settings"):
                    self.connection.request("GET", path)
                    response = self.connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b"<main>local agent</main>")


if __name__ == "__main__":
    unittest.main()
