import os
import shutil
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ACTIONS = {
    "list",
    "read",
    "create_file",
    "write_file",
    "create_folder",
    "delete",
    "rename",
}


def _resolve_project_path(path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = Path(os.path.abspath(candidate))

    try:
        relative_path = candidate.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Path must be inside the project directory") from exc

    current = PROJECT_ROOT
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symbolic links are not allowed in managed paths")

    resolved = candidate.resolve()
    try:
        resolved.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise ValueError("Path must resolve inside the project directory") from exc
    return resolved


def manage_files(
    action: str,
    path: str,
    destination: str | None = None,
    content: str | None = None,
) -> dict[str, object] | str:
    """Manage project files and folders without accessing paths outside the project."""
    try:
        if action not in _ACTIONS:
            raise ValueError(f"Unsupported file action: {action}")

        target = _resolve_project_path(path)
        if action in {"delete", "rename"} and target == PROJECT_ROOT:
            raise ValueError("The project root cannot be deleted or renamed")

        if action == "list":
            if not target.is_dir():
                raise ValueError(f"Not a directory: {path}")
            return [
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                }
                for entry in sorted(target.iterdir(), key=lambda item: item.name.lower())
            ]

        if action == "read":
            if not target.is_file():
                raise ValueError(f"Not a file: {path}")
            return target.read_text(encoding="utf-8")

        if action == "create_file":
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("x", encoding="utf-8") as file:
                file.write(content or "")
            return f"Created file: {path}"

        if action == "write_file":
            if not target.parent.is_dir():
                raise ValueError(f"Parent directory does not exist: {target.parent}")
            target.write_text(content or "", encoding="utf-8")
            return f"Wrote file: {path}"

        if action == "create_folder":
            target.mkdir(parents=True, exist_ok=False)
            return f"Created folder: {path}"

        if action == "delete":
            if not target.exists():
                raise ValueError(f"Path does not exist: {path}")
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return f"Deleted: {path}"

        if destination is None:
            raise ValueError("The destination argument is required for rename")
        new_target = _resolve_project_path(destination)
        if new_target == PROJECT_ROOT:
            raise ValueError("The project root cannot be overwritten")
        if not target.exists():
            raise ValueError(f"Path does not exist: {path}")
        if new_target.exists():
            raise ValueError(f"Destination already exists: {destination}")
        if not new_target.parent.is_dir():
            raise ValueError(
                f"Destination parent directory does not exist: {new_target.parent}"
            )
        target.rename(new_target)
        return f"Renamed {path} to {destination}"
    except (OSError, UnicodeError, ValueError) as exc:
        return {"error": str(exc)}
