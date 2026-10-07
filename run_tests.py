"""Run all tool unit tests and print an explicit pass/fail summary."""

import unittest
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(project_root / "tests"),
        pattern="test_*.py",
        top_level_dir=str(project_root),
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)

    passed = result.testsRun - len(result.failures) - len(result.errors) - len(
        result.skipped
    )
    print(
        "\nTest summary: "
        f"{passed} passed, "
        f"{len(result.failures)} failed, "
        f"{len(result.errors)} errors, "
        f"{len(result.skipped)} skipped."
    )
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
