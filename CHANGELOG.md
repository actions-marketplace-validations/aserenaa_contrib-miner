# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.0.0] - 2026-10-06

First public release.

### Added

- Composite GitHub Action that renders a user's contribution calendar as an animated 8-bit GIF.
- A miner walks the year and digs one ore per active day: coal, copper, gold and diamond by
  contribution level, with sparkles, a gem pop and a running contribution counter.
- `contrib-miner` command line tool with `--sample` and `--from-json` for offline previews.
- Delta-encoded frames that keep a full year at about 100 KB at the default 2x scale.

[Unreleased]: https://github.com/aserenaa/contrib-miner/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/aserenaa/contrib-miner/releases/tag/v1.0.0
