# Do It

A Windows desktop automation agent that uses selectable OpenRouter or Google
Gemini providers to manage windows, keyboard and mouse input, processes, and
project files.

## Requirements

- Windows
- Python 3.10 or newer
- An OpenRouter API key or Google AI Studio API key

Install the Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root (next to `agent.py`) and configure the
provider you want to use:

```text
AI_PROVIDER=openrouter
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=liquid/lfm-2.5-2.6b:free
```

`.env` is ignored by Git. Do not commit API keys.

To use Gemini directly with a Google AI Studio API key instead:

```text
AI_PROVIDER=gemini
GEMINI_API_KEY=your_google_ai_studio_key
GEMINI_MODEL=gemini-2.5-flash
```

`AI_PROVIDER` accepts `openrouter` or `gemini` and defaults to `openrouter`.
Only the key for the selected provider is required. Provider model names can be
changed using `OPENROUTER_MODEL` or `GEMINI_MODEL`.

## Run

From the project root:

```powershell
python agent.py
```

The default prompt opens Notepad, brings it to the foreground, and types
`hello`. Change the `run_agent(...)` prompt at the bottom of `agent.py` to give
the agent a different initial task.

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
- **Keyboard and mouse:** type Unicode text into the focused application, press
  named keys with modifiers, move the pointer, click, and scroll.
- **Processes:** `kill_process(pid)` force-terminates a process and its child
  processes. This cannot be undone; only request it when you intend to stop that
  process. The agent itself cannot terminate itself.
- **Project files:** list, read, create, write, delete, and rename files and
  folders. Paths are restricted to the project directory; deleting a directory
  also deletes its contents.
- **Telegram Desktop:** open the logged-in app, search for a person, group, or
  channel, open a unique match, and read visible message text. Sending a message
  searches and opens the named target, then requires direct terminal
  confirmation. UI automation works only with information Telegram exposes in
  its Windows accessibility tree; it does not enumerate the full chat list.
- **Python dependencies:** the agent can check required packages with
  `manage_project_dependencies(action="check")`. If an integration reports a
  missing dependency, it can offer installation from `requirements.txt`;
  installation prompts for `yes` and targets the same Python interpreter
  running the agent.
- **System and hardware:** inspect Windows version/build/architecture, uptime,
  CPU, memory, disks, GPUs, environment variables (sensitive values are
  redacted), battery, and power plans. Shutdown/restart/sleep/hibernate/lock,
  restore-point creation, Windows Update install/hide, and optional-feature
  changes require typing `yes` in the terminal. Update and feature listing is
  read-only. Administrative actions may require running the terminal as
  administrator.

## Project layout

```text
agent.py                 Entry point
automation/
  agent.py               Provider-independent agent loop
  providers.py           OpenRouter and Gemini API adapters
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
