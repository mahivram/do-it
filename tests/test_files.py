import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.files import manage_files


class ManageFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project_root = patch("automation.files.PROJECT_ROOT", self.root)
        self.project_root.start()
        self.addCleanup(self.project_root.stop)
        self.addCleanup(self.temp.cleanup)

    def test_create_directory_list_create_read_and_write_file(self):
        self.assertEqual(manage_files("create_folder", "nested"), "Created folder: nested")
        self.assertEqual(
            manage_files("create_file", "nested/note.txt", content="hello"),
            "Created file: nested/note.txt",
        )
        self.assertEqual(manage_files("read", "nested/note.txt"), "hello")
        self.assertEqual(
            manage_files("write_file", "nested/note.txt", content="updated"),
            "Wrote file: nested/note.txt",
        )
        self.assertEqual(manage_files("read", "nested/note.txt"), "updated")
        self.assertEqual(
            manage_files("list", "nested"),
            [{"name": "note.txt", "type": "file"}],
        )

    def test_create_file_does_not_overwrite(self):
        manage_files("create_file", "note.txt", content="original")
        error = manage_files("create_file", "note.txt", content="new")
        self.assertIn("error", error)
        self.assertEqual((self.root / "note.txt").read_text(), "original")

    def test_create_folder_does_not_overwrite_existing_folder(self):
        (self.root / "folder").mkdir()
        self.assertIn("error", manage_files("create_folder", "folder"))

    def test_rename_file_and_folder_and_reject_existing_destination(self):
        manage_files("create_file", "old.txt", content="data")
        self.assertEqual(
            manage_files("rename", "old.txt", destination="new.txt"),
            "Renamed old.txt to new.txt",
        )
        self.assertTrue((self.root / "new.txt").is_file())
        manage_files("create_file", "occupied.txt")
        self.assertIn(
            "error",
            manage_files("rename", "new.txt", destination="occupied.txt"),
        )

    def test_delete_file_and_folder_recursively(self):
        (self.root / "folder").mkdir()
        (self.root / "folder" / "nested.txt").write_text("data")
        self.assertEqual(manage_files("delete", "folder"), "Deleted: folder")
        self.assertFalse((self.root / "folder").exists())

    def test_rejects_paths_outside_project_and_parent_traversal(self):
        outside = self.root.parent / f"{self.root.name}-outside.txt"
        for path in ("../escape.txt", str(outside)):
            with self.subTest(path=path):
                self.assertIn("error", manage_files("create_file", path))
        self.assertFalse(outside.exists())

    def test_rejects_root_delete_or_rename(self):
        self.assertIn("error", manage_files("delete", "."))
        self.assertIn("error", manage_files("rename", ".", destination="renamed"))
        self.assertTrue(self.root.is_dir())

    def test_rejects_invalid_action_missing_path_and_invalid_target_types(self):
        self.assertIn("error", manage_files("invalid", "."))
        self.assertIn("error", manage_files("list", "missing"))
        self.assertIn("error", manage_files("read", "."))
        self.assertIn("error", manage_files("rename", "missing", destination="target"))

    def test_symlink_cannot_escape_project_when_platform_allows_symlinks(self):
        outside = self.root.parent
        link = self.root / "outside-link"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlink creation is unavailable: {exc}")
        self.assertIn("error", manage_files("list", "outside-link"))


if __name__ == "__main__":
    unittest.main()
