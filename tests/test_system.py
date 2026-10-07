import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from tests import win32_mocks
from automation import system
from automation.system import (
    create_system_restore_point,
    get_hardware_info,
    get_power_info,
    get_system_info,
    get_system_uptime,
    list_environment_variables,
    manage_power,
    manage_windows_features,
    manage_windows_updates,
)


class SystemInformationTests(unittest.TestCase):
    @patch("automation.system.platform.machine", return_value="AMD64")
    @patch("automation.system.platform.version", return_value="10.0.22631")
    @patch("automation.system.platform.release", return_value="11")
    @patch("automation.system.platform.system", return_value="Windows")
    def test_get_system_info(self, _system, _release, _version, _machine):
        self.assertEqual(
            get_system_info(),
            {
                "os": "Windows",
                "release": "11",
                "version": "10.0.22631",
                "architecture": "AMD64",
            },
        )

    def test_get_system_uptime_returns_boot_time_and_seconds(self):
        kernel32 = Mock()
        kernel32.GetTickCount64.return_value = 3_600_000
        with (
            patch.object(system.ctypes, "windll", Mock(kernel32=kernel32), create=True),
            patch(
                "automation.system.datetime",
                wraps=datetime,
            ),
        ):
            result = get_system_uptime()
        self.assertEqual(result["uptime_seconds"], 3600)
        boot_time = datetime.fromisoformat(result["boot_time_utc"])
        self.assertEqual(boot_time.tzinfo, timezone.utc)
        self.assertEqual(result["last_restart_utc"], result["boot_time_utc"])

    @patch(
        "automation.system._run_powershell_json",
        return_value={
            "cpu": {"Name": "CPU"},
            "memory_bytes": 123,
            "disks": [{"device": "C:"}],
            "gpus": [{"name": "GPU"}],
        },
    )
    def test_get_hardware_info_returns_cpu_memory_disk_and_gpu(self, run_script):
        result = get_hardware_info()
        self.assertEqual(result["memory_bytes"], 123)
        self.assertEqual(result["disks"][0]["device"], "C:")
        self.assertEqual(result["gpus"][0]["name"], "GPU")
        run_script.assert_called_once()

    def test_get_hardware_info_reports_malformed_powershell_result(self):
        with patch("automation.system._run_powershell_json", return_value=[]):
            with self.assertRaisesRegex(RuntimeError, "invalid hardware"):
                get_hardware_info()

    def test_environment_variables_redact_secret_marked_names(self):
        with patch.dict(
            os.environ,
            {
                "TEST_API_KEY": "secret-key",
                "TEST_PASSWORD": "secret-password",
                "TEST_TOKEN": "secret-token",
                "SSH_KEY": "private-key",
                "AWS_ACCESS_KEY_ID": "secret-access-key",
                "DATABASE_URL": "mysql://user:password@db",
                "TEST_PATH_VALUE": "safe-path",
            },
        ):
            result = list_environment_variables()
        self.assertEqual(result["TEST_API_KEY"], "<redacted>")
        self.assertEqual(result["TEST_PASSWORD"], "<redacted>")
        self.assertEqual(result["TEST_TOKEN"], "<redacted>")
        self.assertEqual(result["SSH_KEY"], "<redacted>")
        self.assertEqual(result["AWS_ACCESS_KEY_ID"], "<redacted>")
        self.assertEqual(result["DATABASE_URL"], "<redacted>")
        self.assertEqual(result["TEST_PATH_VALUE"], "safe-path")

    @patch("automation.system._run_powershell", side_effect=["[]", "Power plan output"])
    def test_get_power_info_returns_batteries_and_power_plans(self, _run_script):
        self.assertEqual(
            get_power_info(),
            {"batteries": [], "power_plans": ["Power plan output"]},
        )


class ConfirmedSystemActionsTests(unittest.TestCase):
    @patch("automation.system.subprocess.run")
    @patch("automation.system.input", return_value="no")
    def test_power_action_cancellation_does_not_execute(self, _input, run):
        self.assertEqual(manage_power("shutdown"), "Cancelled system shutdown")
        run.assert_not_called()

    @patch("automation.system.subprocess.run")
    @patch("automation.system.input", return_value="yes")
    def test_shutdown_requires_yes_and_runs_fixed_command(self, _input, run):
        run.return_value.returncode = 0
        self.assertEqual(manage_power("shutdown"), "Started system shutdown")
        run.assert_called_once_with(
            ["shutdown.exe", "/s", "/t", "0"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    @patch("automation.system.input", return_value="yes")
    @patch("automation.system._run_powershell")
    def test_sleep_requires_confirmation_and_uses_suspend_api(self, run, _input):
        self.assertEqual(manage_power("sleep"), "Started system sleep")
        self.assertIn("SetSuspendState", run.call_args.args[0])

    def test_power_action_rejects_unknown_action(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            manage_power("format")

    @patch("automation.system.input", return_value="yes")
    @patch("automation.system.subprocess.run")
    def test_restart_hibernate_and_lock_run_expected_commands(self, run, _input):
        run.return_value.returncode = 0
        expected_commands = {
            "restart": ["shutdown.exe", "/r", "/t", "0"],
            "hibernate": ["shutdown.exe", "/h"],
            "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
        }
        for action, command in expected_commands.items():
            with self.subTest(action=action):
                self.assertEqual(manage_power(action), f"Started system {action}")
                self.assertEqual(run.call_args.args[0], command)

    @patch("automation.system.input", side_effect=EOFError)
    @patch("automation.system.subprocess.run")
    def test_power_action_cancels_if_confirmation_input_is_unavailable(self, _run, _input):
        self.assertEqual(manage_power("restart"), "Cancelled system restart")
        _run.assert_not_called()

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="no")
    def test_restore_point_cancellation_does_not_call_powershell(self, _input, run):
        self.assertEqual(
            create_system_restore_point("Before changes"),
            "Cancelled system restore point creation",
        )
        run.assert_not_called()

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="yes")
    def test_restore_point_escapes_description_and_requires_confirmation(self, _input, run):
        self.assertEqual(
            create_system_restore_point("User's restore point"),
            "Created system restore point: User's restore point",
        )
        self.assertIn("'User''s restore point'", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 300)

    @patch("automation.system.input")
    def test_restore_point_rejects_empty_description_before_prompt(self, prompt):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            create_system_restore_point(" ")
        prompt.assert_not_called()

    @patch("automation.system._run_powershell", return_value="[]")
    def test_windows_update_list_is_read_only_and_parses_result(self, run):
        self.assertEqual(manage_windows_updates("list"), [])
        run.assert_called_once()
        self.assertIn("IsInstalled=0 and IsHidden=0", run.call_args.args[0])

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="no")
    def test_windows_update_cancellation_does_not_run_script(self, _input, run):
        result = manage_windows_updates("install", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        self.assertEqual(result, "Cancelled Windows Update install")
        run.assert_not_called()

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="yes")
    def test_windows_update_install_requires_valid_id_and_confirmation(self, _input, run):
        update_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        self.assertIn(update_id, manage_windows_updates("install", update_id))
        self.assertIn(update_id, run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 1800)

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="yes")
    def test_windows_update_hide_requires_confirmation_and_runs_hide_script(self, _input, run):
        update_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        result = manage_windows_updates("hide", update_id)
        self.assertIn("hide completed", result)
        self.assertIn("$update.IsHidden = $true", run.call_args.args[0])

    @patch("automation.system.input")
    def test_windows_update_rejects_invalid_id_before_confirmation(self, prompt):
        with self.assertRaisesRegex(ValueError, "valid update_id"):
            manage_windows_updates("hide", "not-a-guid")
        prompt.assert_not_called()

    @patch("automation.system._run_powershell_json", return_value=[{"FeatureName": "X"}])
    def test_windows_feature_list_is_read_only(self, run):
        self.assertEqual(manage_windows_features("list"), [{"FeatureName": "X"}])
        run.assert_called_once()

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="no")
    def test_windows_feature_cancellation_does_not_run_script(self, _input, run):
        self.assertEqual(
            manage_windows_features("enable", "Feature-X"),
            "Cancelled Windows feature enable",
        )
        run.assert_not_called()

    @patch("automation.system._run_powershell")
    @patch("automation.system.input", return_value="yes")
    def test_windows_feature_change_requires_confirmation_and_escapes_name(self, _input, run):
        result = manage_windows_features("disable", "Feature's Name")
        self.assertIn("Feature's Name", result)
        script = run.call_args.args[0]
        self.assertIn("Disable-WindowsOptionalFeature", script)
        self.assertIn("'Feature''s Name'", script)
        self.assertIn("-NoRestart", script)

    @patch("automation.system.input")
    def test_windows_feature_change_requires_name_before_confirmation(self, prompt):
        with self.assertRaisesRegex(ValueError, "feature_name is required"):
            manage_windows_features("enable")
        prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
