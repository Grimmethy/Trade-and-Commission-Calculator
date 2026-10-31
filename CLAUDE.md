# CLAUDE.md
- Never expose private-mode routes publicly. Public access is the allowlist in `app/mode.py`; test with `tests/test_mode.py`.
- Never write inventory data from here; deals are recorded in the inventory plugin's Trades tab.
- Run tests: `.venv/bin/python -m pytest tests`. FastAPI: register literal routes before `{param}` routes.
