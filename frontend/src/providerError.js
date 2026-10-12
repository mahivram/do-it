const PROVIDER_NAMES = {
  openrouter: "OpenRouter",
  freellm: "FreeLLMAPI",
  gemini: "Google Gemini",
};

const DEFAULT_FREELLM_BASE_URL = "http://127.0.0.1:31415/v1";

export function isProviderConnectionError(message) {
  return /connection error|connection refused|connecterror|actively refused|failed to establish.*connection|networkerror/i
    .test(message);
}

export function describeProviderError(message, provider, baseUrl) {
  if (!isProviderConnectionError(message)) {
    return message;
  }

  if (provider === "freellm") {
    const routerUrl = baseUrl?.trim() || DEFAULT_FREELLM_BASE_URL;
    return (
      `Could not connect to FreeLLMAPI at ${routerUrl}. Start the FreeLLMAPI ` +
      "router and verify its API base URL in Settings."
    );
  }

  const providerName = PROVIDER_NAMES[provider] ?? "AI provider";
  return `Could not connect to ${providerName}. Check your network and provider settings, then try again.`;
}
