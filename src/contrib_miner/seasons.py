"""Seasonal dressing: sky colours, surface decorations and the miner's hat.

A season never changes the mine itself, only what sits above the grass, so
every frame costs the same and the contribution graph reads the same.
"""

from __future__ import annotations

import datetime
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from . import sprites as S

if TYPE_CHECKING:
    from .render import Canvas, Scene

Decorate = Callable[["Canvas", "Scene", random.Random], None]


@dataclass(frozen=True)
class Season:
    name: str
    start: tuple[int, int]  # (month, day), inclusive
    end: tuple[int, int]  # (month, day), inclusive
    palette: dict[str, dict[str, str]]  # theme -> palette overrides
    hat: dict[str, str]  # overrides for the miner's helmet ("y") and lamp ("w")
    card_border: str
    decorate: Decorate = field(repr=False)

    def active_on(self, day: datetime.date) -> bool:
        return self.start <= (day.month, day.day) <= self.end


def _surface_spots(scene: Scene, rng: random.Random, count: int, width: int) -> list[int]:
    """Spread decorations along the surface, clear of the entry shaft on the left."""
    lo, hi = 24, scene.w - width - 4
    slot = (hi - lo) // count
    return [lo + i * slot + rng.randrange(max(1, slot - width)) for i in range(count)]


# --- Halloween -----------------------------------------------------------------

MOON = [
    "..mmm..",
    ".mmmMm.",
    "mmMmmmm",
    "mmmmmMm",
    "mMmmmmm",
    ".mmmMm.",
    "..mmm..",
]
MOON_KEY = {"m": "gold_hi", "M": "gold"}

BAT = [
    "b.....b",
    "bb.b.bb",
    ".bbbbb.",
    "...b...",
]

PUMPKIN = [
    "...s...",
    ".oOoOo.",
    "oeoOoeo",
    "oOoOoOo",
    "ommmmmo",
    ".oOoOo.",
]
PUMPKIN_KEY = {"s": "grass_dark", "o": "copper", "O": "copper_hi", "e": "gold_hi", "m": "gold_hi"}


def _halloween(c: Canvas, scene: Scene, rng: random.Random) -> None:
    mx = scene.w * 3 // 5
    c.blit(MOON, MOON_KEY, mx, 7)
    bat = {"b": "purple_hi" if scene.theme == "dark" else "coal"}
    for dx, dy in ((-30, 9), (12, 5), (40, 11)):
        c.blit(BAT, bat, mx + dx, dy)
    from .render import GRASS_Y

    for x in _surface_spots(scene, rng, 7, len(PUMPKIN[0])):
        c.blit(PUMPKIN, PUMPKIN_KEY, x, GRASS_Y - len(PUMPKIN) + 1)  # sits slightly in the grass


# --- Christmas -----------------------------------------------------------------

TREE = [
    "...*...",
    "...g...",
    "..gGg..",
    "..gog..",
    ".gGgGg.",
    ".ggogg.",
    "gGgGgGg",
    "gogggog",
    "...t...",
]
TREE_KEY = {"*": "gold", "g": "grass_dark", "G": "grass", "o": "shirt", "t": "dirt_light"}


def _christmas(c: Canvas, scene: Scene, rng: random.Random) -> None:
    from .render import GRASS_Y

    # Snow on the grass: a white top row with a little drift below it.
    c.rect(0, GRASS_Y, scene.w, 1, S.IDX["spark"])
    for x in range(scene.w):
        if rng.random() < 0.35:
            c.set(x, GRASS_Y + 1, S.IDX["spark"])
    for x in _surface_spots(scene, rng, 7, len(TREE[0])):
        c.blit(TREE, TREE_KEY, x, GRASS_Y - len(TREE))


SEASONS: dict[str, Season] = {
    "halloween": Season(
        name="halloween",
        start=(10, 15),
        end=(11, 1),
        palette={
            "dark": {"bg": "#1f1030", "star": "#5d275d", "star_hi": "#8e478c", "accent": "#ef7d57"},
            "light": {"bg": "#f4a261", "star": "#ffd6a5", "star_hi": "#f8c08a", "accent": "#5d275d"},
        },
        hat={"y": "purple", "w": "gold_hi"},
        card_border="copper",
        decorate=_halloween,
    ),
    "christmas": Season(
        name="christmas",
        start=(12, 1),
        end=(12, 26),
        palette={
            "dark": {"bg": "#10213b", "star": "#94b0c2", "star_hi": "#ffffff", "accent": "#ffffff"},
            "light": {"bg": "#d6ecf7", "star": "#ffffff", "star_hi": "#eaf4fb", "accent": "#b13e53"},
        },
        hat={"y": "shirt", "w": "spark"},
        card_border="shirt",
        decorate=_christmas,
    ),
}

SEASON_CHOICES = ["none", "auto", *SEASONS]


def resolve(choice: str | None, today: datetime.date | None = None) -> Season | None:
    """Turn a --season choice into a Season. "auto" picks whichever is active today."""
    if choice in (None, "", "none"):
        return None
    if choice == "auto":
        today = today or datetime.datetime.now(datetime.timezone.utc).date()
        return next((s for s in SEASONS.values() if s.active_on(today)), None)
    if choice not in SEASONS:
        raise ValueError(f"unknown season {choice!r}; choose from {', '.join(SEASON_CHOICES)}")
    return SEASONS[choice]
