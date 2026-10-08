"""Provider adapters for OpenAI-compatible and Google Gemini APIs."""

import json
import os
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class ToolInvocation:
    name: str
    arguments: str
    call_id: str | None = None


@dataclass(frozen=True)
class ProviderTurn:
    text: str | None
    tool_calls: list[ToolInvocation]


class OpenRouterSession:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> None:
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.model = model
        self.tools = tools
        self.messages: list[Any] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def next_turn(self) -> ProviderTurn:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.tools,
            temperature=0.2,
        )
        response_message = response.choices[0].message
        self.messages.append(response_message)
        return ProviderTurn(
            text=response_message.content,
            tool_calls=[
                ToolInvocation(
                    name=call.function.name,
                    arguments=call.function.arguments,
                    call_id=call.id,
                )
                for call in response_message.tool_calls or []
            ],
        )

    def add_tool_results(
        self, calls: list[ToolInvocation], results: list[Any]
    ) -> None:
        for call, result in zip(calls, results, strict=True):
            if call.call_id is None:
                raise ValueError("OpenRouter tool call is missing its call ID")
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": json.dumps(result),
                }
            )


class GeminiSession:
    def __init__(
        self,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        tools: list[dict[str, Any]],
    ) -> None:
        from google import genai
        from google.genai import types

        self.types = types
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=tool["function"]["name"],
                            description=tool["function"].get("description"),
                            parameters_json_schema=tool["function"]["parameters"],
                        )
                        for tool in tools
                    ]
                )
            ],
            temperature=0.2,
        )
        self.contents: list[Any] = [user_prompt]

    def next_turn(self) -> ProviderTurn:
        response = self.client.models.generate_content(
            model=self.model,
            contents=self.contents,
            config=self.config,
        )
        if not response.candidates or response.candidates[0].content is None:
            raise RuntimeError("Gemini returned no candidate content")

        content = response.candidates[0].content
        self.contents.append(content)
        calls: list[ToolInvocation] = []
        for part in content.parts or []:
            function_call = part.function_call
            if function_call is not None:
                calls.append(
                    ToolInvocation(
                        name=function_call.name,
                        arguments=json.dumps(function_call.args or {}),
                    )
                )

        return ProviderTurn(text=response.text, tool_calls=calls)

    def add_tool_results(
        self, calls: list[ToolInvocation], results: list[Any]
    ) -> None:
        parts = [
            self.types.Part.from_function_response(
                name=call.name,
                response=result if isinstance(result, dict) else {"result": result},
            )
            for call, result in zip(calls, results, strict=True)
        ]
        self.contents.append(self.types.Content(role="user", parts=parts))


def create_provider_session(
    system_prompt: str,
    user_prompt: str,
    tools: list[dict[str, Any]],
) -> OpenRouterSession | GeminiSession:
    provider = os.environ.get("AI_PROVIDER", "openrouter").strip().lower()
    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required when AI_PROVIDER=openrouter"
            )
        model = os.environ.get("OPENROUTER_MODEL", "liquid/lfm-2.5-2.6b:free")
        return OpenRouterSession(api_key, model, system_prompt, user_prompt, tools)

    if provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        return GeminiSession(api_key, model, system_prompt, user_prompt, tools)

    raise ValueError(
        f"Unsupported AI_PROVIDER {provider!r}; choose 'openrouter' or 'gemini'"
    )
