import os
import subprocess


def kill_process(pid: int) -> str:
    """Force-terminate a process and its child processes by PID."""
    if pid <= 4:
        raise ValueError("PID must be greater than 4")
    if pid == os.getpid():
        raise ValueError("The agent cannot terminate its own process")

    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(detail or f"taskkill failed with exit code {result.returncode}")
    return f"Terminated process {pid} and its child processes"
