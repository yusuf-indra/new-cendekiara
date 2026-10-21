# Cendekiara (new)

Practice-test platform: IELTS-style English tests, TPA Bappenas, CPNS SKD, PKN STAN and more,
with a question bank, exam / practice / study modes, a public SEO site and an Android app.

This is a fresh rebuild. The old app (`yusuf-indra/Cendekiara`) is a **reference only**.

- Rules for anyone writing code (AI or human): [`AGENTS.md`](AGENTS.md)
- Where the project is now: [`docs/PROGRESS.md`](docs/PROGRESS.md)
- Design: [`docs/`](docs/)

```bash
make install   # backend venv (+ frontend deps)
make check     # lint, types, tests: exactly what CI runs
make dev       # local backend (memory store, dev login) + frontend
```
