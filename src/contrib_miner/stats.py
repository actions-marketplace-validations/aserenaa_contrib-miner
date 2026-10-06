"""Year summary shown on the closing card."""

from __future__ import annotations

from dataclasses import dataclass, field

from .fetch import Calendar


@dataclass(frozen=True)
class Stats:
    total: int
    active_days: int
    best_day: int
    longest_streak: int
    days_by_ore_level: dict[int, int] = field(default_factory=dict)


def summarize(cal: Calendar) -> Stats:
    days = [day for week in cal.weeks for day in week if day is not None]
    days.sort(key=lambda d: d.date)
    streak = longest = 0
    for day in days:
        streak = streak + 1 if day.count > 0 else 0
        longest = max(longest, streak)
    days_by_ore_level = {level: sum(1 for d in days if d.level == level) for level in (4, 3, 2, 1)}
    return Stats(
        total=cal.total,
        active_days=sum(1 for d in days if d.count > 0),
        best_day=max((d.count for d in days), default=0),
        longest_streak=longest,
        days_by_ore_level=days_by_ore_level,
    )
