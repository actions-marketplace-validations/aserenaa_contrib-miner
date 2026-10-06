"""Fetch a user's contribution calendar from the GitHub GraphQL API."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

import requests

GRAPHQL_URL = "https://api.github.com/graphql"

QUERY = """
query($login: String!%(params)s) {
  user(login: $login) {
    login
    contributionsCollection%(args)s {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            weekday
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}


@dataclass(frozen=True)
class Day:
    date: str
    count: int
    level: int


@dataclass
class Calendar:
    login: str
    total: int
    year: int | None = None  # None means the last twelve months
    # Each week has 7 slots indexed by weekday (0 = Sunday). Days outside the
    # one-year window are None, which happens in the first and last week.
    weeks: list[list[Day | None]] = field(default_factory=list)


def build_query(year: int | None) -> str:
    if year is None:
        return QUERY % {"params": "", "args": ""}
    return QUERY % {"params": ", $from: DateTime!, $to: DateTime!", "args": "(from: $from, to: $to)"}


def year_range(year: int) -> dict[str, str]:
    return {"from": f"{year}-01-01T00:00:00Z", "to": f"{year}-12-31T23:59:59Z"}


def parse_calendar(payload: dict, year: int | None = None) -> Calendar:
    """Turn a raw GraphQL response body into a Calendar."""
    if payload.get("errors"):
        messages = "; ".join(e.get("message", "?") for e in payload["errors"])
        raise RuntimeError(f"GitHub GraphQL error: {messages}")
    user = (payload.get("data") or {}).get("user")
    if user is None:
        raise RuntimeError("GitHub user not found")
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks: list[list[Day | None]] = []
    for week in cal["weeks"]:
        slots: list[Day | None] = [None] * 7
        for d in week["contributionDays"]:
            slots[d["weekday"]] = Day(
                date=d["date"],
                count=d["contributionCount"],
                level=LEVELS.get(d["contributionLevel"], 0),
            )
        weeks.append(slots)
    return Calendar(login=user["login"], total=cal["totalContributions"], weeks=weeks, year=year)


def fetch_calendar(login: str, token: str, year: int | None = None, timeout: float = 30) -> Calendar:
    variables = {"login": login, **(year_range(year) if year else {})}
    resp = requests.post(
        GRAPHQL_URL,
        json={"query": build_query(year), "variables": variables},
        headers={"Authorization": f"bearer {token}", "User-Agent": "contrib-miner"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return parse_calendar(resp.json(), year)


def sample_calendar(login: str = "octocat", seed: int = 7, end: date | None = None) -> Calendar:
    """Deterministic fake calendar for offline previews and CI."""
    rng = random.Random(seed)
    end = end or date(2026, 10, 6)
    start = end - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back up to Sunday
    weeks: list[list[Day | None]] = []
    total = 0
    day = start
    while day <= end:
        slots: list[Day | None] = [None] * 7
        for wd in range(7):
            if day <= end:
                busy = rng.random() < 0.4
                count = rng.choice([1, 2, 3, 5, 8, 13]) if busy else 0
                level = 0 if count == 0 else 1 if count < 3 else 2 if count < 5 else 3 if count < 8 else 4
                slots[wd] = Day(day.isoformat(), count, level)
                total += count
            day += timedelta(days=1)
        weeks.append(slots)
    return Calendar(login=login, total=total, weeks=weeks)
