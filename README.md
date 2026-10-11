# Do It

A Windows desktop automation agent that uses an OpenAI-compatible router
(OpenRouter by default) or Google Gemini to manage windows, keyboard and mouse
input, processes, and project files.

## Requirements

- Windows
- Python 3.10 or newer
- An OpenRouter or FreeLLM API key, or a Google AI Studio API key

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root (next to `agent.py`) and configure the
provider you want to use:

```text
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free
```

`.env` is ignored by Git. Do not commit API keys.

For a custom OpenAI-compatible router endpoint, set `OPENROUTER_BASE_URL` to
that endpoint's API base URL. To use the FreeLLM unified API key, set
`FREELLM_API_KEY`; it is used when `OPENROUTER_API_KEY` is not set. You can
leave `OPENROUTER_API_KEY` unset when using the FreeLLM key.

To use Gemini directly with a Google AI Studio API key instead:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
```

`AI_PROVIDER` accepts `openrouter`, `freellm`, or `gemini` and defaults to
`openrouter`. For FreeLLM, set `AI_PROVIDER=freellm` and `FREELLM_API_KEY`;
the model is automatically routed. Only the key for the selected provider is
required. Provider model names can be changed using `OPENROUTER_MODEL` or
`GEMINI_MODEL`.

## Run

From the project root:

```powershell
python agent.py
```

The default prompt opens Notepad, brings it to the foreground, and types
`hello`. Change the `run_agent(...)` prompt at the bottom of `agent.py` to give
the agent a different initial task.

## React prompt UI

Build the React UI and start the Python agent web app from the project root:

```powershell
npm --prefix frontend install
npm --prefix frontend run build
python web.py
```

Open `http://127.0.0.1:8000`. The React app now sends prompts to the local
Python agent, which can use the project's Windows, keyboard, mouse, process,
Telegram, system, dependency, and project-file tools. For actions that require
confirmation, the agent pauses and asks you to approve or cancel in the UI.

In **Settings**, choose OpenRouter, FreeLLM Unified, or Gemini. Enter a key and
model, or leave the key blank to use the matching credentials from `.env`.
FreeLLM uses `http://127.0.0.1:31415/v1` by default and sends `model: "auto"`;
start the [FreeLLMAPI router](https://github.com/tashfeenahmed/freellmapi/releases/latest)
before using it. Settings and the last 20 prompt responses are stored in that
browser's local storage. The API key is not encrypted there and is sent to the
loopback Python server, which uses it to contact the selected provider. The
server binds only to `127.0.0.1`.

For browser tasks, the agent can inspect the visible Chrome window through
Windows accessibility, report the controls it actually sees, and click a
uniquely named observed control. If it encounters multiple account choices, it
can pause and ask you which observed option to use. Tool results are shown live
while the agent decides what to do next. Chrome exposes only the page
information its accessibility tree makes available; when the page does not
expose enough information, the agent must report that limitation rather than
claiming a step succeeded.

For frontend development, run `python web.py --reload` in one terminal and
`npm --prefix frontend run dev` in another; Vite proxies `/api` requests to
the local Python agent. The Python server restarts when project `.py` files
change. Frontend changes are hot-reloaded by Vite. A backend reload interrupts
any agent job currently running. For normal use, start the backend with
`python web.py` without `--reload`.

Run the frontend unit tests and production build from the project root:

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

## Tests

Run every unit test from the project root with one command:

```powershell
python run_tests.py
```

The tests mock Windows APIs and process calls; they do not send real input,
launch applications, or terminate processes. Tests cover tool functions and
their inputs/outputs; they do not test LLM agent orchestration.

## Available tools

- **Windows:** list visible windows, focus a window, open an application, close a
  window gracefully, and set a window's bounds with `set_window_bounds(hwnd, x,
  y, w, h)`.
- **Keyboard and mouse:** send Unicode text to the focused application, press
  named keys with modifiers, move the pointer, click, and scroll. Text input
  reports sent keyboard events; it cannot verify what the target application
  ultimately displays.
- **Chrome:** inspect controls exposed by the visible Chrome window's Windows
  accessibility tree and click a unique observed control. The agent can ask
  you to choose when it sees multiple accounts or results; page content that
  Chrome does not expose cannot be verified automatically.
- **Processes:** `kill_process(pid)` force-terminates a process and its child
  processes. This cannot be undone; only request it when you intend to stop that
  process. The agent itself cannot terminate itself.
- **Project files:** list, read, create, write, delete, and rename files and
  folders. Paths are restricted to the project directory; deleting a directory
  also deletes its contents.
- **Telegram Desktop:** open the logged-in app, search for a person, group, or
  channel, open a unique match, and read visible message text. Sending a message
  searches and opens the named target, then requires direct terminal
  confirmation in the web app, or in the terminal when using the CLI. UI
  automation works only with information Telegram exposes in
  its Windows accessibility tree; it does not enumerate the full chat list.
- **Python dependencies:** the agent can check required packages with
  `manage_project_dependencies(action="check")`. If an integration reports a
  missing dependency, it can offer installation from `requirements.txt`;
  installation requires confirmation in the web app, or `yes` in the terminal
  when using the CLI, and targets the same Python interpreter running the agent.
- **System and hardware:** inspect Windows version/build/architecture, uptime,
  CPU, memory, disks, GPUs, environment variables (sensitive values are
  redacted), battery, and power plans. Shutdown/restart/sleep/hibernate/lock,
  restore-point creation, Windows Update install/hide, and optional-feature
  changes require confirmation in the web app, or `yes` in the terminal when
  using the CLI. Update and feature listing is
  read-only. Administrative actions may require running the terminal as
  administrator.

## Project layout

```text
agent.py                 Entry point
web.py                   Loopback-only web app for the React UI and Python agent
frontend/
  src/App.jsx             React prompt and provider settings UI
  src/agentApi.js         Local Python agent API client
  src/storage.js          Browser-local settings and prompt history
automation/
  agent.py               Provider-independent agent loop
  web.py                 Local HTTP API and confirmation-aware agent jobs
  providers.py           OpenAI-compatible router and Gemini API adapters
  tools.py               Tool schemas, mapping, and dispatch
  windows.py             Window management
  input.py               Keyboard and mouse input
  processes.py           Process management
  system.py              System information and confirmed system controls
  files.py               Project-scoped file management
apps/
  telegram/
    desktop.py           Telegram Desktop UI automation
win32_helper.py          Compatibility imports for older scripts
file_tools.py            Compatibility imports for older scripts
.env.example             Environment-variable template
```
