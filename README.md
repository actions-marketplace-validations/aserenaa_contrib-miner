<h1 align="center">contrib-miner</h1>

<p align="center">
  <strong>Your GitHub contribution graph, dug up by an 8-bit miner. One GIF for your profile README, refreshed daily.</strong>
</p>

<p align="center">
  <a href="https://github.com/aserenaa/contrib-miner/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/aserenaa/contrib-miner/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/python-%E2%89%A53.10-3776AB?logo=python&logoColor=white">
  <img alt="GitHub Action" src="https://img.shields.io/badge/GitHub%20Action-composite-2088FF?logo=githubactions&logoColor=white">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

---

The contribution graph is the most personal thing on a GitHub profile, and it is also the most
static. **contrib-miner** turns it into a tiny scene: a miner climbs down into your last year,
walks to every day you contributed and mines it out. The busier the day, the richer the ore.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="docs/sample-light.gif">
    <img src="docs/sample.gif" alt="An 8-bit miner climbing down into a contribution graph, walking through tunnels and striking coal, copper, gold and diamond ore from the side while a contribution counter climbs" width="864">
  </picture>
</p>

## Features

- ⛏️ **Your real graph** — the last year of contributions from the GitHub GraphQL API, placed exactly like the grid on your profile.
- 💎 **Ore by intensity** — GitHub's four contribution levels become coal, copper, gold and diamond.
- 🚶 **A real dig** — the miner walks the tunnels week by week, reaches each ore and strikes it from the side.
- 🎞️ **Animated, then still** — sparkles, a pickaxe swing and a running counter. The loop ends on your year as a tunnel map.
- 📊 **A closing stats card** — total contributions, active days, days per ore, your best day and your longest streak.
- ⏱️ **A loop that fits** — busy years speed up automatically, so the animation stays around 25 seconds.
- 🪶 **Small** — each frame stores only the pixels that changed, so a full year is usually 100 to 250 KB.
- 🌗 **Dark and light** — a night sky or a daytime one with clouds, switched by the viewer's GitHub theme.
- 🔍 **Crisp at any size** — drawn at 1 pixel per sprite pixel and upscaled with nearest-neighbour sampling.
- 🔒 **No servers, no secrets** — runs inside your own Actions with the default token, and publishes to a separate branch so your profile history stays clean.

## Add it to your profile

Your profile README lives in the repository named after your username, for example `octocat/octocat`.

**1. Add a workflow** at `.github/workflows/contrib-miner.yml`:

```yaml
name: Contrib miner

on:
  schedule:
    - cron: "17 3 * * *" # daily
  workflow_dispatch:

permissions:
  contents: read

jobs:
  miner:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: write # push the GIF to the output branch
    steps:
      - uses: aserenaa/contrib-miner@v1
        with:
          github_user_name: ${{ github.repository_owner }}
          output: dist/miner.gif
          light_output: dist/miner-light.gif
      # A single-commit orphan branch, force-pushed, so GIF history never piles up.
      - name: Publish to the output branch
        working-directory: dist
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          git init -q -b output
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add .
          git commit -qm "Update miner GIFs"
          git push -qf "https://x-access-token:${GH_TOKEN}@github.com/${GITHUB_REPOSITORY}.git" output
```

**2. Run it once** from the **Actions** tab (**Contrib miner → Run workflow**) so the `output` branch exists.

**3. Embed the GIF** in your profile `README.md`. GitHub shows the light version to visitors using the light theme:

```html
<picture>
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/<you>/<you>/output/miner-light.gif">
  <img src="https://raw.githubusercontent.com/<you>/<you>/output/miner.gif" alt="My contributions over the last year, mined" width="864">
</picture>
```

Only want one theme? Drop `light_output` and the `<source>` line.

### Inputs

| Input | Default | Description |
|---|---|---|
| `github_user_name` | repository owner | Login whose contributions are rendered |
| `output` | `dist/miner.gif` | Where to write the GIF |
| `year` | none | A calendar year such as `2025`; empty means the last twelve months |
| `theme` | `dark` | Theme of `output`: `dark` or `light` |
| `light_output` | none | Also write a light-theme GIF here, from the same data |
| `scale` | `2` | Integer upscale factor, 1 to 8 |
| `max_seconds` | `25` | Target loop length. Busy years speed up to fit, `0` keeps the natural speed |
| `github_token` | `github.token` | Token for the GraphQL API |

### Private contributions

The default token only sees public contributions. To include private ones:

1. Turn on **Settings → Public profile → Include private contributions on my profile**.
2. Create a classic personal access token with only the `read:user` scope.
3. Store it as an Actions secret, for example `MINER_TOKEN`, and pass `github_token: ${{ secrets.MINER_TOKEN }}`.

> [!TIP]
> GitHub caches README images for a few minutes. If the GIF looks stale right after a run, wait or hard-refresh.

## Run it locally

```bash
git clone https://github.com/aserenaa/contrib-miner.git
cd contrib-miner
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/contrib-miner --sample --output dist/sample.gif                 # offline, fake data
GITHUB_TOKEN=$(gh auth token) .venv/bin/contrib-miner --user <you>        # your real graph
.venv/bin/contrib-miner --from-json response.json --output dist/saved.gif # a saved GraphQL response
```

## How it works

1. `fetch.py` asks the GraphQL API for `contributionsCollection.contributionCalendar` and places each day by weekday.
2. `plan()` in `render.py` routes the miner. He stays one week behind the ores he mines, so he always strikes from the left, and sweeps each week from the closer end.
3. The mine is one persistent canvas that changes a cell at a time: dirt he walks through becomes a passage, and mined ore leaves a tunnel with rubble in its colour.
4. Pillow writes the GIF with a fixed 30-colour palette, crops every frame to the area that changed and makes the rest transparent.

Sprites, tiles, the palette and the 3x5 pixel font are plain text maps in
[`sprites.py`](src/contrib_miner/sprites.py), so redrawing the miner is a text edit.

## Contributing

Bug reports, fixes and new themes are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[changelog](CHANGELOG.md). Report security issues privately as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Abraham Serena
