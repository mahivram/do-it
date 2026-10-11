import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.chrome.desktop import click_chrome_control, inspect_chrome_window


def make_control(name, control_type="Button", visible=True, enabled=True):
    control = Mock()
    control.window_text.return_value = name
    control.element_info = SimpleNamespace(
        name=name,
        control_type=control_type,
        automation_id=f"id-{name}",
    )
    control.is_visible.return_value = visible
    control.is_enabled.return_value = enabled
    return control


class ChromeAccessibilityTests(unittest.TestCase):
    def setUp(self):
        self.account = make_control("Personal account", "ListItem")
        self.sign_in = make_control("Sign in")
        self.hidden = make_control("Hidden account", visible=False)
        self.disabled = make_control("Disabled account", enabled=False)
        self.window = Mock()
        self.window.exists.return_value = True
        self.window.window_text.return_value = "Google - Google Chrome"
        self.window.element_info.class_name = "Chrome_WidgetWin_1"
        self.window.descendants.return_value = [
            self.account,
            self.sign_in,
            self.hidden,
            self.disabled,
        ]
        desktop = Mock()
        desktop.window.return_value = self.window
        pywinauto = SimpleNamespace(Desktop=Mock(return_value=desktop))
        self.modules = patch.dict(sys.modules, {"pywinauto": pywinauto})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_inspection_returns_live_accessible_control_names(self):
        result = inspect_chrome_window(123)

        self.assertEqual(result["window"], "Google - Google Chrome")
        self.assertEqual(
            [control["name"] for control in result["controls"]],
            ["Personal account", "Sign in"],
        )
        self.assertFalse(result["truncated"])

    def test_click_requires_one_exact_visible_accessibility_match(self):
        self.assertIn("Personal account", click_chrome_control(123, "Personal account"))
        self.account.click_input.assert_called_once_with()

    def test_click_refuses_ambiguous_or_missing_controls(self):
        duplicate = make_control("Personal account", "Button")
        self.window.descendants.return_value.append(duplicate)
        with self.assertRaisesRegex(ValueError, "2 controls"):
            click_chrome_control(123, "Personal account")
        with self.assertRaisesRegex(ValueError, "No visible Chrome control"):
            click_chrome_control(123, "Wrong account")
        self.account.click_input.assert_not_called()

    def test_rejects_a_window_that_is_not_chrome(self):
        self.window.window_text.return_value = "Settings"
        self.window.element_info.class_name = "ApplicationFrameWindow"
        with self.assertRaisesRegex(ValueError, "not a Chrome window"):
            inspect_chrome_window(123)


if __name__ == "__main__":
    unittest.main()
