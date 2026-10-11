import React, { useEffect, useRef, useState } from "react";
import { loadLocalValue, saveLocalValue } from "./storage.js";
import {
  answerConfirmation,
  getAgentJob,
  startAgentJob,
} from "./agentApi.js";

const SETTINGS_KEY = "do-it.settings";
const HISTORY_KEY = "do-it.history";

const DEFAULT_SETTINGS = {
  provider: "openrouter",
  providers: {
    openrouter: {
      apiKey: "",
      model: "openai/gpt-4o-mini",
      baseUrl: "https://openrouter.ai/api/v1",
    },
    freellm: {
      apiKey: "",
      baseUrl: "http://127.0.0.1:31415/v1",
    },
    gemini: {
      apiKey: "",
      model: "gemini-2.5-flash",
    },
  },
};

const PROVIDERS = {
  openrouter: { name: "OpenRouter", shortName: "OR", color: "violet" },
  freellm: { name: "FreeLLM Unified", shortName: "FL", color: "green" },
  gemini: { name: "Google Gemini", shortName: "G", color: "blue" },
};

const OPENAI_COMPATIBLE_PROVIDERS = ["openrouter", "freellm"];
const POLL_INTERVAL_MS = 500;

function waitForNextPoll() {
  return new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
}

function readInitialData() {
  const result = { settings: DEFAULT_SETTINGS, history: [], error: "" };
  try {
    const saved = loadLocalValue(SETTINGS_KEY, DEFAULT_SETTINGS);
    if (saved && PROVIDERS[saved.provider] && saved.providers) {
      const savedFreeLlm = saved.providers.freellm ?? {};
      const freellmConfig = {
        ...DEFAULT_SETTINGS.providers.freellm,
        ...savedFreeLlm,
      };
      if (
        freellmConfig.baseUrl === "https://openrouter.ai/api/v1"
        || freellmConfig.baseUrl === "http://localhost:3001/v1"
      ) {
        freellmConfig.baseUrl = DEFAULT_SETTINGS.providers.freellm.baseUrl;
      }
      result.settings = {
        provider: saved.provider,
        providers: {
          openrouter: {
            ...DEFAULT_SETTINGS.providers.openrouter,
            ...(saved.providers.openrouter ?? {}),
          },
          freellm: freellmConfig,
          gemini: {
            ...DEFAULT_SETTINGS.providers.gemini,
            ...(saved.providers.gemini ?? {}),
          },
        },
      };
    }
  } catch {
    result.error = "Saved settings could not be read. You can enter them again below.";
  }

  try {
    const savedHistory = loadLocalValue(HISTORY_KEY, []);
    if (Array.isArray(savedHistory)) {
      result.history = savedHistory.filter((entry) => (
        entry
        && typeof entry.id === "string"
        && typeof entry.prompt === "string"
        && typeof entry.response === "string"
        && typeof entry.model === "string"
        && PROVIDERS[entry.provider]
      ));
    }
  } catch {
    result.error = "Saved local data could not be read. New data will be saved on this device.";
  }
  return result;
}

function Icon({ name, size = 18 }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": true,
  };
  if (name === "spark") {
    return <svg {...common}><path d="m12 3 1.9 5.8L20 11l-6.1 2.2L12 19l-1.9-5.8L4 11l6.1-2.2L12 3Z" /><path d="m19 14 1.2 2.8L23 18l-2.8 1.2L19 22l-1.2-2.8L15 18l2.8-1.2L19 14Z" /></svg>;
  }
  if (name === "settings") {
    return <svg {...common}><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.4 1.1-1.4 2.4-1.7-.7a8 8 0 0 1-1.5.9l-.3 1.8h-2.8l-.3-1.8a8 8 0 0 1-1.5-.9l-1.7.7-1.4-2.4L7.7 15a8 8 0 0 1 0-1.8l-1.4-1.1 1.4-2.4 1.7.7a8 8 0 0 1 1.5-.9l.3-1.8H14l.3 1.8a8 8 0 0 1 1.5.9l1.7-.7 1.4 2.4-1.4 1.1a8 8 0 0 1-.1 1.8Z" /></svg>;
  }
  if (name === "plus") {
    return <svg {...common}><path d="M12 5v14M5 12h14" /></svg>;
  }
  if (name === "send") {
    return <svg {...common}><path d="m21 3-7.4 18-3.8-7.8L2 9.4 21 3Z" /><path d="M21 3 9.8 13.2" /></svg>;
  }
  if (name === "message") {
    return <svg {...common}><path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5 8 8 0 0 1-3.4-.8L4 20l1.5-4A7.5 7.5 0 1 1 20 11.5Z" /><path d="M8.5 11.5h.01M12.5 11.5h.01M16.5 11.5h.01" /></svg>;
  }
  if (name === "arrow") {
    return <svg {...common}><path d="M7 17 17 7M7 7h10v10" /></svg>;
  }
  return null;
}

export default function App() {
  const [initialData] = useState(readInitialData);
  const [settings, setSettings] = useState(initialData.settings);
  const [history, setHistory] = useState(initialData.history);
  const [page, setPage] = useState("chat");
  const [prompt, setPrompt] = useState("");
  const [activeEntry, setActiveEntry] = useState(initialData.history[0] ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copyError, setCopyError] = useState("");
  const [storageError, setStorageError] = useState(initialData.error);
  const [activeJob, setActiveJob] = useState(null);
  const [confirmationPending, setConfirmationPending] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [copiedEntryId, setCopiedEntryId] = useState(null);
  const promptInput = useRef(null);
  const activeProvider = PROVIDERS[settings.provider];
  const activeConfig = settings.providers[settings.provider];

  useEffect(() => {
    try {
      saveLocalValue(SETTINGS_KEY, settings);
    } catch {
      setStorageError("Settings could not be saved in this browser. Check local storage permissions.");
    }
  }, [settings]);

  useEffect(() => {
    try {
      saveLocalValue(HISTORY_KEY, history);
    } catch {
      setStorageError("Prompt history could not be saved in this browser.");
    }
  }, [history]);

  function updateProviderConfig(provider, changes) {
    setSettings((current) => ({
      ...current,
      providers: {
        ...current.providers,
        [provider]: {
          ...current.providers[provider],
          ...changes,
        },
      },
    }));
  }

  function chooseProvider(provider) {
    setSettings((current) => ({ ...current, provider }));
  }

  async function submitPrompt(event) {
    event.preventDefault();
    const requestPrompt = prompt.trim();
    if (!requestPrompt || loading) {
      return;
    }

    setError("");
    setCopyError("");
    setLoading(true);
    try {
      const config = { ...activeConfig };

      const started = await startAgentJob(
        requestPrompt,
        settings.provider,
        config,
      );
      setActiveJob({ id: started.id, status: started.status, tools: [] });
      let job;
      while (true) {
        await waitForNextPoll();
        job = await getAgentJob(started.id);
        setActiveJob(job);
        if (job.status === "completed") {
          break;
        }
        if (job.status === "failed") {
          throw new Error(job.error || "The Python agent failed.");
        }
      }

      const entry = {
        id: globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`,
        prompt: requestPrompt,
        response: job.response,
        provider: settings.provider,
        model: settings.provider === "freellm" ? "auto" : config.model,
        tools: job.tools,
        createdAt: new Date().toISOString(),
      };
      setHistory((current) => [entry, ...current].slice(0, 20));
      setActiveEntry(entry);
      setPrompt("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The request failed.");
    } finally {
      setLoading(false);
      setConfirmationPending(false);
      setActiveJob(null);
    }
  }

  async function handleConfirmation(approved) {
    if (!activeJob?.confirmation || confirmationPending) {
      return;
    }
    setConfirmationPending(true);
    try {
      await answerConfirmation(
        activeJob.id,
        activeJob.confirmation.id,
        approved,
      );
    } catch (confirmationError) {
      setError(
        confirmationError instanceof Error
          ? confirmationError.message
          : "Could not send the confirmation decision.",
      );
    } finally {
      setConfirmationPending(false);
    }
  }

  function startNewPrompt() {
    setPrompt("");
    setActiveEntry(null);
    setError("");
    setCopyError("");
    setActiveJob(null);
    setPage("chat");
  }

  useEffect(() => {
    function handleShortcut(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        startNewPrompt();
        window.setTimeout(() => promptInput.current?.focus(), 0);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark"><Icon name="spark" size={22} /></span>
          <span>do it<span className="brand-period">.</span></span>
        </a>

        <button className="new-prompt-button" onClick={startNewPrompt}>
          <Icon name="plus" size={18} />
          <span>New prompt</span>
          <span className="shortcut">Ctrl K</span>
        </button>

        <div className="sidebar-label">WORKSPACE</div>
        <button className={`nav-item ${page === "chat" ? "selected" : ""}`} onClick={() => setPage("chat")}>
          <Icon name="message" />
          <span>Prompt studio</span>
        </button>
        <button className={`nav-item ${page === "settings" ? "selected" : ""}`} onClick={() => setPage("settings")}>
          <Icon name="settings" />
          <span>Settings</span>
          <span className="nav-dot" />
        </button>

        <div className="history-heading">
          <span className="sidebar-label">RECENT PROMPTS</span>
          {history.length > 0 && (
            <button
              className="clear-history"
              onClick={() => {
                setHistory([]);
                setActiveEntry(null);
              }}
            >
              Clear
            </button>
          )}
        </div>
        <div className="history-list">
          {history.length === 0 ? (
            <p className="empty-history">Your recent prompts will appear here.</p>
          ) : (
            history.map((entry) => (
              <button
                className={`history-item ${activeEntry?.id === entry.id ? "active" : ""}`}
                key={entry.id}
                onClick={() => {
                  setActiveEntry(entry);
                  setPrompt(entry.prompt);
                  setPage("chat");
                }}
                title={entry.prompt}
              >
                <span className="history-item-title">{entry.prompt}</span>
                <span className="history-item-meta">{PROVIDERS[entry.provider]?.name ?? entry.provider}</span>
              </button>
            ))
          )}
        </div>

        <div className="sidebar-bottom">
          <div className={`provider-avatar ${activeProvider.color}`}>{activeProvider.shortName}</div>
          <div className="sidebar-provider-copy">
            <span className="sidebar-provider-name">{activeProvider.name}</span>
            <span className="sidebar-provider-model">{settings.provider === "freellm" ? "Automatically routed" : activeConfig.model}</span>
          </div>
          <button className="icon-button sidebar-edit" aria-label="Open settings" onClick={() => setPage("settings")}>
            <Icon name="settings" size={17} />
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span><span className="breadcrumb-divider">/</span>
            <span className="breadcrumb-current">{page === "settings" ? "Settings" : "Prompt studio"}</span>
          </div>
          <div className="topbar-actions">
            <span className="local-badge"><span /> Saved locally</span>
            <button
              className="icon-button top-settings"
              aria-label="Open settings"
              onClick={() => setPage(page === "settings" ? "chat" : "settings")}
            >
              <Icon name="settings" />
            </button>
          </div>
        </header>

        {page === "settings" ? (
          <section className="settings-page">
            <div className="page-eyebrow"><span className="eyebrow-line" /> YOUR WORKSPACE</div>
            <h1>Settings<span className="heading-period">.</span></h1>
            <p className="page-description">Choose a model provider and manage your connection.</p>

            {storageError && <div className="notice notice-error">{storageError}</div>}

            <div className="settings-card">
              <div className="settings-card-heading">
                <div>
                  <h2>AI provider</h2>
                  <p>Choose which model receives your prompts.</p>
                </div>
                <span className="card-step">01</span>
              </div>
              <div className="provider-options">
                {Object.entries(PROVIDERS).map(([id, provider]) => (
                  <button
                    className={`provider-option ${settings.provider === id ? "chosen" : ""}`}
                    key={id}
                    onClick={() => chooseProvider(id)}
                  >
                    <span className={`provider-avatar ${provider.color}`}>{provider.shortName}</span>
                    <span className="provider-option-copy">
                      <strong>{provider.name}</strong>
                      <span>
                        {id === "openrouter"
                          ? "OpenAI-compatible models"
                          : id === "freellm"
                            ? "FreeLLM unified API key"
                            : "Google AI models"}
                      </span>
                    </span>
                    <span className="radio-mark">{settings.provider === id && <span />}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="settings-card connection-card">
              <div className="settings-card-heading">
                <div>
                  <h2>{activeProvider.name} connection</h2>
                  <p>Saved in this browser and sent to your local Python agent.</p>
                </div>
                <span className="card-step">02</span>
              </div>
              <label className="form-label" htmlFor="api-key">API key</label>
              <div className="input-with-action">
                <input
                  id="api-key"
                  type={showKey ? "text" : "password"}
                  autoComplete="off"
                  placeholder={
                    settings.provider === "openrouter"
                      ? "sk-or-..."
                      : settings.provider === "freellm"
                        ? "FreeLLM unified API key"
                        : "AIza..."
                  }
                  value={activeConfig.apiKey}
                  onChange={(event) => updateProviderConfig(settings.provider, { apiKey: event.target.value })}
                />
                <button className="reveal-button" onClick={() => setShowKey((visible) => !visible)} type="button">
                  {showKey ? "Hide" : "Show"}
                </button>
              </div>

              {settings.provider === "freellm" ? (
                <div className="auto-routing-note">
                  <span className="routing-icon"><Icon name="spark" size={16} /></span>
                  <span><strong>Model selection is automatic</strong><span>FreeLLM routes each prompt to the best available model.</span></span>
                  <span className="auto-pill">AUTO</span>
                </div>
              ) : (
                <>
                  <label className="form-label" htmlFor="model-name">Model</label>
                  <input
                    id="model-name"
                    type="text"
                    placeholder="Model identifier"
                    value={activeConfig.model}
                    onChange={(event) => updateProviderConfig(settings.provider, { model: event.target.value })}
                  />
                </>
              )}

              {OPENAI_COMPATIBLE_PROVIDERS.includes(settings.provider) && (
                <>
                  <label className="form-label" htmlFor="base-url">API base URL</label>
                  <input
                    id="base-url"
                    type="url"
                    placeholder={settings.provider === "freellm" ? "http://127.0.0.1:31415/v1" : "https://openrouter.ai/api/v1"}
                    value={activeConfig.baseUrl}
                    onChange={(event) => updateProviderConfig(settings.provider, { baseUrl: event.target.value })}
                  />
                </>
              )}

              {settings.provider === "freellm" && (
                <p className="field-hint">
                  Start FreeLLMAPI first; the default router address is http://127.0.0.1:31415/v1.{" "}
                  <a href="https://github.com/tashfeenahmed/freellmapi#quick-start" target="_blank" rel="noreferrer">
                    Setup guide
                  </a>
                </p>
              )}

              <div className="privacy-note">
                <Icon name="spark" size={16} />
                <span>Keys you enter are stored in browser local storage (not encrypted) and sent to the local Python agent. You can leave this blank to use the provider key configured in the project .env file.</span>
              </div>
            </div>

            <div className="settings-saved"><span /> Changes save automatically on this device</div>
          </section>
        ) : (
          <section className="studio-page">
            <div className="studio-intro">
              <div className="page-eyebrow"><span className="eyebrow-line" /> YOUR AI WORKSPACE</div>
              <h1>Make it<br />happen<span className="heading-period">.</span></h1>
              <p className="page-description">One good prompt is all it takes to get moving.</p>
            </div>

            {storageError && <div className="notice notice-error">{storageError}</div>}

            <form className="prompt-card" onSubmit={submitPrompt}>
              <div className="prompt-card-top">
                <span className="prompt-label"><span className="prompt-status-dot" /> MESSAGE</span>
                <button className="model-select" type="button" onClick={() => setPage("settings")}>
                  <span className={`provider-mini ${activeProvider.color}`}>{activeProvider.shortName}</span>
                  <span>{activeProvider.name}</span>
                  <span className="model-divider">·</span>
                  <span className="model-select-model">{settings.provider === "freellm" ? "Auto-routed" : activeConfig.model}</span>
                  <span className="select-chevron">⌄</span>
                </button>
              </div>
              <textarea
                aria-label="Your prompt"
                ref={promptInput}
                placeholder="Ask anything, or describe what you want to make..."
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                    event.preventDefault();
                    event.currentTarget.form.requestSubmit();
                  }
                }}
                rows={4}
              />
              <div className="prompt-card-bottom">
                <span className="keyboard-hint"><kbd>Ctrl</kbd><kbd>↵</kbd> to send</span>
                <button className="send-button" type="submit" disabled={loading || !prompt.trim()}>
                  {loading ? <span className="spinner" /> : <Icon name="send" size={16} />}
                  <span>{loading ? "Thinking..." : "Send prompt"}</span>
                  {!loading && <kbd>↵</kbd>}
                </button>
              </div>
            </form>

            {error && (
              <div className="notice notice-error request-error" role="alert">
                <span className="error-mark">!</span>
                <div><strong>Couldn’t get a response</strong><span>{error}</span></div>
                {error.toLowerCase().includes("api key") && (
                  <button onClick={() => setPage("settings")}>Open settings <Icon name="arrow" size={14} /></button>
                )}
              </div>
            )}

            {activeJob && (
              <div className="agent-progress" aria-live="polite">
                <div className="agent-progress-heading">
                  <span className="agent-progress-indicator">
                    {activeJob.status === "waiting_confirmation" ? "!" : <span className="spinner" />}
                  </span>
                  <span>
                    <strong>
                      {activeJob.status === "waiting_confirmation"
                        ? "Your approval is needed"
                        : activeJob.status === "queued"
                          ? "Waiting for the agent"
                          : "Python agent is working"}
                    </strong>
                    <span>The agent can use your desktop and project tools.</span>
                  </span>
                </div>
                {activeJob.tools?.length > 0 && (
                  <ul className="tool-activity">
                    {activeJob.tools.map((tool, index) => (
                      <li key={`${tool.name}-${index}`}>
                        <span className={`tool-status ${tool.status}`} />
                        <span>{tool.name.replaceAll("_", " ")}</span>
                        <span className="tool-status-label">{tool.status}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {activeJob.confirmation && (
                  <div className="confirmation-card">
                    <div className="confirmation-copy">
                      <strong>Confirm this action</strong>
                      <span>{activeJob.confirmation.description}</span>
                    </div>
                    <div className="confirmation-actions">
                      <button
                        className="confirmation-reject"
                        type="button"
                        disabled={confirmationPending}
                        onClick={() => handleConfirmation(false)}
                      >
                        Cancel
                      </button>
                      <button
                        className="confirmation-approve"
                        type="button"
                        disabled={confirmationPending}
                        onClick={() => handleConfirmation(true)}
                      >
                        {confirmationPending ? "Sending..." : "Approve"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeEntry ? (
              <article className="response-card">
                <div className="response-heading">
                  <div className="response-heading-label"><span className="response-icon"><Icon name="spark" size={17} /></span><span>RESPONSE</span></div>
                  <span className="response-provider">
                    {PROVIDERS[activeEntry.provider]?.name ?? activeEntry.provider}
                    <span>·</span>
                    {activeEntry.provider === "freellm" ? "Auto-routed" : activeEntry.model}
                    {activeEntry.routedVia && <><span>·</span>{activeEntry.routedVia}</>}
                  </span>
                </div>
                <div className="response-prompt"><span className="response-prompt-label">YOU ASKED</span><p>{activeEntry.prompt}</p></div>
                <div className="response-body">{activeEntry.response}</div>
                {activeEntry.tools?.length > 0 && (
                  <details className="response-tools">
                    <summary>{activeEntry.tools.length} agent tool{activeEntry.tools.length === 1 ? "" : "s"} used</summary>
                    <ul className="tool-activity">
                      {activeEntry.tools.map((tool, index) => (
                        <li key={`${tool.name}-${index}`}>
                          <span className={`tool-status ${tool.status}`} />
                          <span>{tool.name.replaceAll("_", " ")}</span>
                          <span className="tool-status-label">{tool.status}</span>
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
                <div className="response-footer">
                  <span>
                    {activeEntry.createdAt
                      ? new Date(activeEntry.createdAt).toLocaleString()
                      : "Saved response"}
                  </span>
                  <button
                    type="button"
                    className="copy-button"
                    onClick={async () => {
                      setCopyError("");
                      try {
                        await navigator.clipboard.writeText(activeEntry.response);
                        setCopiedEntryId(activeEntry.id);
                        window.setTimeout(() => setCopiedEntryId(null), 1400);
                      } catch {
                        setCopyError("Clipboard access was denied.");
                      }
                    }}
                  >
                    {copiedEntryId === activeEntry.id ? "Copied" : "Copy response"}
                  </button>
                  {copyError && <span className="copy-error" role="alert">{copyError}</span>}
                </div>
              </article>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon"><Icon name="spark" size={22} /></div>
                <div><strong>A little room to think.</strong><span>Your answer will show up here.</span></div>
              </div>
            )}

            <div className="studio-footnote">
              <span className="footnote-star">✳</span>
              <span>Your prompt is sent to the local Python agent, which can run this project's desktop and file tools.</span>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
