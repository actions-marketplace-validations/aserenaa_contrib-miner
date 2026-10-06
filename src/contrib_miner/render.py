"""Turn a Calendar into an animated GIF of a miner digging up contributions."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from PIL import Image

from . import sprites as S
from .fetch import Calendar
from .layout import BOTTOM, GRASS_Y, GRID_Y, HEADER_Y, MARGIN_X, ROWS, SKY_DECORATION_MIN_X, SURFACE_Y
from .seasons import Season
from .stats import Stats, summarize

INTRO_MS = 600
FINISHED_MINE_MS = 1000
CARD_MS = 4000
TWINKLE_EVERY_FRAMES = 40
DEFAULT_MAX_SECONDS = 30
GIF_DELAY_UNIT_MS = 10
KEEP_PREVIOUS_FRAME = 1


@dataclass(frozen=True)
class Timing:
    step_ms: int = 40
    wind_up_ms: int = 50
    strike_ms: int = 70
    cells_per_step: int = 1

    @property
    def skips_wind_up(self) -> bool:
        return self.wind_up_ms == 0

    def mining_ms(self, moves: int, mines: int) -> int:
        walk_frames = math.ceil(moves / self.cells_per_step)
        if self.skips_wind_up:
            walk_frames = max(0, walk_frames - mines)
        return walk_frames * self.step_ms + mines * (self.wind_up_ms + self.strike_ms)


FASTEST = Timing(step_ms=40, wind_up_ms=40, strike_ms=60)
MAX_CELLS_PER_STEP = 4


def _scaled_delay(ms: float, fastest: int) -> int:
    whole_units = int(ms // GIF_DELAY_UNIT_MS) * GIF_DELAY_UNIT_MS
    return max(fastest, whole_units)


def choose_timing(moves: int, mines: int, max_seconds: float | None) -> Timing:
    """Pick the slowest, smoothest timing whose loop fits in max_seconds.

    Delays shrink down to FASTEST, then the miner walks several cells per
    frame, and very busy years finally skip the wind-up frame.
    """
    base = Timing()
    if not max_seconds:
        return base
    budget = max_seconds * 1000 - INTRO_MS - FINISHED_MINE_MS - CARD_MS
    natural = base.mining_ms(moves, mines)
    if natural <= budget:
        return base
    factor = max(budget, 0) / natural
    timing = Timing(
        step_ms=_scaled_delay(base.step_ms * factor, FASTEST.step_ms),
        wind_up_ms=_scaled_delay(base.wind_up_ms * factor, FASTEST.wind_up_ms),
        strike_ms=_scaled_delay(base.strike_ms * factor, FASTEST.strike_ms),
    )
    while timing.mining_ms(moves, mines) > budget and timing.cells_per_step < MAX_CELLS_PER_STEP:
        timing = replace(timing, cells_per_step=timing.cells_per_step + 1)
    if timing.mining_ms(moves, mines) > budget:
        timing = replace(timing, wind_up_ms=0)
    return timing


class Canvas:
    """A palette-indexed pixel buffer with tiny blitting helpers."""

    def __init__(self, w: int, h: int, fill: int = 0):
        self.w, self.h = w, h
        self.px = bytearray([fill]) * (w * h)

    def copy(self) -> Canvas:
        c = Canvas.__new__(Canvas)
        c.w, c.h, c.px = self.w, self.h, bytearray(self.px)
        return c

    def set(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = color

    def rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, color)

    def blit(self, rows: list[str], key: dict[str, str], x: int, y: int, flip: bool = False) -> None:
        for dy, row in enumerate(rows):
            if flip:
                row = row[::-1]
            for dx, ch in enumerate(row):
                if ch != ".":
                    self.set(x + dx, y + dy, S.IDX[key[ch]])

    def text(self, s: str, x: int, y: int, color: str) -> None:
        c = S.IDX[color]
        for i, ch in enumerate(s.upper()):
            glyph = S.FONT.get(ch, S.FONT["?"])
            for dy, row in enumerate(glyph):
                for dx, bit in enumerate(row):
                    if bit == "#":
                        self.set(x + i * S.GLYPH_ADVANCE + dx, y + dy, c)

    def to_image(self, scale: int, theme: str = "dark", season: Season | None = None) -> Image.Image:
        img = Image.frombytes("P", (self.w, self.h), bytes(self.px))
        img.putpalette(S.palette_bytes(theme, season.palette_by_theme.get(theme) if season else None))
        if scale > 1:
            img = img.resize((self.w * scale, self.h * scale), Image.Resampling.NEAREST)
        return img


@dataclass(frozen=True)
class Step:
    """One action of the miner. For "enter" and "move", (col, row) is where he
    ends up. For "mine", it is the ore he strikes from the cell to its left."""

    kind: Literal["enter", "move", "mine"]
    col: int
    row: int


def _ore_rows(week) -> list[int]:
    return [row for row, day in enumerate(week) if day is not None and day.level > 0]


def _nearest_end_first(rows: list[int], current_row: int) -> list[int]:
    if abs(current_row - rows[-1]) < abs(current_row - rows[0]):
        return rows[::-1]
    return rows


def plan(cal: Calendar) -> list[Step]:
    """Plan a route that mines every ore from its left-hand side.

    The miner stays one column behind the ores he mines, so every cell he
    walks into is already mined or plain dirt.
    """
    steps = [Step("enter", -1, 0)]
    col, row = -1, 0
    for target, week in enumerate(cal.weeks):
        standing_col = target - 1
        while col < standing_col:
            col += 1
            steps.append(Step("move", col, row))
        ores = _ore_rows(week)
        if not ores:
            continue
        for ore_row in _nearest_end_first(ores, row):
            while row != ore_row:
                row += 1 if ore_row > row else -1
                steps.append(Step("move", col, row))
            steps.append(Step("mine", target, ore_row))
    return steps


def _ore_tile(level: int) -> tuple[list[str], dict[str, str]]:
    ore, hi = S.ORES[level]
    rows = [
        "".join(m if m != "." else s for s, m in zip(srow, mrow, strict=True))
        for srow, mrow in zip(S.STONE, S.ORE_MASK, strict=True)
    ]
    return rows, {**S.STONE_KEY, "o": ore, "h": hi}


class Scene:
    """Holds the mine as a persistent canvas that only changes cell by cell."""

    def __init__(self, cal: Calendar, theme: str = "dark", season: Season | None = None):
        self.cal = cal
        self.theme = theme
        self.season = season
        self.miner_key = {**S.MINER_KEY, **(season.hat_colours if season else {})}
        self.cols = len(cal.weeks)
        self.w = MARGIN_X * 2 + self.cols * S.TILE
        self.h = GRID_Y + ROWS * S.TILE + BOTTOM
        rng = random.Random(cal.login)
        self.stars = [
            (rng.randrange(self.w), rng.randrange(1, GRASS_Y - 1), rng.random() < 0.3) for _ in range(self.w // 12)
        ]
        self.clouds = [
            (rng.randrange(SKY_DECORATION_MIN_X, self.w - 10), rng.randrange(9, 13)) for _ in range(self.w // 70)
        ]
        self.ore_tiles = {lvl: _ore_tile(lvl) for lvl in S.ORES}
        self.walked: set[tuple[int, int]] = set()
        self.mined: set[tuple[int, int]] = set()
        self.base = self._draw_base()

    def cell_xy(self, col: int, row: int) -> tuple[int, int]:
        return MARGIN_X + col * S.TILE, GRID_Y + row * S.TILE

    def level(self, col: int, row: int) -> int:
        if 0 <= col < self.cols:
            day = self.cal.weeks[col][row]
            return day.level if day is not None else 0
        return 0

    def _draw_base(self) -> Canvas:
        c = Canvas(self.w, self.h, S.IDX["bg"])
        c.rect(0, GRASS_Y, self.w, 2, S.IDX["grass"])
        c.rect(0, GRASS_Y + 2, self.w, 1, S.IDX["grass_dark"])
        for x in range(0, self.w, 5):
            c.set(x + (x // 5) % 3, GRASS_Y, S.IDX["grass_hi"])
        for y in range(GRID_Y, self.h, S.TILE):
            for x in range(0, self.w, S.TILE):
                c.blit(S.DIRT, S.DIRT_KEY, x, y, flip=((x // S.TILE + y // S.TILE) % 2 == 1))
        if self.theme == "light":
            for x, y in self.clouds:
                c.blit(S.CLOUD, S.CLOUD_KEY, x, y)
        if self.season:
            self.season.decorate(c, self, random.Random(f"{self.cal.login}:{self.season.name}"))
        for col in range(self.cols):
            for row in range(ROWS):
                lvl = self.level(col, row)
                if lvl:
                    rows, key = self.ore_tiles[lvl]
                    c.blit(rows, key, *self.cell_xy(col, row))
        return c

    def open_shaft(self) -> None:
        self.base.rect(0, GRASS_Y, S.TILE, GRID_Y - GRASS_Y, S.IDX["tunnel"])

    def walk_into(self, col: int, row: int) -> None:
        if (col, row) in self.walked or (col, row) in self.mined:
            return
        self.walked.add((col, row))
        self.base.blit(S.PATH, S.PATH_KEY, *self.cell_xy(col, row))

    def mine(self, col: int, row: int) -> None:
        ore, hi = S.ORES[self.level(col, row)]
        self.mined.add((col, row))
        self.base.blit(S.MINED, {**S.TUNNEL_KEY, "o": ore, "h": hi}, *self.cell_xy(col, row))

    def frame(self, tick: int, counted: int, miner: tuple[int, int, list[str]], effects=()) -> Canvas:
        c = self.base.copy()
        if self.theme == "dark":
            twinkle = tick // TWINKLE_EVERY_FRAMES
            for i, (x, y, bright) in enumerate(self.stars):
                if bright or (i + twinkle) % 5 != 0:
                    c.set(x, y, S.IDX["star_hi" if bright and twinkle % 2 else "star"])
        title = f"{self.cal.login} {self.cal.year}" if self.cal.year else self.cal.login
        c.text(title, MARGIN_X, HEADER_Y, "text")
        right = f"{counted} CONTRIBUTIONS"
        colour = "accent" if counted >= self.cal.total else "text_dim"
        c.text(right, self.w - MARGIN_X - S.text_width(right), HEADER_Y, colour)
        for x, y in effects:
            c.blit(S.SPARKLE, S.SPARKLE_KEY, x, y)
        x, y, pose = miner
        c.blit(pose, self.miner_key, x, y)
        return c


Run = tuple[str, str]
GEM_PREFIX = "gem:"
GEM_WIDTH = 4
CARD_GEM_COLOURS = {**S.ORES, 1: ("coal_hi", "stone_light")}


def _run_width(runs: list[Run]) -> int:
    width = 0
    for text, _ in runs:
        width += GEM_WIDTH if text.startswith(GEM_PREFIX) else len(text) * S.GLYPH_ADVANCE
    return width - 1


def card_lines(stats: Stats) -> list[list[Run]]:
    ores: list[Run] = []
    for level, days in stats.days_by_ore_level.items():
        if ores:
            ores.append(("  ", "spark"))
        ores += [(f"{GEM_PREFIX}{level}", ""), (f" {days}", "spark")]
    return [
        [
            (str(stats.total), "spark"),
            (" CONTRIBUTIONS IN ", "stone_light"),
            (str(stats.active_days), "spark"),
            (" DAYS", "stone_light"),
        ],
        ores,
        [
            ("BEST DAY ", "stone_light"),
            (str(stats.best_day), "spark"),
            ("  LONGEST STREAK ", "stone_light"),
            (str(stats.longest_streak), "spark"),
            (" DAYS", "stone_light"),
        ],
    ]


def draw_card(c: Canvas, stats: Stats, border: str = "gold") -> None:
    """A dark panel centred over the mine. It uses fixed colours so it reads the same in every theme."""
    lines = card_lines(stats)
    pad, line_h = 6, 8
    w = max(_run_width(line) for line in lines) + pad * 2
    h = len(lines) * line_h - 3 + pad * 2
    x0 = (c.w - w) // 2
    y0 = GRID_Y + (ROWS * S.TILE - h) // 2
    c.rect(x0 - 1, y0 - 1, w + 2, h + 2, S.IDX[border])
    c.rect(x0, y0, w, h, S.IDX["tunnel"])
    for i, line in enumerate(lines):
        x = x0 + (w - _run_width(line)) // 2
        y = y0 + pad + i * line_h
        for text, colour in line:
            if text.startswith(GEM_PREFIX):
                ore, hi = CARD_GEM_COLOURS[int(text.removeprefix(GEM_PREFIX))]
                c.blit(S.GEM, {"o": ore, "h": hi}, x, y + 1)
                x += GEM_WIDTH
            else:
                c.text(text, x, y, colour)
                x += len(text) * S.GLYPH_ADVANCE


def render_frames(
    cal: Calendar,
    max_seconds: float | None = DEFAULT_MAX_SECONDS,
    theme: str = "dark",
    season: Season | None = None,
) -> tuple[list[Canvas], list[int]]:
    steps = plan(cal)
    timing = choose_timing(
        moves=sum(s.kind != "mine" for s in steps),
        mines=sum(s.kind == "mine" for s in steps),
        max_seconds=max_seconds,
    )
    scene = Scene(cal, theme, season)
    frames: list[Canvas] = []
    durations: list[int] = []
    counted = 0
    x, y = 0, SURFACE_Y
    steps_shown = 0
    cells_walked_unshown = 0

    def push(pose: list[str], ms: int, effects=()) -> None:
        frames.append(scene.frame(len(frames), counted, (x, y, pose), effects))
        durations.append(ms)

    def show_walk() -> None:
        nonlocal steps_shown, cells_walked_unshown
        if cells_walked_unshown:
            steps_shown += 1
            push(S.MINER_STEP if steps_shown % 2 else S.MINER_UP, timing.step_ms)
            cells_walked_unshown = 0

    push(S.MINER_UP, INTRO_MS)
    for step in steps:
        if step.kind in ("enter", "move"):
            if step.kind == "enter":
                scene.open_shaft()
            scene.walk_into(step.col, step.row)
            x, y = scene.cell_xy(step.col, step.row)
            cells_walked_unshown += 1
            if cells_walked_unshown >= timing.cells_per_step:
                show_walk()
        else:
            ox, oy = scene.cell_xy(step.col, step.row)
            if timing.skips_wind_up:
                cells_walked_unshown = 0
            else:
                show_walk()
                push(S.MINER_UP, timing.wind_up_ms, effects=[(ox + 2, oy + 2)])
            scene.mine(step.col, step.row)
            counted += cal.weeks[step.col][step.row].count
            push(S.MINER_DOWN, timing.strike_ms, effects=[(ox + 4, oy + 1)])
    show_walk()

    counted = cal.total
    push(S.MINER_UP, FINISHED_MINE_MS)
    card = scene.frame(len(frames), counted, (x, y, S.MINER_UP))
    draw_card(card, summarize(cal), season.card_border if season else "gold")
    frames.append(card)
    durations.append(CARD_MS)
    return frames, durations


def _merge_duplicates(frames: list[Canvas], durations: list[int]) -> tuple[list[Canvas], list[int]]:
    """Fold identical consecutive frames into one longer frame."""
    out_f: list[Canvas] = []
    out_d: list[int] = []
    for f, d in zip(frames, durations, strict=True):
        if out_f and out_f[-1].px == f.px:
            out_d[-1] += d
        else:
            out_f.append(f)
            out_d.append(d)
    return out_f, out_d


def render_gif(
    cal: Calendar,
    path: str | Path,
    scale: int = 2,
    max_seconds: float | None = DEFAULT_MAX_SECONDS,
    theme: str = "dark",
    season: Season | None = None,
) -> Path:
    if theme not in S.THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose from {', '.join(S.THEMES)}")
    frames, durations = _merge_duplicates(*render_frames(cal, max_seconds, theme, season))
    images = [f.to_image(scale, theme, season) for f in frames]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        disposal=KEEP_PREVIOUS_FRAME,
        transparency=S.IDX["transparent"],
        optimize=True,
    )
    return path
