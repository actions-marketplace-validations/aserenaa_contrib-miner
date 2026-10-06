# Contributing

Thanks for helping make contrib-miner better!

## Setup

contrib-miner needs Python 3.10 or newer.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m unittest discover -s tests   # tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint and formatting
.venv/bin/contrib-miner --sample --output dist/sample.gif   # preview without a token
```

Tests must not need the network or a GitHub token. Use `sample_calendar()` or a saved GraphQL
response with `parse_calendar()`.

## Pull requests

- Keep each pull request focused, with tests for new behavior.
- Run the tests and ruff before pushing; CI runs both on Python 3.10 to 3.13.
- Commit messages are a single capitalized, imperative summary of 50 characters or less
  (for example `Add a night sky theme`).
- Update `README.md` when an input, option or behavior changes.

### Changes to the art

Sprites, tiles, the palette and the pixel font live in
[`src/contrib_miner/sprites.py`](src/contrib_miner/sprites.py) as text maps. Attach a before and
after GIF or PNG to the pull request, rendered with `--sample` so it shows no real account.
The palette must stay under 256 colors, and the rendered sample should stay under about 250 KB.
If the art changes, regenerate `docs/sample.gif` in the same pull request.

Security issues go through [SECURITY.md](SECURITY.md), not public issues.
