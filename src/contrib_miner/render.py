"""Turn a Calendar into an animated GIF of a miner digging up contributions.

The miner climbs down a shaft on the left and works through the year one week
(column) at a time. He always stands in the column to the left of the ores he
is mining and swings at them from the side, walking up and down to reach each
one. Dirt he walks through becomes a passage; mined ore leaves a tunnel with a
little rubble, so the finished mine still shows the contribution graph.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image

from . import sprites as S
from .fetch import Calendar
from .stats import Stats, summarize

MARGIN_X = 8  # one tile of dirt on each side; the left one holds the entry shaft
HEADER_Y = 3
GRASS_Y = 18
GRID_Y = 21
BOTTOM = 4
ROWS = 7
SURFACE_Y = GRASS_Y - S.TILE  # where the miner stands before climbing down

# Frame timings in milliseconds. GIF stores delays in 10 ms units, so keep multiples of 10.
INTRO_MS = 600
OUTRO_MS = 1000  # the finished mine, before the card
CARD_MS = 4000
TWINKLE_EVERY = 40  # frames; star changes touch the whole sky, so keep them rare
DEFAULT_MAX_SECONDS = 25


@dataclass(frozen=True)
class Timing:
    step: int = 40  # ms per walking frame
    wind_up: int = 50
    strike: int = 70
    stride: int = 1  # cells walked per frame

    def mining_ms(self, moves: int, mines: int) -> int:
        walk_frames = -(-moves // self.stride)  # ceiling division
        if not self.wind_up:
            # Walking between neighbouring ores is folded into the strike frame.
            walk_frames = max(0, walk_frames - mines)
        return walk_frames * self.step + mines * (self.wind_up + self.strike)


# Fastest timings that still read as walking and swinging. Many browsers slow
# GIF delays under 20 ms down to 100 ms, so nothing goes below 20.
FLOOR = Timing(step=20, wind_up=20, strike=40)
MAX_STRIDE = 4


def _tens(ms: float, floor: int) -> int:
    return max(floor, int(ms // 10) * 10)


def choose_timing(moves: int, mines: int, max_seconds: float | None) -> Timing:
    """Pick the slowest, smoothest timing whose loop fits in max_seconds.

    Delays shrink proportionally down to FLOOR first. If that is still too
    long, the miner covers several cells per walking frame, which also keeps
    the file small. As a last resort for very busy years, the wind-up frame is
    dropped: the walking pose already holds the pickaxe up.
    """
    base = Timing()
    if not max_seconds:
        return base
    budget = max_seconds * 1000 - INTRO_MS - OUTRO_MS - CARD_MS
    natural = base.mining_ms(moves, mines)
    if natural <= budget:
        return base
    factor = max(budget, 0) / natural
    timing = Timing(
        step=_tens(base.step * factor, FLOOR.step),
        wind_up=_tens(base.wind_up * factor, FLOOR.wind_up),
        strike=_tens(base.strike * factor, FLOOR.strike),
    )
    stride = 1
    while timing.mining_ms(moves, mines) > budget and stride < MAX_STRIDE:
        stride += 1
        timing = Timing(timing.step, timing.wind_up, timing.strike, stride)
    if timing.mining_ms(moves, mines) > budget:
        timing = Timing(timing.step, 0, timing.strike, timing.stride)
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

    def to_image(self, scale: int, theme: str = "dark") -> Image.Image:
        img = Image.frombytes("P", (self.w, self.h), bytes(self.px))
        img.putpalette(S.palette_bytes(theme))
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


def plan(cal: Calendar) -> list[Step]:
    """Plan a route that mines every ore from its left-hand side."""
    steps = [Step("enter", -1, 0)]
    col, row = -1, 0
    for target, week in enumerate(cal.weeks):
        # Stay one column behind the column being mined. Everything in the
        # column he walks into was already mined or is plain dirt.
        while col < target - 1:
            col += 1
            steps.append(Step("move", col, row))
        ores = _ore_rows(week)
        if not ores:
            continue
        # Sweep the column starting from whichever end is closer.
        if abs(row - ores[-1]) < abs(row - ores[0]):
            ores.reverse()
        for ore_row in ores:
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

    def __init__(self, cal: Calendar, theme: str = "dark"):
        self.cal = cal
        self.theme = theme
        self.cols = len(cal.weeks)
        self.w = MARGIN_X * 2 + self.cols * S.TILE
        self.h = GRID_Y + ROWS * S.TILE + BOTTOM
        rng = random.Random(cal.login)
        self.stars = [
            (rng.randrange(self.w), rng.randrange(1, GRASS_Y - 1), rng.random() < 0.3) for _ in range(self.w // 12)
        ]
        # Clouds stay clear of the shaft on the left and the header text above.
        self.clouds = [(rng.randrange(24, self.w - 10), rng.randrange(9, 13)) for _ in range(self.w // 70)]
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
            twinkle = tick // TWINKLE_EVERY
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
        c.blit(pose, S.MINER_KEY, x, y)
        return c


Run = tuple[str, str]  # (text, palette colour); a "gem:<level>" text draws an ore icon


def _run_width(runs: list[Run]) -> int:
    width = 0
    for text, _ in runs:
        width += 4 if text.startswith("gem:") else len(text) * S.GLYPH_ADVANCE
    return width - 1


# Coal is nearly black, so on the dark card its icon uses lighter greys.
CARD_GEMS = {1: ("coal_hi", "stone_light")}


def card_lines(stats: Stats) -> list[list[Run]]:
    ores: list[Run] = []
    for level, days in stats.ores.items():
        if ores:
            ores.append(("  ", "spark"))
        ores += [(f"gem:{level}", ""), (f" {days}", "spark")]
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


def draw_card(c: Canvas, stats: Stats) -> None:
    """A dark panel centred over the mine. It uses fixed colours so it reads the same in every theme."""
    lines = card_lines(stats)
    pad, line_h = 6, 8
    w = max(_run_width(line) for line in lines) + pad * 2
    h = len(lines) * line_h - 3 + pad * 2
    x0 = (c.w - w) // 2
    y0 = GRID_Y + (ROWS * S.TILE - h) // 2
    c.rect(x0 - 1, y0 - 1, w + 2, h + 2, S.IDX["gold"])
    c.rect(x0, y0, w, h, S.IDX["tunnel"])
    for i, line in enumerate(lines):
        x = x0 + (w - _run_width(line)) // 2
        y = y0 + pad + i * line_h
        for text, colour in line:
            if text.startswith("gem:"):
                ore, hi = CARD_GEMS.get(int(text[4:]), S.ORES[int(text[4:])])
                c.blit(S.GEM, {"o": ore, "h": hi}, x, y + 1)
                x += 4
            else:
                c.text(text, x, y, colour)
                x += len(text) * S.GLYPH_ADVANCE


def render_frames(
    cal: Calendar, max_seconds: float | None = DEFAULT_MAX_SECONDS, theme: str = "dark"
) -> tuple[list[Canvas], list[int]]:
    steps = plan(cal)
    timing = choose_timing(
        moves=sum(s.kind != "mine" for s in steps),
        mines=sum(s.kind == "mine" for s in steps),
        max_seconds=max_seconds,
    )
    scene = Scene(cal, theme)
    frames: list[Canvas] = []
    durations: list[int] = []
    counted = 0
    x, y = 0, SURFACE_Y
    stride = 0
    pending = 0  # cells walked since the last walking frame

    def push(pose: list[str], ms: int, effects=()) -> None:
        frames.append(scene.frame(len(frames), counted, (x, y, pose), effects))
        durations.append(ms)

    def flush_walk() -> None:
        # Draw the miner where he has walked to, alternating legs.
        nonlocal stride, pending
        if pending:
            stride += 1
            push(S.MINER_STEP if stride % 2 else S.MINER_UP, timing.step)
            pending = 0

    push(S.MINER_UP, INTRO_MS)
    for step in steps:
        if step.kind in ("enter", "move"):
            if step.kind == "enter":
                scene.open_shaft()
            scene.walk_into(step.col, step.row)
            x, y = scene.cell_xy(step.col, step.row)
            pending += 1
            if pending >= timing.stride:
                flush_walk()
        else:
            if timing.wind_up:
                flush_walk()
            else:
                pending = 0  # fastest mode: the strike frame also shows where he walked to
            ox, oy = scene.cell_xy(step.col, step.row)
            if timing.wind_up:
                push(S.MINER_UP, timing.wind_up, effects=[(ox + 2, oy + 2)])
            scene.mine(step.col, step.row)
            counted += cal.weeks[step.col][step.row].count
            push(S.MINER_DOWN, timing.strike, effects=[(ox + 4, oy + 1)])
    flush_walk()

    counted = cal.total
    push(S.MINER_UP, OUTRO_MS)
    card = scene.frame(len(frames), counted, (x, y, S.MINER_UP))
    draw_card(card, summarize(cal))
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
) -> Path:
    if theme not in S.THEMES:
        raise ValueError(f"unknown theme {theme!r}; choose from {', '.join(S.THEMES)}")
    frames, durations = _merge_duplicates(*render_frames(cal, max_seconds, theme))
    images = [f.to_image(scale, theme) for f in frames]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # With optimize, Pillow crops each frame to the area that changed and makes
    # unchanged pixels inside it transparent, so a walking step costs a few bytes.
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        disposal=1,  # keep the previous frame; transparent pixels show it through
        transparency=S.IDX["clear"],
        optimize=True,
    )
    return path
