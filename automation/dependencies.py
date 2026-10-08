"""Check and confirmation-gated installation of this project's dependencies."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
PROJECT_DISTRIBUTIONS = ("openai", "pywin32", "pywinauto", "google-genai")


def check_project_dependencies() -> list[dict[str, Any]]:
    """Report whether each required project distribution is installed."""
    dependencies = []
    for name in PROJECT_DISTRIBUTIONS:
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            dependencies.append(
                {"name": name, "installed": False, "version": None}
            )
        else:
            dependencies.append(
                {"name": name, "installed": True, "version": version}
            )
    return dependencies


def manage_project_dependencies(action: str) -> dict[str, Any]:
    """Check dependencies or install requirements.txt after terminal confirmation."""
    if action == "check":
        dependencies = check_project_dependencies()
        return {
            "python": sys.executable,
            "dependencies": dependencies,
            "missing": [item["name"] for item in dependencies if not item["installed"]],
        }
    if action != "install":
        raise ValueError("Action must be 'check' or 'install'")

    if not REQUIREMENTS_FILE.is_file():
        raise FileNotFoundError(f"Project requirements file not found: {REQUIREMENTS_FILE}")

    try:
        answer = input(
            "Install this project's dependencies into the currently running "
            f"Python ({sys.executable}) from {REQUIREMENTS_FILE.name}? "
            "Type 'yes' to confirm: "
        )
    except EOFError:
        answer = ""
    if answer.strip().lower() != "yes":
        return {"status": "cancelled", "python": sys.executable}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS_FILE),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=900,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or f"pip exited with code {result.returncode}")

    dependencies = check_project_dependencies()
    missing = [item["name"] for item in dependencies if not item["installed"]]
    if missing:
        raise RuntimeError(
            "Installation completed but dependencies are still missing: "
            + ", ".join(missing)
        )
    return {
        "status": "installed",
        "python": sys.executable,
        "dependencies": dependencies,
    }
