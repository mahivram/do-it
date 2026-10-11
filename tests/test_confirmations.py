import unittest
from unittest.mock import Mock

from automation.confirmations import request_confirmation, use_confirmation_handler


class ConfirmationTests(unittest.TestCase):
    def test_uses_explicit_web_confirmation_handler(self):
        handler = Mock(return_value=True)
        terminal_input = Mock()

        with use_confirmation_handler(handler):
            approved = request_confirmation("Restart Windows", terminal_input)

        self.assertTrue(approved)
        handler.assert_called_once_with("Restart Windows")
        terminal_input.assert_not_called()

    def test_uses_terminal_confirmation_when_no_handler_is_active(self):
        self.assertTrue(
            request_confirmation("Confirm operation", lambda _prompt: " YES ")
        )
        self.assertFalse(
            request_confirmation("Confirm operation", lambda _prompt: "no")
        )

    def test_cancels_when_terminal_input_is_unavailable(self):
        def unavailable(_prompt):
            raise EOFError

        self.assertFalse(request_confirmation("Confirm operation", unavailable))

    def test_confirmation_handler_is_reset_after_leaving_context(self):
        handler = Mock(return_value=True)
        terminal_input = Mock(return_value="no")

        with use_confirmation_handler(handler):
            self.assertTrue(request_confirmation("First", terminal_input))
        self.assertFalse(request_confirmation("Second", terminal_input))

        handler.assert_called_once_with("First")
        terminal_input.assert_called_once()


if __name__ == "__main__":
    unittest.main()
