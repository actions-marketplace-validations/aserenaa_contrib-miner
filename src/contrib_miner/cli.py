"""Command line entry point: contrib-miner --user NAME --output out.gif"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .fetch import fetch_calendar, parse_calendar, sample_calendar
from .render import DEFAULT_MAX_SECONDS, render_gif


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="contrib-miner", description=__doc__)
    p.add_argument("--user", help="GitHub login to render")
    p.add_argument("--output", default="dist/miner.gif", help="where to write the GIF")
    p.add_argument("--scale", type=int, default=2, help="integer upscale factor (default 2)")
    p.add_argument(
        "--max-seconds",
        type=float,
        default=DEFAULT_MAX_SECONDS,
        help=f"target loop length; busy years speed up to fit, 0 disables (default {DEFAULT_MAX_SECONDS})",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"),
        help="GitHub token (defaults to $GITHUB_TOKEN or $GH_TOKEN)",
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--sample", action="store_true", help="use deterministic fake data, no network")
    src.add_argument("--from-json", metavar="FILE", help="read a saved GraphQL response instead of calling the API")
    args = p.parse_args(argv)

    if not 1 <= args.scale <= 8:
        p.error("--scale must be between 1 and 8")
    if args.max_seconds < 0:
        p.error("--max-seconds must be 0 or more")

    if args.sample:
        cal = sample_calendar(args.user or "octocat")
    elif args.from_json:
        with open(args.from_json, encoding="utf-8") as fh:
            cal = parse_calendar(json.load(fh))
    else:
        if not args.user:
            p.error("--user is required unless --sample or --from-json is given")
        if not args.token:
            p.error("a token is required: pass --token or set GITHUB_TOKEN")
        cal = fetch_calendar(args.user, args.token)

    out = render_gif(cal, args.output, scale=args.scale, max_seconds=args.max_seconds or None)
    size_kb = out.stat().st_size / 1024
    print(f"wrote {out} ({size_kb:.0f} KB, {len(cal.weeks)} weeks, {cal.total} contributions)", file=sys.stderr)
    return 0
