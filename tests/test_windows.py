import unittest
from unittest.mock import patch

from tests.win32_mocks import win32con, win32gui
from automation import windows


class WindowTests(unittest.TestCase):
    def setUp(self):
        win32gui.window_calls.clear()

    @patch("automation.windows.subprocess.Popen")
    def test_open_window_passes_application_and_arguments(self, popen):
        popen.return_value.pid = 4321
        result = windows.open_window("app.exe", ["--flag"])
        self.assertEqual(result, "Started app.exe with process ID 4321")
        popen.assert_called_once_with(["app.exe", "--flag"])

    def test_close_window_posts_close_to_valid_window(self):
        result = windows.close_window(123)
        self.assertEqual(result, "Sent a close request to window handle 123")
        self.assertIn(("post", 123, win32con.WM_CLOSE, 0, 0), win32gui.window_calls)

    def test_close_window_reports_invalid_handle(self):
        self.assertEqual(windows.close_window(999), "Error: Invalid HWND 999")
        self.assertEqual(win32gui.window_calls, [])

    def test_find_window_by_title_matches_case_insensitively(self):
        self.assertEqual(windows.find_window_by_title("EXAMPLE"), [(123, "Example window")])

    def test_focus_window_restores_and_activates(self):
        result = windows.focus_and_bring_to_front(123)
        self.assertIn("Successfully", result)
        self.assertIn(("show", 123, win32con.SW_SHOW), win32gui.window_calls)
        self.assertIn(("foreground", 123), win32gui.window_calls)

    def test_focus_window_rejects_invalid_handle(self):
        self.assertEqual(windows.focus_and_bring_to_front(999), "Error: Invalid HWND 999")

    def test_get_active_windows_excludes_empty_titles(self):
        self.assertEqual(windows.get_active_windows(), [{"hwnd": 123, "title": "Example window"}])

    def test_set_window_bounds_uses_requested_rect_without_activation(self):
        result = windows.set_window_bounds(123, 10, 20, 800, 600)
        self.assertEqual(result, "Set window 123 bounds to (10, 20, 800, 600)")
        self.assertIn(
            ("bounds", 123, 0, 10, 20, 800, 600, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE),
            win32gui.window_calls,
        )

    def test_set_window_bounds_rejects_invalid_handle_or_size(self):
        with self.assertRaisesRegex(ValueError, "Invalid HWND"):
            windows.set_window_bounds(999, 0, 0, 20, 20)
        for width, height in ((0, 10), (10, 0), (-1, 10)):
            with self.subTest(width=width, height=height), self.assertRaisesRegex(
                ValueError, "positive"
            ):
                windows.set_window_bounds(123, 0, 0, width, height)


if __name__ == "__main__":
    unittest.main()
