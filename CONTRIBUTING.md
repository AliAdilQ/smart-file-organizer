# Contributing

1. Fork the repository and create a descriptive branch.
2. Follow the README setup instructions using Python 3.11+.
3. Keep routes small; filesystem behavior belongs in organizer services.
4. Add meaningful tests using pytest temporary directories. Never test against
   personal folders. Preserve preview, no-overwrite, ownership, and undo guarantees.
5. Run `python -m pytest -q` and review the UI on desktop and mobile.
6. Open a pull request explaining the problem, resulting behavior, and verification.

Use PEP 8, clear names, focused commits, and docstrings for nontrivial behavior.
Do not include `.env`, generated databases, logs, personal paths, or credentials.
Security reports belong in the private workflow described in SECURITY.md.
