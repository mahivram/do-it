import unittest

import tests.win32_mocks
from automation.interactions import request_user_input, use_user_input_handler
from automation.tools import execute_tool_call


class UserInteractionTests(unittest.TestCase):
    def test_uses_the_active_interface_to_ask_for_a_choice(self):
        received = []

        def answer(question, options):
            received.append((question, options))
            return "Personal account"

        with use_user_input_handler(answer):
            result = execute_tool_call(
                "ask_user",
                '{"question":"Which account?","options":["Work","Personal account"]}',
            )

        self.assertEqual(result, "Personal account")
        self.assertEqual(received, [("Which account?", ["Work", "Personal account"])])

    def test_rejects_invalid_choice_lists(self):
        result = execute_tool_call(
            "ask_user",
            '{"question":"Choose","options":["same","SAME"]}',
        )
        self.assertIn("error", result)
        self.assertIn("unique", result["error"])

    def test_cli_input_accepts_a_numbered_choice(self):
        self.assertEqual(
            request_user_input(
                "Which account?",
                ["Work", "Personal"],
                lambda _prompt: "2",
            ),
            "Personal",
        )

    def test_context_handler_is_reset_after_use(self):
        with use_user_input_handler(lambda _question, _options: "web answer"):
            self.assertEqual(
                request_user_input("Question", input_function=lambda _: "terminal"),
                "web answer",
            )
        self.assertEqual(
            request_user_input("Question", input_function=lambda _: "terminal"),
            "terminal",
        )


if __name__ == "__main__":
    unittest.main()
