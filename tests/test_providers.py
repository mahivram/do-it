import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from google.genai import types

from automation.providers import (
    GeminiSession,
    OpenRouterSession,
    ToolInvocation,
    create_provider_session,
)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_files",
            "description": "Manage project files.",
            "parameters": {
                "type": "object",
                "properties": {"action": {"type": "string"}},
                "required": ["action"],
            },
        },
    }
]


class ProviderConfigurationTests(unittest.TestCase):
    @patch.dict(os.environ, {"AI_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"})
    @patch("google.genai.Client")
    def test_selects_gemini_with_configured_model(self, client_factory):
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-test"}):
            session = create_provider_session("system", "user", TOOLS)

        self.assertIsInstance(session, GeminiSession)
        client_factory.assert_called_once_with(api_key="test-key")
        self.assertEqual(session.model, "gemini-test")

    @patch.dict(os.environ, {"AI_PROVIDER": "openrouter", "OPENROUTER_API_KEY": "test-key"})
    @patch("automation.providers.OpenAI")
    def test_selects_openrouter_with_configured_model(self, client_factory):
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "router-test"}):
            session = create_provider_session("system", "user", TOOLS)

        self.assertIsInstance(session, OpenRouterSession)
        client_factory.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
        )
        self.assertEqual(session.model, "router-test")

    @patch.dict(os.environ, {"AI_PROVIDER": "gemini"}, clear=True)
    def test_requires_key_for_selected_provider(self):
        with self.assertRaisesRegex(ValueError, "GEMINI_API_KEY"):
            create_provider_session("system", "user", TOOLS)

    @patch.dict(os.environ, {"AI_PROVIDER": "unknown"})
    def test_rejects_unknown_provider(self):
        with self.assertRaisesRegex(ValueError, "Unsupported AI_PROVIDER"):
            create_provider_session("system", "user", TOOLS)


class GeminiSessionTests(unittest.TestCase):
    @patch("google.genai.Client")
    def test_wraps_string_tool_result_in_function_response(self, client_factory):
        session = GeminiSession("test-key", "gemini-test", "system", "user", TOOLS)

        session.add_tool_results(
            [ToolInvocation("telegram_open", "{}")],
            ["Opened or focused Telegram Desktop"],
        )

        function_response = session.contents[-1].parts[0].function_response
        self.assertEqual(function_response.name, "telegram_open")
        self.assertEqual(
            function_response.response,
            {"result": "Opened or focused Telegram Desktop"},
        )
        client_factory.assert_called_once_with(api_key="test-key")

    @patch("google.genai.Client")
    def test_converts_function_calls_and_returns_function_results(self, client_factory):
        session = GeminiSession("test-key", "gemini-test", "system", "user", TOOLS)
        client = client_factory.return_value
        call_part = types.Part.from_function_call(
            name="manage_files",
            args={"action": "list"},
        )
        response_content = types.Content(
            role="model",
            parts=[call_part],
        )
        client.models.generate_content.return_value = SimpleNamespace(
            candidates=[SimpleNamespace(content=response_content)],
            text=None,
        )

        turn = session.next_turn()
        self.assertEqual(
            turn.tool_calls,
            [ToolInvocation("manage_files", '{"action": "list"}')],
        )
        client.models.generate_content.assert_called_once()
        self.assertEqual(
            client.models.generate_content.call_args.kwargs["contents"][0],
            "user",
        )
        self.assertEqual(
            session.config.tools[0].function_declarations[0].name,
            "manage_files",
        )

        session.add_tool_results(turn.tool_calls, [{"items": []}])
        function_response = session.contents[-1]
        self.assertEqual(function_response.role, "user")
        self.assertEqual(
            function_response.parts[0].function_response.name,
            "manage_files",
        )
        self.assertEqual(
            function_response.parts[0].function_response.response,
            {"items": []},
        )


class OpenRouterSessionTests(unittest.TestCase):
    @patch("automation.providers.OpenAI")
    def test_preserves_tool_call_and_appends_tool_result(self, client_factory):
        session = OpenRouterSession("test-key", "model-test", "system", "user", TOOLS)
        client = client_factory.return_value
        tool_call = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(name="manage_files", arguments='{"action":"list"}'),
        )
        message = SimpleNamespace(content=None, tool_calls=[tool_call])
        client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=message)]
        )

        turn = session.next_turn()
        self.assertEqual(
            turn.tool_calls,
            [ToolInvocation("manage_files", '{"action":"list"}', "call-1")],
        )
        session.add_tool_results(turn.tool_calls, [{"items": []}])
        self.assertEqual(session.messages[-1]["tool_call_id"], "call-1")
        self.assertEqual(session.messages[-1]["content"], '{"items": []}')


if __name__ == "__main__":
    unittest.main()
