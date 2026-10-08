import importlib.metadata
import subprocess
import sys
import unittest
from unittest.mock import patch

from automation.dependencies import (
    PROJECT_DISTRIBUTIONS,
    REQUIREMENTS_FILE,
    check_project_dependencies,
    manage_project_dependencies,
)


class DependencyCheckTests(unittest.TestCase):
    @patch("automation.dependencies.importlib.metadata.version")
    def test_check_reports_installed_and_missing_packages(self, version):
        def installed_version(name):
            if name == "pywin32":
                return "312"
            raise importlib.metadata.PackageNotFoundError(name)

        version.side_effect = installed_version
        result = check_project_dependencies()
        self.assertEqual(
            result,
            [
                {
                    "name": name,
                    "installed": name == "pywin32",
                    "version": "312" if name == "pywin32" else None,
                }
                for name in PROJECT_DISTRIBUTIONS
            ],
        )

    @patch("automation.dependencies.importlib.metadata.version")
    def test_check_includes_missing_gemini_sdk(self, version):
        def installed_version(name):
            if name == "google-genai":
                raise importlib.metadata.PackageNotFoundError(name)
            return "1"

        version.side_effect = installed_version
        result = check_project_dependencies()

        gemini_sdk = next(item for item in result if item["name"] == "google-genai")
        self.assertEqual(
            gemini_sdk,
            {"name": "google-genai", "installed": False, "version": None},
        )

    @patch("automation.dependencies.check_project_dependencies")
    def test_check_action_reports_python_and_missing_packages(self, check):
        check.return_value = [
            {"name": "pywinauto", "installed": False, "version": None},
            {"name": "openai", "installed": True, "version": "3.0"},
        ]
        result = manage_project_dependencies("check")
        self.assertEqual(result["missing"], ["pywinauto"])
        self.assertEqual(result["dependencies"], check.return_value)
        self.assertTrue(result["python"].lower().endswith(".exe"))

    def test_unknown_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "check.*install"):
            manage_project_dependencies("upgrade")


class DependencyInstallTests(unittest.TestCase):
    @patch("automation.dependencies.subprocess.run")
    @patch("automation.dependencies.input", return_value="no")
    def test_declining_install_does_not_run_pip(self, _input, run):
        result = manage_project_dependencies("install")
        self.assertEqual(result["status"], "cancelled")
        run.assert_not_called()

    @patch("automation.dependencies.subprocess.run")
    @patch("automation.dependencies.input", return_value="yes")
    @patch("automation.dependencies.check_project_dependencies")
    def test_install_uses_current_python_and_requirements_file(
        self, check, _input, run
    ):
        check.return_value = [
            {"name": name, "installed": True, "version": "1"}
            for name in PROJECT_DISTRIBUTIONS
        ]
        run.return_value = subprocess.CompletedProcess(
            args=["pip"], returncode=0, stdout="", stderr=""
        )
        result = manage_project_dependencies("install")
        self.assertEqual(result["status"], "installed")
        self.assertEqual(
            run.call_args.args[0],
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                str(REQUIREMENTS_FILE),
            ],
        )
        self.assertEqual(run.call_args.kwargs["timeout"], 900)
        check.assert_called_once()

    @patch("automation.dependencies.subprocess.run")
    @patch("automation.dependencies.input", side_effect=EOFError)
    def test_noninteractive_install_safely_cancels(self, _input, run):
        self.assertEqual(
            manage_project_dependencies("install")["status"],
            "cancelled",
        )
        run.assert_not_called()

    @patch("automation.dependencies.subprocess.run")
    @patch("automation.dependencies.input", return_value="yes")
    def test_pip_failure_is_reported(self, _input, run):
        run.return_value = subprocess.CompletedProcess(
            args=["pip"], returncode=1, stdout="", stderr="permission denied"
        )
        with self.assertRaisesRegex(RuntimeError, "permission denied"):
            manage_project_dependencies("install")

    @patch("automation.dependencies.subprocess.run")
    @patch("automation.dependencies.input", return_value="yes")
    @patch("automation.dependencies.check_project_dependencies")
    def test_reports_packages_still_missing_after_successful_pip(
        self, check, _input, run
    ):
        check.return_value = [
            {"name": name, "installed": name != "pywinauto", "version": None}
            for name in PROJECT_DISTRIBUTIONS
        ]
        run.return_value = subprocess.CompletedProcess(
            args=["pip"], returncode=0, stdout="", stderr=""
        )
        with self.assertRaisesRegex(RuntimeError, "pywinauto"):
            manage_project_dependencies("install")


if __name__ == "__main__":
    unittest.main()
