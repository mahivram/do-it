import unittest

from tests.win32_mocks import win32api, win32con
from automation.input import (
    click_mouse,
    move_mouse,
    press_key,
    scroll_mouse,
    type_text,
)


class KeyboardTests(unittest.TestCase):
    def setUp(self):
        win32api.key_events.clear()

    def test_type_text_sends_unicode_utf16_units(self):
        self.assertEqual(type_text("A🙂"), "Typed 2 characters")
        units = [event[1] for event in win32api.key_events]
        self.assertEqual(units, [ord("A"), ord("A"), 0xD83D, 0xD83D, 0xDE42, 0xDE42])

    def test_type_text_rejects_oversized_input(self):
        with self.assertRaisesRegex(ValueError, "5000"):
            type_text("x" * 5001)
        self.assertEqual(win32api.key_events, [])

    def test_press_key_releases_key_and_modifiers_in_reverse_order(self):
        self.assertEqual(press_key("enter", ["ctrl", "shift"]), "Pressed ctrl+shift+enter")
        self.assertEqual(
            [(event[0], event[2]) for event in win32api.key_events],
            [
                (win32con.VK_CONTROL, 0),
                (win32con.VK_SHIFT, 0),
                (win32con.VK_RETURN, 0),
                (win32con.VK_RETURN, 2),
                (win32con.VK_SHIFT, 2),
                (win32con.VK_CONTROL, 2),
            ],
        )

    def test_press_key_rejects_unsupported_key_or_modifier(self):
        with self.assertRaisesRegex(ValueError, "Unsupported key"):
            press_key("unknown")
        with self.assertRaisesRegex(ValueError, "Modifiers"):
            press_key("enter", ["meta"])

    def test_press_key_releases_pressed_modifiers_if_press_raises(self):
        calls = []

        def fail_on_key(key, _scan, flags, _extra):
            calls.append((key, flags))
            if key == win32con.VK_RETURN and flags == 0:
                raise OSError("simulated input failure")

        win32api.keybd_event = fail_on_key
        with self.assertRaisesRegex(OSError, "simulated"):
            press_key("enter", ["ctrl"])
        self.assertEqual(calls[-1], (win32con.VK_CONTROL, 2))
        win32api.keybd_event = lambda *args: win32api.key_events.append(args)


class MouseTests(unittest.TestCase):
    def setUp(self):
        win32api.mouse_events.clear()
        win32api.cursor_positions.clear()

    def test_move_mouse_sets_coordinates(self):
        self.assertEqual(move_mouse(20, 30), "Moved mouse to (20, 30)")
        self.assertEqual(win32api.cursor_positions, [(20, 30)])

    def test_click_mouse_emits_down_up_for_each_click(self):
        self.assertEqual(click_mouse("right", 2), "Clicked right mouse button 2 time(s)")
        self.assertEqual(
            [event[0] for event in win32api.mouse_events],
            [
                win32con.MOUSEEVENTF_RIGHTDOWN,
                win32con.MOUSEEVENTF_RIGHTUP,
                win32con.MOUSEEVENTF_RIGHTDOWN,
                win32con.MOUSEEVENTF_RIGHTUP,
            ],
        )

    def test_click_mouse_rejects_invalid_button_or_count(self):
        for args in ({"button": "extra"}, {"clicks": 0}, {"clicks": 11}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                click_mouse(**args)

    def test_scroll_mouse_uses_signed_delta_and_rejects_zero(self):
        self.assertEqual(scroll_mouse(-120), "Scrolled mouse wheel by -120")
        self.assertEqual(win32api.mouse_events, [(win32con.MOUSEEVENTF_WHEEL, 0, 0, -120, 0)])
        with self.assertRaisesRegex(ValueError, "zero"):
            scroll_mouse(0)


if __name__ == "__main__":
    unittest.main()
