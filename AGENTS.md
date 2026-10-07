# Development instructions

- For every new tool/function, behavior change, or bug fix, add or update unit
  tests for the actual function behavior and relevant failure cases.
- Keep tests focused on tools and utility functions (for example, file
  create/read/write, opening/closing windows, typing, mouse actions, process
  management, and bounds). Do not add tests for the LLM agent conversation loop
  or agent orchestration unless explicitly requested.
- Run `python run_tests.py` before considering a code change complete. Do not
  perform real desktop input, launch real applications, or
  terminate real processes in tests; mock operating-system interactions.
- Keep tests colocated by subsystem under `tests/` and use the standard-library
  `unittest` framework unless the project adopts another test runner.
- Keep API keys and other secrets out of tests, fixtures, and committed files.
