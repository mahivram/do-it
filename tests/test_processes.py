import os
import subprocess
import unittest
from unittest.mock import patch

from automation.processes import kill_process


class KillProcessTests(unittest.TestCase):
    def test_kills_requested_process_tree(self):
        result = subprocess.CompletedProcess(
            args=["taskkill"], returncode=0, stdout="SUCCESS", stderr=""
        )
        with patch("automation.processes.subprocess.run", return_value=result) as run:
            self.assertEqual(
                kill_process(1234),
                "Terminated process 1234 and its child processes",
            )
        run.assert_called_once_with(
            ["taskkill", "/PID", "1234", "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

    def test_rejects_system_and_agent_pids_without_calling_taskkill(self):
        with patch("automation.processes.subprocess.run") as run:
            for pid in (0, 4):
                with self.subTest(pid=pid), self.assertRaisesRegex(ValueError, "greater"):
                    kill_process(pid)
            with self.assertRaisesRegex(ValueError, "cannot terminate"):
                kill_process(os.getpid())
        run.assert_not_called()

    def test_reports_taskkill_failure(self):
        failure = subprocess.CompletedProcess(
            args=["taskkill"], returncode=1, stdout="", stderr="Access denied"
        )
        with patch("automation.processes.subprocess.run", return_value=failure):
            with self.assertRaisesRegex(RuntimeError, "Access denied"):
                kill_process(1234)

    def test_reports_taskkill_timeout(self):
        with patch(
            "automation.processes.subprocess.run",
            side_effect=subprocess.TimeoutExpired("taskkill", 10),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                kill_process(1234)


if __name__ == "__main__":
    unittest.main()
