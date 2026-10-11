"""Loopback-only HTTP API and static frontend for the automation agent."""

import json
import logging
import mimetypes
import os
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from automation.agent import run_agent_request


LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
MAX_REQUEST_BYTES = 100_000
MAX_PROMPT_LENGTH = 20_000
MAX_JOBS = 50
CONFIRMATION_TIMEOUT_SECONDS = 120
USER_INPUT_TIMEOUT_SECONDS = 300
ALLOWED_PROVIDERS = {"openrouter", "freellm", "gemini"}
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
RELOAD_POLL_SECONDS = 0.5
RELOAD_IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "__pycache__",
    "frontend",
    "node_modules",
    "tests",
    "venv",
}


def _loopback_origin(value: str | None, server_port: int) -> bool:
    if value is None:
        return True
    try:
        origin = urlsplit(value)
        return (
            origin.scheme in {"http", "https"}
            and origin.hostname in LOOPBACK_HOSTS
            and origin.port in {server_port, 5173}
            and origin.username is None
            and origin.password is None
        )
    except ValueError:
        return False


def validate_request(data: Any) -> tuple[str, dict[str, str]]:
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    prompt = data.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Prompt must not be empty.")
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f"Prompt must be {MAX_PROMPT_LENGTH} characters or fewer.")

    provider = data.get("provider")
    config = data.get("config")
    if (
        not isinstance(provider, str)
        or provider not in ALLOWED_PROVIDERS
        or not isinstance(config, dict)
    ):
        raise ValueError("Choose a supported provider and provide its settings.")

    allowed_fields = (
        {"apiKey", "model", "baseUrl"}
        if provider in {"openrouter", "freellm"}
        else {"apiKey", "model"}
    )
    if set(config) - allowed_fields:
        raise ValueError("Provider settings contain unsupported fields.")
    values: dict[str, str] = {}
    field_limits = {"apiKey": 4096, "model": 256, "baseUrl": 2048}
    for field in allowed_fields:
        value = config.get(field, "")
        if not isinstance(value, str) or len(value) > field_limits[field]:
            raise ValueError(f"Invalid provider setting: {field}.")
        values[field] = value.strip()

    if provider in {"openrouter", "freellm"}:
        base_url = values.get("baseUrl", "")
        if base_url:
            try:
                parsed = urlsplit(base_url)
            except ValueError as exc:
                raise ValueError(
                    "API base URL must use HTTPS (or HTTP on this device)."
                ) from exc
            local_http = parsed.scheme == "http" and parsed.hostname in LOOPBACK_HOSTS
            if (
                parsed.scheme != "https"
                and not local_http
            ) or (
                not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("API base URL must use HTTPS (or HTTP on this device).")

    provider_settings = {
        "provider": provider,
        "api_key": values.get("apiKey", ""),
    }
    if "model" in values:
        provider_settings["model"] = values["model"]
    if "baseUrl" in values:
        provider_settings["base_url"] = values["baseUrl"]
    return prompt.strip(), provider_settings


@dataclass
class _AgentJob:
    id: str
    condition: threading.Condition
    created_at: float
    status: str = "queued"
    response: str | None = None
    error: str | None = None
    tools: list[dict[str, Any]] = field(default_factory=list)
    confirmation: dict[str, str] | None = None
    interaction: dict[str, Any] | None = None
    confirmation_result: bool | None = None
    interaction_result: str | None = None
    interaction_submitted: bool = False


class AgentJobs:
    """Run agent tasks serially and pause for direct browser confirmations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._agent_lock = threading.Lock()
        self._jobs: dict[str, _AgentJob] = {}

    def create(self, prompt: str, provider_config: dict[str, str]) -> str:
        job_id = uuid.uuid4().hex
        job = _AgentJob(
            id=job_id,
            condition=threading.Condition(self._lock),
            created_at=time.monotonic(),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._prune()
        thread = threading.Thread(
            target=self._run,
            args=(job_id, prompt, provider_config),
            name=f"agent-job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return job_id

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._public_job(job) if job is not None else None

    def confirm(self, job_id: str, confirmation_id: str, approved: bool) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if (
                job is None
                or job.confirmation is None
                or job.confirmation["id"] != confirmation_id
                or job.confirmation_result is not None
            ):
                return False
            job.confirmation_result = approved
            job.condition.notify_all()
            return True

    def submit_input(self, job_id: str, interaction_id: str, answer: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if (
                job is None
                or job.interaction is None
                or job.interaction["id"] != interaction_id
                or job.interaction_submitted
            ):
                return False
            job.interaction_result = answer
            job.interaction_submitted = True
            job.condition.notify_all()
            return True

    def _run(
        self, job_id: str, prompt: str, provider_config: dict[str, str]
    ) -> None:
        with self._agent_lock:
            with self._lock:
                job = self._jobs[job_id]
                job.status = "running"
            try:
                result = run_agent_request(
                    prompt,
                    provider_config=provider_config,
                    confirmation_handler=lambda description: self._request_confirmation(
                        job_id, description
                    ),
                    user_input_handler=lambda question, options: self._request_user_input(
                        job_id, question, options
                    ),
                    on_tool_event=lambda event: self._record_tool_event(job_id, event),
                )
            except Exception as exc:
                LOGGER.exception("Agent job failed")
                with self._lock:
                    job.status = "failed"
                    job.error = str(exc)
            else:
                with self._lock:
                    job.status = "completed"
                    job.response = result["response"]
            finally:
                with self._lock:
                    job.condition.notify_all()

    def _record_tool_event(self, job_id: str, event: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            tool_event: dict[str, Any] = {
                "id": event["id"],
                "name": event["name"],
                "status": event["status"],
            }
            if "result" in event:
                result = json.dumps(event["result"], ensure_ascii=False, default=str)
                tool_event["result"] = (
                    result
                    if len(result) <= 4000
                    else result[:4000] + "… (truncated)"
                )
            for index, existing in enumerate(job.tools):
                if existing["id"] == event["id"]:
                    job.tools[index] = tool_event
                    break
            else:
                job.tools.append(tool_event)

    def _request_confirmation(self, job_id: str, description: str) -> bool:
        with self._lock:
            job = self._jobs[job_id]
            confirmation_id = uuid.uuid4().hex
            job.confirmation = {
                "id": confirmation_id,
                "description": description,
            }
            job.confirmation_result = None
            job.status = "waiting_confirmation"
            deadline = time.monotonic() + CONFIRMATION_TIMEOUT_SECONDS
            while job.confirmation_result is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    job.confirmation_result = False
                    break
                job.condition.wait(remaining)

            approved = job.confirmation_result is True
            job.confirmation_result = None
            job.confirmation = None
            job.status = "running"
            return approved

    def _request_user_input(
        self, job_id: str, question: str, options: list[str] | None
    ) -> str | None:
        with self._lock:
            job = self._jobs[job_id]
            interaction_id = uuid.uuid4().hex
            job.interaction = {
                "id": interaction_id,
                "question": question,
                "options": options,
            }
            job.interaction_result = None
            job.interaction_submitted = False
            job.status = "waiting_input"
            deadline = time.monotonic() + USER_INPUT_TIMEOUT_SECONDS
            while not job.interaction_submitted:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                job.condition.wait(remaining)

            answer = job.interaction_result
            job.interaction_result = None
            job.interaction_submitted = False
            job.interaction = None
            job.status = "running"
            return answer

    def _public_job(self, job: _AgentJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "status": job.status,
            "response": job.response,
            "error": job.error,
            "tools": list(job.tools),
            "confirmation": job.confirmation,
            "interaction": job.interaction,
        }

    def _prune(self) -> None:
        completed = sorted(
            (
                (job_id, job)
                for job_id, job in self._jobs.items()
                if job.status in {"completed", "failed"}
            ),
            key=lambda item: item[1].created_at,
        )
        while len(self._jobs) > MAX_JOBS and completed:
            job_id, _ = completed.pop(0)
            self._jobs.pop(job_id, None)


JOBS = AgentJobs()


class AgentRequestHandler(BaseHTTPRequestHandler):
    server_version = "DoItAgent/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _authorized_local_request(self) -> bool:
        try:
            host = urlsplit(f"//{self.headers.get('Host', '')}")
            valid_host = (
                host.hostname in LOOPBACK_HOSTS
                and host.port == self.server.server_port
            )
        except ValueError:
            valid_host = False
        valid_origin = _loopback_origin(
            self.headers.get("Origin"), self.server.server_port
        )
        if valid_host and valid_origin:
            return True
        self._send_json(403, {"error": "Only local app requests are allowed."})
        return False

    def _send_json(self, status: int, value: dict[str, Any]) -> None:
        payload = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> Any:
        if self.headers.get_content_type() != "application/json":
            raise ValueError("Content-Type must be application/json.")
        length = self.headers.get("Content-Length")
        if length is None or not length.isdigit():
            raise ValueError("A valid Content-Length header is required.")
        size = int(length)
        if size > MAX_REQUEST_BYTES:
            raise ValueError("Request body is too large.")
        try:
            return json.loads(self.rfile.read(size))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must contain valid JSON.") from exc

    def do_GET(self) -> None:
        if not self._authorized_local_request():
            return
        if self.path == "/api/health":
            self._send_json(200, {"status": "ok"})
            return
        if self.path.startswith("/api/jobs/"):
            job_id = self.path.removeprefix("/api/jobs/")
            if not job_id or "/" in job_id:
                self._send_json(404, {"error": "Agent job not found."})
                return
            job = JOBS.get(job_id)
            if job is None:
                self._send_json(404, {"error": "Agent job not found."})
                return
            self._send_json(200, job)
            return

        self._serve_frontend()

    def do_POST(self) -> None:
        if not self._authorized_local_request():
            return
        try:
            data = self._read_json()
            if self.path == "/api/jobs":
                prompt, provider_config = validate_request(data)
                self._send_json(
                    202,
                    {"id": JOBS.create(prompt, provider_config), "status": "queued"},
                )
                return

            parts = self.path.strip("/").split("/")
            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "jobs"
                and parts[3] == "confirmation"
            ):
                confirmation_id = data.get("confirmationId") if isinstance(data, dict) else None
                approved = data.get("approved") if isinstance(data, dict) else None
                if not isinstance(confirmation_id, str) or not isinstance(approved, bool):
                    raise ValueError("A confirmation ID and approval decision are required.")
                if not JOBS.confirm(parts[2], confirmation_id, approved):
                    self._send_json(409, {"error": "This confirmation is no longer pending."})
                    return
                self._send_json(200, {"status": "decision_received"})
                return

            if (
                len(parts) == 4
                and parts[0] == "api"
                and parts[1] == "jobs"
                and parts[3] == "input"
            ):
                interaction_id = data.get("interactionId") if isinstance(data, dict) else None
                answer = data.get("answer") if isinstance(data, dict) else None
                if (
                    not isinstance(interaction_id, str)
                    or not isinstance(answer, str)
                    or not answer.strip()
                    or len(answer) > 2000
                ):
                    raise ValueError("A pending input ID and a non-empty answer are required.")
                if not JOBS.submit_input(parts[2], interaction_id, answer.strip()):
                    self._send_json(409, {"error": "This question is no longer pending."})
                    return
                self._send_json(200, {"status": "answer_received"})
                return

            self._send_json(404, {"error": "API route not found."})
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception:
            LOGGER.exception("Local agent API request failed")
            self._send_json(500, {"error": "The local agent request failed."})

    def _serve_frontend(self) -> None:
        requested_path = self.path.split("?", 1)[0]
        relative_path = "index.html" if requested_path == "/" else requested_path.lstrip("/")
        dist_root = FRONTEND_DIST.resolve()
        file_path = (dist_root / relative_path).resolve()
        try:
            file_path.relative_to(dist_root)
        except ValueError:
            self.send_error(404)
            return
        if not file_path.is_file():
            file_path = dist_root / "index.html"
        if not file_path.is_file():
            self.send_error(
                503,
                "Frontend build not found. Run npm run build in the frontend folder.",
            )
            return

        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


class LoopbackAgentServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _python_source_snapshot(
    project_root: Path = PROJECT_ROOT,
) -> tuple[tuple[str, int, int], ...]:
    """Return timestamps and sizes for runtime Python files in the project."""
    snapshot = []
    for current_root, directories, files in os.walk(project_root):
        directories[:] = [
            name
            for name in directories
            if name not in RELOAD_IGNORED_DIRECTORIES
        ]
        for name in files:
            if not name.endswith(".py"):
                continue
            source_path = Path(current_root) / name
            stat = source_path.stat()
            snapshot.append(
                (
                    source_path.relative_to(project_root).as_posix(),
                    stat.st_mtime_ns,
                    stat.st_size,
                )
            )
    return tuple(sorted(snapshot))


def _wait_for_python_source_change(
    snapshot: tuple[tuple[str, int, int], ...],
    process: subprocess.Popen[bytes] | None,
    project_root: Path = PROJECT_ROOT,
) -> tuple[tuple[str, int, int], ...]:
    while True:
        time.sleep(RELOAD_POLL_SECONDS)
        latest = _python_source_snapshot(project_root)
        if latest != snapshot:
            return latest
        if process is not None and process.poll() is not None:
            print("Python server stopped; waiting for a source change to restart it.")
            process = None


def _serve_with_reload(host: str, port: int) -> None:
    project_root = PROJECT_ROOT
    entry_point = project_root / "web.py"
    command = [
        sys.executable,
        str(entry_point),
        "--host",
        host,
        "--port",
        str(port),
    ]
    snapshot = _python_source_snapshot(project_root)
    print("Python hot reload enabled; watching project Python files.")

    while True:
        process = subprocess.Popen(command, cwd=project_root)
        try:
            snapshot = _wait_for_python_source_change(snapshot, process, project_root)
        except KeyboardInterrupt:
            if process.poll() is None:
                process.terminate()
                process.wait()
            print("\nStopping Do It agent UI.")
            return

        if process.poll() is None:
            process.terminate()
            process.wait()
        print("Python source changed; restarting the local agent server.")


def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    if host not in LOOPBACK_HOSTS:
        raise ValueError("The agent web server must bind to a loopback address.")
    if reload:
        _serve_with_reload(host, port)
        return

    server = LoopbackAgentServer((host, port), AgentRequestHandler)
    print(f"Do It agent UI: http://{host}:{server.server_port}")
    if not (FRONTEND_DIST / "index.html").is_file():
        print("Frontend build missing. In frontend/, run: npm install; npm run build")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Do It agent UI.")
    finally:
        server.server_close()
