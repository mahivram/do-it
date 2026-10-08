import unittest
from unittest.mock import Mock, patch

from apps.telegram import desktop


class FakeControl:
    def __init__(self, name, control_type="ListItem", visible=True, enabled=True):
        self.name = name
        self.element_info = type("ElementInfo", (), {
            "name": name,
            "control_type": control_type,
            "class_name": "",
        })()
        self.visible = visible
        self.enabled = enabled
        self.clicked = False

    def is_visible(self):
        return self.visible

    def is_enabled(self):
        return self.enabled

    def window_text(self):
        return self.name

    def click_input(self):
        self.clicked = True


class FakeWindow:
    def __init__(self, controls=None, edits=None):
        self.controls = controls or []
        self.edits = edits if edits is not None else [FakeControl("Search", "Edit")]
        self.focused = False

    def descendants(self, control_type=None):
        if control_type == "Edit":
            return self.edits
        return self.controls + self.edits

    def set_focus(self):
        self.focused = True

    def process_id(self):
        return 1234

    def window_text(self):
        return "A chat title, not the application name"


class TelegramDesktopTests(unittest.TestCase):
    def test_telegram_window_reports_missing_dependency(self):
        with patch.dict("sys.modules", {"pywinauto": None}):
            with self.assertRaisesRegex(desktop.TelegramDesktopError, "requires pywinauto"):
                desktop._telegram_window()

    def test_telegram_window_reports_app_not_open(self):
        desktop_mock = Mock()
        desktop_mock.return_value.windows.return_value = []
        with (
            patch(
                "apps.telegram.desktop.subprocess.run",
                return_value=Mock(returncode=0, stdout="", stderr=""),
            ),
            patch.dict("sys.modules", {"pywinauto": Mock(Desktop=desktop_mock)}),
            self.assertRaisesRegex(desktop.TelegramNotRunningError, "not running"),
        ):
            desktop._telegram_window()

    def test_telegram_window_finds_process_even_when_title_has_no_telegram(self):
        target_window = FakeWindow()
        other_window = FakeWindow()
        other_window.process_id = lambda: 5678
        desktop_mock = Mock()
        desktop_mock.return_value.windows.return_value = [other_window, target_window]
        tasklist = Mock(
            returncode=0,
            stdout='"Telegram.exe","1234","Console","1","1,000 K"\n',
            stderr="",
        )
        with (
            patch("apps.telegram.desktop.subprocess.run", return_value=tasklist),
            patch.dict("sys.modules", {"pywinauto": Mock(Desktop=desktop_mock)}),
        ):
            self.assertIs(desktop._telegram_window(), target_window)
        desktop_mock.return_value.windows.assert_called_once_with(visible_only=True)

    def test_telegram_window_reports_process_running_without_visible_window(self):
        desktop_mock = Mock()
        desktop_mock.return_value.windows.return_value = []
        tasklist = Mock(
            returncode=0,
            stdout='"Telegram.exe","1234","Console","1","1,000 K"\n',
            stderr="",
        )
        with (
            patch("apps.telegram.desktop.subprocess.run", return_value=tasklist),
            patch.dict("sys.modules", {"pywinauto": Mock(Desktop=desktop_mock)}),
            self.assertRaisesRegex(
                desktop.TelegramNotRunningError,
                "running, but no visible",
            ),
        ):
                desktop._telegram_window()

    @patch("apps.telegram.desktop.os.startfile", create=True)
    @patch("apps.telegram.desktop.os.name", "nt")
    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop._telegram_window")
    def test_open_telegram_starts_protocol_and_focuses_window(
        self, get_window, _sleep, startfile
    ):
        window = Mock()
        get_window.return_value = window
        self.assertEqual(
            desktop.open_telegram(),
            "Opened or focused Telegram Desktop",
        )
        startfile.assert_called_once_with("tg://")
        window.set_focus.assert_called_once()

    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.press_key")
    def test_search_chats_uses_accessible_search_field_and_filters_results(
        self, press_key, type_text, _sleep
    ):
        window = FakeWindow(
            [FakeControl("News Channel"), FakeControl("Work group")],
            edits=[FakeControl("Search", "Edit")],
        )
        with patch.object(desktop, "_telegram_window", return_value=window):
            result = desktop.search_chats("news")
        self.assertEqual(result, [{"name": "News Channel", "control_type": "ListItem"}])
        self.assertTrue(window.focused)
        press_key.assert_called_once_with("a", ["ctrl"])
        type_text.assert_called_once_with("news")
        self.assertTrue(window.edits[0].clicked)

    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.press_key")
    def test_search_chats_rejects_empty_query_without_input(
        self, press_key, type_text, _sleep
    ):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            desktop.search_chats(" ")
        press_key.assert_not_called()
        type_text.assert_not_called()

    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.press_key")
    def test_open_chat_clicks_one_matching_chat(
        self, _press_key, _type_text, _sleep
    ):
        chat = FakeControl("News Channel")
        window = FakeWindow([chat], edits=[FakeControl("Search", "Edit")])
        with patch.object(desktop, "_telegram_window", return_value=window):
            result = desktop.open_chat("News")
        self.assertEqual(result, "Opened Telegram chat: News Channel")
        self.assertTrue(chat.clicked)

    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.press_key")
    def test_open_chat_rejects_ambiguous_results_without_clicking(
        self, _press_key, _type_text, _sleep
    ):
        first = FakeControl("News Channel")
        second = FakeControl("News Group")
        with patch.object(
            desktop, "_telegram_window", return_value=FakeWindow([first, second])
        ):
            with self.assertRaisesRegex(desktop.TelegramDesktopError, "ambiguous"):
                desktop.open_chat("News")
        self.assertFalse(first.clicked)
        self.assertFalse(second.clicked)

    @patch("apps.telegram.desktop.time.sleep")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.press_key")
    def test_open_chat_reports_no_matching_chat(
        self, _press_key, _type_text, _sleep
    ):
        with patch.object(desktop, "_telegram_window", return_value=FakeWindow()):
            with self.assertRaisesRegex(desktop.TelegramDesktopError, "No visible"):
                desktop.open_chat("Missing channel")

    def test_read_messages_returns_visible_text_and_respects_limit(self):
        window = FakeWindow(
            [
                FakeControl("First message", control_type="Text"),
                FakeControl("Second message", control_type="Text"),
                FakeControl("Third message", control_type="Text"),
                FakeControl("Navigation", control_type="Button"),
            ]
        )
        with patch.object(desktop, "_telegram_window", return_value=window):
            self.assertEqual(desktop.read_messages(2), ["Second message", "Third message"])

    def test_read_messages_rejects_invalid_limit_and_missing_text(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 100"):
            desktop.read_messages(0)
        with patch.object(desktop, "_telegram_window", return_value=FakeWindow()):
            with self.assertRaisesRegex(desktop.TelegramDesktopError, "No visible message"):
                desktop.read_messages()

    @patch("apps.telegram.desktop.press_key")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.input", return_value="no")
    def test_send_message_cancelled_without_sending(self, _input, type_text, press_key):
        window = FakeWindow(edits=[FakeControl("Message", control_type="Edit")])
        with (
            patch.object(desktop, "open_chat", return_value="Opened Telegram chat: Target"),
            patch.object(desktop, "_telegram_window", return_value=window),
        ):
            self.assertEqual(
                desktop.send_message("Target", "hello"),
                "Cancelled Telegram message send",
            )
        type_text.assert_not_called()
        press_key.assert_not_called()

    @patch("apps.telegram.desktop.press_key")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.input", side_effect=EOFError)
    def test_send_message_cancels_if_confirmation_is_unavailable(
        self, confirm, type_text, press_key
    ):
        window = FakeWindow(edits=[FakeControl("Message", control_type="Edit")])
        with (
            patch.object(desktop, "open_chat", return_value="Opened Telegram chat: Target"),
            patch.object(desktop, "_telegram_window", return_value=window),
        ):
            self.assertEqual(
                desktop.send_message("Target", "hello"),
                "Cancelled Telegram message send",
            )
        type_text.assert_not_called()
        press_key.assert_not_called()

    @patch("apps.telegram.desktop.press_key")
    @patch("apps.telegram.desktop.type_text")
    @patch("apps.telegram.desktop.input", return_value="yes")
    def test_send_message_confirms_then_types_and_submits(
        self, confirm, type_text, press_key
    ):
        edit = FakeControl("Message", control_type="Edit")
        with (
            patch.object(desktop, "open_chat", return_value="Opened Telegram chat: Target") as open_chat,
            patch.object(
                desktop, "_telegram_window", return_value=FakeWindow(edits=[edit])
            ),
        ):
            result = desktop.send_message("Target", "hello")
        self.assertEqual(result, "Sent Telegram message to Target")
        open_chat.assert_called_once_with("Target")
        self.assertIn("Target", confirm.call_args.args[0])
        self.assertTrue(edit.clicked)
        type_text.assert_called_once_with("hello")
        press_key.assert_called_once_with("enter")

    @patch("apps.telegram.desktop.input")
    def test_send_message_rejects_empty_oversized_and_ambiguous_input(self, prompt):
        for chat_name, text in (
            ("Target", " "),
            ("Target", "x" * 4097),
            (" ", "hello"),
        ):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                desktop.send_message(chat_name, text)
        window = FakeWindow(
            edits=[
                FakeControl("Search", control_type="Edit"),
                FakeControl("Message", control_type="Edit"),
            ]
        )
        with (
            patch.object(desktop, "open_chat", return_value="Opened Telegram chat: Target"),
            patch.object(desktop, "_telegram_window", return_value=window),
            self.assertRaisesRegex(desktop.TelegramDesktopError, "Multiple text inputs"),
        ):
            desktop.send_message("Target", "hello")
        prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
