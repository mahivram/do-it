# Do It

A Windows desktop automation agent that uses OpenRouter tool calling to manage
windows, keyboard and mouse input, processes, and project files.

## Requirements

- Windows
- Python 3.10 or newer
- An OpenRouter API key

Install the Python dependencies:

```powershell
python -m pip install openai pywin32
```

Create a `.env` file in the project root (next to `agent.py`) and add your key:

```text
OPENROUTER_API_KEY=your_rotated_openrouter_key
```

`.env` is ignored by Git. Do not commit API keys.

## Run

From the project root:

```powershell
python agent.py
```

The default prompt opens Notepad, brings it to the foreground, and types
`hello`. Change the `run_agent(...)` prompt at the bottom of `agent.py` to give
the agent a different initial task.

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

## Project layout

```text
agent.py                 Entry point
automation/
  agent.py               OpenRouter client and agent loop
  tools.py               Tool schemas, mapping, and dispatch
  windows.py             Window management
  input.py               Keyboard and mouse input
  processes.py           Process management
  files.py               Project-scoped file management
win32_helper.py          Compatibility imports for older scripts
file_tools.py            Compatibility imports for older scripts
.env.example             Environment-variable template
```
