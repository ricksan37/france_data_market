---
paths:
  - "**/*.py"
---

# Python conventions

- Module docstring at the top of every script: what it does, why it exists, how to run it.
- Function docstrings state what is returned and what can be raised (`Raises:` section).
- Comments explain the why; never restate the code, never tell the project history.
- Every `requests` call has `timeout=REQUEST_TIMEOUT_SECONDS` (30 s across the project).
- No bare `raise_for_status()` on external APIs: raise `requests.HTTPError` with the status code, `response.text` and, for auth errors, the `WWW-Authenticate` header.
- Credentials come from the environment through `os.environ[...]` (fail fast with the variable name), loaded by `python-dotenv` locally and injected as secrets in CI. Never print a full token or secret.
- Command-line arguments go through `argparse` (unknown arguments must fail).
- Raw dumps are written once, timestamped, never overwritten, never modified afterwards.
- Exploration and diagnostic scripts live in `exploration/` and import project modules from the root.
- Ollama structured output: `Field(description=...)` in a Pydantic schema does NOT reach the model (the decoding grammar only encodes structure). Every instruction about meaning belongs in the prompt.
