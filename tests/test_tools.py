import unittest
from unittest.mock import patch

from tests import win32_mocks
from automation.tools import TOOLS, TOOL_MAP, TOOL_SCHEMAS, execute_tool_call


class ToolDispatchTests(unittest.TestCase):
    def test_every_tool_has_schema_and_callable(self):
        schema_names = {tool["function"]["name"] for tool in TOOLS}
        self.assertEqual(schema_names, set(TOOL_MAP))
        self.assertEqual(schema_names, set(TOOL_SCHEMAS))

    def test_reports_unknown_tool_invalid_json_and_non_object_arguments(self):
        self.assertIn("error", execute_tool_call("unknown", "{}"))
        self.assertIn("Invalid JSON", execute_tool_call("type_text", "{")["error"])
        self.assertIn("JSON object", execute_tool_call("type_text", "[]")["error"])

    def test_reports_all_missing_required_arguments(self):
        result = execute_tool_call("set_window_bounds", "{}")
        self.assertEqual(
            result,
            {
                "error": (
                    "Missing required argument(s) for set_window_bounds: "
                    "hwnd, x, y, w, h. Retry with all required arguments."
                )
            },
        )

    def test_returns_tool_validation_and_runtime_errors_as_result(self):
        result = execute_tool_call("press_key", '{"key":"invalid"}')
        self.assertEqual(
            result,
            {"error": "Tool press_key failed: Unsupported key: invalid"},
        )
        with patch.dict(TOOL_MAP, {"test_error": lambda: (_ for _ in ()).throw(OSError("failed"))}):
            with patch.dict(TOOL_SCHEMAS, {"test_error": {"properties": {}}}):
                self.assertEqual(
                    execute_tool_call("test_error", "{}"),
                    {"error": "Tool test_error failed: failed"},
                )


if __name__ == "__main__":
    unittest.main()
