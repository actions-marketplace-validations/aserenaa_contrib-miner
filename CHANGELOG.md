# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `max_seconds` input and `--max-seconds` flag, 25 by default. Busy years speed up to fit: delays
  shrink first, then the miner walks several cells per frame, and very busy years skip the wind-up.
- A closing stats card: total contributions, active days, days per ore, best day and longest
  streak.
- A light theme with a daytime sky. `theme` picks the theme of `output`, and `light_output`
  renders a light GIF alongside it for a `<picture>` that follows the viewer's GitHub theme.

## [1.1.0] - 2026-10-06

### Changed

- The header shows the login without an `@` prefix.
- The miner now climbs down a shaft and walks through the mine, striking each ore from the side
  instead of digging a whole week from the surface. Walked dirt becomes a passage, and mined ore
  leaves a tunnel with rubble in its colour, so the final frame still shows the graph.
- GIF frames are cropped to the area that changed, which keeps the longer animation small.
- The offline sample calendar is a little less busy, so the README demo loops sooner.

## [1.0.0] - 2026-10-06

First public release.

### Added

- Composite GitHub Action that renders a user's contribution calendar as an animated 8-bit GIF.
- A miner walks the year and digs one ore per active day: coal, copper, gold and diamond by
  contribution level, with sparkles, a gem pop and a running contribution counter.
- `contrib-miner` command line tool with `--sample` and `--from-json` for offline previews.
- Delta-encoded frames that keep a full year at about 100 KB at the default 2x scale.

[Unreleased]: https://github.com/aserenaa/contrib-miner/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/aserenaa/contrib-miner/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/aserenaa/contrib-miner/releases/tag/v1.0.0
