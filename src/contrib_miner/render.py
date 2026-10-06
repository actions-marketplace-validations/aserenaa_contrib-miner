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

MARGIN_X = 8  # one tile of dirt on each side; the left one holds the entry shaft
HEADER_Y = 3
GRASS_Y = 18
GRID_Y = 21
BOTTOM = 4
ROWS = 7
SURFACE_Y = GRASS_Y - S.TILE  # where the miner stands before climbing down

# Frame timings in milliseconds. GIF stores delays in 10 ms units, so keep multiples of 10.
INTRO_MS = 600
STEP_MS = 40
WIND_UP_MS = 50
STRIKE_MS = 70
TWINKLE_EVERY = 40  # frames; star changes touch the whole sky, so keep them rare
OUTRO_MS = 3000


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

    def to_image(self, scale: int) -> Image.Image:
        img = Image.frombytes("P", (self.w, self.h), bytes(self.px))
        img.putpalette(S.palette_bytes())
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

    def __init__(self, cal: Calendar):
        self.cal = cal
        self.cols = len(cal.weeks)
        self.w = MARGIN_X * 2 + self.cols * S.TILE
        self.h = GRID_Y + ROWS * S.TILE + BOTTOM
        rng = random.Random(cal.login)
        self.stars = [
            (rng.randrange(self.w), rng.randrange(1, GRASS_Y - 1), rng.random() < 0.3) for _ in range(self.w // 12)
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
        twinkle = tick // TWINKLE_EVERY
        for i, (x, y, bright) in enumerate(self.stars):
            if bright or (i + twinkle) % 5 != 0:
                c.set(x, y, S.IDX["star_hi" if bright and twinkle % 2 else "star"])
        c.text(self.cal.login, MARGIN_X, HEADER_Y, "text")
        right = f"{counted} CONTRIBUTIONS"
        colour = "gold" if counted >= self.cal.total else "text_dim"
        c.text(right, self.w - MARGIN_X - S.text_width(right), HEADER_Y, colour)
        for x, y in effects:
            c.blit(S.SPARKLE, S.SPARKLE_KEY, x, y)
        x, y, pose = miner
        c.blit(pose, S.MINER_KEY, x, y)
        return c


def render_frames(cal: Calendar) -> tuple[list[Canvas], list[int]]:
    scene = Scene(cal)
    frames: list[Canvas] = []
    durations: list[int] = []
    counted = 0
    x, y = 0, SURFACE_Y
    stride = 0

    def push(pose: list[str], ms: int, effects=()) -> None:
        frames.append(scene.frame(len(frames), counted, (x, y, pose), effects))
        durations.append(ms)

    def walk(tx: int, ty: int) -> None:
        # One frame per cell, alternating legs.
        nonlocal x, y, stride
        x, y = tx, ty
        stride += 1
        push(S.MINER_STEP if stride % 2 else S.MINER_UP, STEP_MS)

    push(S.MINER_UP, INTRO_MS)
    for step in plan(cal):
        if step.kind == "enter":
            scene.open_shaft()
            scene.walk_into(step.col, step.row)
            walk(*scene.cell_xy(step.col, step.row))
        elif step.kind == "move":
            scene.walk_into(step.col, step.row)
            walk(*scene.cell_xy(step.col, step.row))
        else:
            ox, oy = scene.cell_xy(step.col, step.row)
            push(S.MINER_UP, WIND_UP_MS, effects=[(ox + 2, oy + 2)])
            scene.mine(step.col, step.row)
            counted += cal.weeks[step.col][step.row].count
            push(S.MINER_DOWN, STRIKE_MS, effects=[(ox + 4, oy + 1)])

    counted = cal.total
    push(S.MINER_UP, OUTRO_MS)
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


def render_gif(cal: Calendar, path: str | Path, scale: int = 2) -> Path:
    frames, durations = _merge_duplicates(*render_frames(cal))
    images = [f.to_image(scale) for f in frames]
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
