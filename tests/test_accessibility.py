import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from automation.accessibility import (
    click_accessible_control,
    inspect_accessible_window,
)


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


class AccessibilityTests(unittest.TestCase):
    def setUp(self):
        self.new_project = make_control("New project")
        self.hidden = make_control("Hidden", visible=False)
        self.disabled = make_control("Disabled", enabled=False)
        self.window = Mock()
        self.window.exists.return_value = True
        self.window.window_text.return_value = "Unity Hub"
        self.window.element_info.class_name = "UnityHubWindow"
        self.window.descendants.return_value = [
            self.new_project,
            self.hidden,
            self.disabled,
        ]
        desktop = Mock()
        desktop.window.return_value = self.window
        pywinauto = SimpleNamespace(Desktop=Mock(return_value=desktop))
        modules = patch.dict(sys.modules, {"pywinauto": pywinauto})
        modules.start()
        self.addCleanup(modules.stop)

    def test_inspects_accessible_controls_in_non_browser_desktop_apps(self):
        result = inspect_accessible_window(123)

        self.assertEqual(result["window"], "Unity Hub")
        self.assertEqual(
            result["controls"],
            [
                {
                    "index": 0,
                    "name": "New project",
                    "control_type": "Button",
                    "automation_id": "id-New project",
                }
            ],
        )

    def test_clicks_one_uniquely_named_visible_enabled_control(self):
        result = click_accessible_control(123, "New project")

        self.assertIn("New project", result)
        self.new_project.click_input.assert_called_once_with()
        self.hidden.click_input.assert_not_called()
        self.disabled.click_input.assert_not_called()

    def test_refuses_missing_and_ambiguous_control_names(self):
        with self.assertRaisesRegex(ValueError, "No visible window control"):
            click_accessible_control(123, "Create")

        duplicate = make_control("New project", "Text")
        self.window.descendants.return_value.append(duplicate)
        with self.assertRaisesRegex(ValueError, "2 controls"):
            click_accessible_control(123, "New project")
        self.new_project.click_input.assert_not_called()

    def test_reports_a_window_handle_with_no_accessible_window(self):
        self.window.exists.return_value = False
        with self.assertRaisesRegex(ValueError, "No accessible window"):
            inspect_accessible_window(999)


if __name__ == "__main__":
    unittest.main()
