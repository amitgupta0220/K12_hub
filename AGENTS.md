# Repository Instructions

These instructions apply to all work in this repository.

## Scope and change discipline

- Work only on the scope requested in the current prompt.
- Inspect existing code, tests, documentation, and configuration before changing them.
- Do not replace or rewrite working code without a specific, documented reason.
- Stop after completing the requested scope. Do not begin a later phase unless explicitly asked.

## Engineering standards

- Use Python type hints for Python code.
- Add or update tests for every behavior change.
- Run every validation command required by the current prompt.
- Stop when a required validation command fails; do not continue to later work.
- Never report a test or validation as passing unless it was actually run successfully.
- Keep UI code separate from data-access code and business logic.
- All SQL used by the application must be read-only and parameterized.
- LLM output must never be executed directly as SQL. Translate questions into a validated, structured query plan with an allowlisted execution path.

## Data safety and privacy

- Never commit secrets, `.env` files, credentials, generated raw data, database volumes, or student-level generated datasets.
- Never use real student information.
- Use deterministic test fixtures instead of relying on live websites.
- Keep synthetic datasets and public aggregate datasets clearly separated in storage, code paths, metadata, and documentation.
- Label public data with its source and label synthetic data as synthetic.

## Documentation and delivery

- Update `docs/progress.md` after every completed task.
- Record important architectural decisions in `docs/decisions.md`.
- Commit after each successful phase when the workspace is a Git repository.
- Before committing, verify that no secret, credential, generated raw data, database volume, or real student information is included.
- At handoff, report changed files, commands run, results, and unresolved issues.
