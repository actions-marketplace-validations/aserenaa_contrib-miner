"""Turn a Calendar into an animated GIF of a miner digging up contributions."""

from __future__ import annotations

import random
from itertools import pairwise
from pathlib import Path

from PIL import Image

from . import sprites as S
from .fetch import Calendar

MARGIN_X = 8
HEADER_Y = 3
MINER_Y = 12
GRASS_Y = 23
GRID_Y = 26
BOTTOM = 4
ROWS = 7


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


def _ore_tile(level: int) -> tuple[list[str], dict[str, str]]:
    ore, hi = S.ORES[level]
    rows = [
        "".join(m if m != "." else s for s, m in zip(srow, mrow, strict=True))
        for srow, mrow in zip(S.STONE, S.ORE_MASK, strict=True)
    ]
    return rows, {**S.STONE_KEY, "o": ore, "h": hi}


class Scene:
    def __init__(self, cal: Calendar):
        self.cal = cal
        self.cols = len(cal.weeks)
        self.w = MARGIN_X * 2 + self.cols * S.TILE
        self.h = GRID_Y + ROWS * S.TILE + BOTTOM
        rng = random.Random(cal.login)
        self.stars = [
            (rng.randrange(self.w), rng.randrange(1, GRASS_Y - 2), rng.random() < 0.3) for _ in range(self.w // 12)
        ]
        self.ore_tiles = {lvl: _ore_tile(lvl) for lvl in S.ORES}

    def tile_xy(self, col: int, row: int) -> tuple[int, int]:
        return MARGIN_X + col * S.TILE, GRID_Y + row * S.TILE

    def background(self, dug: set[tuple[int, int]], twinkle: int) -> Canvas:
        c = Canvas(self.w, self.h, S.IDX["bg"])
        twinkle //= 6
        for i, (x, y, bright) in enumerate(self.stars):
            on = bright or (i + twinkle) % 5 != 0
            if on:
                c.set(x, y, S.IDX["star_hi" if bright and twinkle % 2 else "star"])
        # Grass strip with a little texture.
        c.rect(0, GRASS_Y, self.w, 2, S.IDX["grass"])
        c.rect(0, GRASS_Y + 2, self.w, 1, S.IDX["grass_dark"])
        for x in range(0, self.w, 5):
            c.set(x + (x // 5) % 3, GRASS_Y, S.IDX["grass_hi"])
        # Underground: side margins and bottom are plain dirt.
        for y in range(GRID_Y, self.h, S.TILE):
            for x in range(0, self.w, S.TILE):
                c.blit(S.DIRT, S.DIRT_KEY, x, y, flip=((x // S.TILE + y // S.TILE) % 2 == 1))
        for col, week in enumerate(self.cal.weeks):
            for row, day in enumerate(week):
                x, y = self.tile_xy(col, row)
                if (col, row) in dug:
                    c.blit(S.TUNNEL, S.TUNNEL_KEY, x, y)
                elif day is not None and day.level > 0:
                    rows, key = self.ore_tiles[day.level]
                    c.blit(rows, key, x, y)
        return c

    def header(self, c: Canvas, mined: int) -> None:
        c.text(self.cal.login, MARGIN_X, HEADER_Y, "text")
        right = f"{mined} CONTRIBUTIONS"
        colour = "gold" if mined >= self.cal.total else "text_dim"
        c.text(right, self.w - MARGIN_X - S.text_width(right), HEADER_Y, colour)

    def miner(self, c: Canvas, col: int, down: bool) -> None:
        # Place the miner so the pickaxe head lands over the column centre.
        x = MARGIN_X + col * S.TILE - 7
        c.blit(S.MINER_DOWN if down else S.MINER_UP, S.MINER_KEY, x, MINER_Y)


def render_frames(cal: Calendar) -> tuple[list[Canvas], list[int]]:
    scene = Scene(cal)
    frames: list[Canvas] = []
    durations: list[int] = []
    dug: set[tuple[int, int]] = set()
    mined = 0
    tick = 0

    def push(canvas: Canvas, ms: int) -> None:
        nonlocal tick
        frames.append(canvas)
        durations.append(ms)
        tick += 1

    # Intro: miner stands at the start.
    for _ in range(4):
        c = scene.background(dug, tick)
        scene.header(c, mined)
        scene.miner(c, 0, down=False)
        push(c, 150)

    for col, week in enumerate(cal.weeks):
        ores = [(row, d) for row, d in enumerate(week) if d is not None and d.level > 0]
        if not ores:
            c = scene.background(dug, tick)
            scene.header(c, mined)
            scene.miner(c, col, down=False)
            push(c, 60)
            continue

        # Swing up: ores in this column sparkle.
        c = scene.background(dug, tick)
        for row, _ in ores:
            x, y = scene.tile_xy(col, row)
            c.blit(S.SPARKLE, S.SPARKLE_KEY, x + 2 + (row % 2) * 2, y + 2)
        scene.header(c, mined)
        scene.miner(c, col, down=False)
        push(c, 80)

        # Swing down: column is dug out and the best gem pops up.
        dug.update((col, row) for row, _ in ores)
        mined += sum(d.count for _, d in ores)
        best = max(d.level for _, d in ores)
        ore, hi = S.ORES[best]
        c = scene.background(dug, tick)
        scene.header(c, mined)
        scene.miner(c, col, down=True)
        gx = MARGIN_X + col * S.TILE + 2
        c.blit(S.GEM, {"o": ore, "h": hi}, gx, MINER_Y - 1)
        push(c, 100)

    # Outro: show the final dig site, then loop.
    mined = cal.total
    c = scene.background(dug, tick)
    scene.header(c, mined)
    scene.miner(c, len(cal.weeks) - 1, down=False)
    push(c, 3000)
    return frames, durations


def _delta(prev: Canvas, cur: Canvas, clear: int) -> Canvas:
    """Replace pixels that did not change since the previous frame with the
    reserved transparent index. Long transparent runs compress very well."""
    out = cur.copy()
    px, before = out.px, prev.px
    for i in range(len(px)):
        if px[i] == before[i]:
            px[i] = clear
    return out


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
    clear = S.IDX["clear"]
    encoded = [frames[0]] + [_delta(a, b, clear) for a, b in pairwise(frames)]
    images = [f.to_image(scale) for f in encoded]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,
        disposal=1,  # keep the previous frame; transparent pixels show it through
        transparency=clear,
        optimize=False,
    )
    return path
