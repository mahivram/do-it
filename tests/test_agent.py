import unittest
from unittest.mock import Mock, patch

import tests.win32_mocks
from automation.agent import AgentCancelled, _system_prompt, run_agent_request
from automation.providers import ProviderTurn, ToolInvocation


class AgentBehaviorTests(unittest.TestCase):
    def test_web_prompt_requires_live_observation_and_evidence_based_claims(self):
        prompt = _system_prompt(web_mode=True)

        self.assertIn("Ground every claim in actual tool results", prompt)
        self.assertIn("inspect_chrome_window", prompt)
        self.assertIn("ask_user", prompt)
        self.assertIn("do not pretend it succeeded", prompt)

    @patch("automation.agent.create_provider_session")
    def test_cancellation_before_start_does_not_create_provider_session(
        self, create_session
    ):
        with self.assertRaises(AgentCancelled):
            run_agent_request("Do a task", cancel_check=lambda: True)

        create_session.assert_not_called()

    @patch("automation.agent.execute_tool_call", return_value="Action finished")
    @patch("automation.agent.create_provider_session")
    def test_cancellation_after_tool_prevents_another_provider_turn(
        self, create_session, execute_tool
    ):
        session = Mock()
        session.next_turn.return_value = ProviderTurn(
            text=None,
            tool_calls=[ToolInvocation("open_window", '{"application":"chrome"}')],
        )
        create_session.return_value = session
        cancel_checks = iter([False, False, False, False, False, True])

        with self.assertRaises(AgentCancelled):
            run_agent_request(
                "Open Chrome",
                cancel_check=lambda: next(cancel_checks),
            )

        execute_tool.assert_called_once_with("open_window", '{"application":"chrome"}')
        session.next_turn.assert_called_once()
        session.add_tool_results.assert_not_called()

    @patch("automation.agent.execute_tool_call", return_value={"error": "Window missing"})
    @patch("automation.agent.create_provider_session")
    def test_tool_errors_are_reported_as_failed_and_forwarded_to_model(
        self, create_session, execute_tool
    ):
        session = Mock()
        session.next_turn.side_effect = [
            ProviderTurn(
                text=None,
                tool_calls=[ToolInvocation("inspect_chrome_window", '{"hwnd": 123}')],
            ),
            ProviderTurn(text="The browser window could not be inspected.", tool_calls=[]),
        ]
        create_session.return_value = session
        events = []

        result = run_agent_request(
            "Inspect Chrome",
            confirmation_handler=lambda _description: False,
            user_input_handler=lambda _question, _options: None,
            on_tool_event=events.append,
        )

        self.assertEqual(result["response"], "The browser window could not be inspected.")
        self.assertEqual(events[0]["status"], "running")
        self.assertEqual(events[1]["status"], "failed")
        self.assertEqual(events[1]["result"], {"error": "Window missing"})
        session.add_tool_results.assert_called_once()
        self.assertEqual(session.add_tool_results.call_args.args[1], [{"error": "Window missing"}])
        execute_tool.assert_called_once_with(
            "inspect_chrome_window",
            '{"hwnd": 123}',
        )

    @patch("automation.agent.execute_tool_call", return_value="First action ran")
    @patch("automation.agent.create_provider_session")
    def test_executes_only_one_action_from_a_tool_batch(
        self, create_session, execute_tool
    ):
        session = Mock()
        session.next_turn.side_effect = [
            ProviderTurn(
                text=None,
                tool_calls=[
                    ToolInvocation("open_window", '{"application":"chrome"}', "call-1"),
                    ToolInvocation("type_text", '{"text":"search"}', "call-2"),
                ],
            ),
            ProviderTurn(text="I will inspect the browser before typing.", tool_calls=[]),
        ]
        create_session.return_value = session
        events = []

        result = run_agent_request("Search in Chrome", on_tool_event=events.append)

        execute_tool.assert_called_once_with("open_window", '{"application":"chrome"}')
        self.assertEqual(events[0]["status"], "running")
        skipped_event = next(event for event in events if event["status"] == "skipped")
        self.assertIn("Not run", skipped_event["result"]["error"])
        session.add_tool_results.assert_called_once()
        self.assertEqual(
            session.add_tool_results.call_args.args[1],
            [
                "First action ran",
                {"error": skipped_event["result"]["error"]},
            ],
        )
        self.assertIn("inspect", result["response"])


if __name__ == "__main__":
    unittest.main()
