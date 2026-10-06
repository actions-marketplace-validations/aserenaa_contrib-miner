"""Palette, pixel font and sprite maps. Every sprite is a list of strings
where each character maps to a palette entry and '.' is transparent."""

from __future__ import annotations

# Order matters: the index of each entry is its GIF palette index.
PALETTE: list[tuple[str, str]] = [
    ("bg", "#1a1c2c"),
    ("star", "#566c86"),
    ("star_hi", "#94b0c2"),
    ("text", "#f4f4f4"),
    ("text_dim", "#94b0c2"),
    ("grass", "#38b764"),
    ("grass_hi", "#a7f070"),
    ("grass_dark", "#257179"),
    ("dirt", "#6b4226"),
    ("dirt_dark", "#4a2c17"),
    ("dirt_light", "#8a5a35"),
    ("stone", "#5b6378"),
    ("stone_dark", "#3a3f52"),
    ("stone_light", "#8b93a8"),
    ("coal", "#14141c"),
    ("coal_hi", "#4d4d5e"),
    ("copper", "#ef7d57"),
    ("copper_hi", "#ffb38a"),
    ("gold", "#ffcd75"),
    ("gold_hi", "#fff4c2"),
    ("diamond", "#41a6f6"),
    ("diamond_hi", "#73eff7"),
    ("tunnel", "#0d0d14"),
    ("tunnel_edge", "#262033"),
    ("skin", "#f2b88f"),
    ("shirt", "#b13e53"),
    ("pants", "#3b5dc9"),
    ("boots", "#333c57"),
    ("spark", "#ffffff"),
    # Reserved: marks "unchanged since last frame" in delta-encoded GIF frames.
    ("clear", "#ff00ff"),
]

IDX = {name: i for i, (name, _) in enumerate(PALETTE)}


def palette_bytes() -> bytes:
    out = bytearray()
    for _, hexcode in PALETTE:
        out += bytes.fromhex(hexcode[1:])
    return bytes(out)


TILE = 8

# --- Tiles -----------------------------------------------------------------

DIRT = [
    "ddddDddd",
    "dlddddDd",
    "ddddlddd",
    "dDdddddd",
    "ddddddld",
    "ddlddDdd",
    "Dddddddd",
    "dddlddDd",
]
DIRT_KEY = {"d": "dirt", "D": "dirt_dark", "l": "dirt_light"}

STONE = [
    "LLLLLLLs",
    "LssssssS",
    "LssssssS",
    "LssssssS",
    "LssssssS",
    "LssssssS",
    "LssssssS",
    "sSSSSSSS",
]
STONE_KEY = {"s": "stone", "S": "stone_dark", "L": "stone_light"}

ORE_MASK = [
    "........",
    "..ho....",
    ".oo..ho.",
    "....oo..",
    "..o.....",
    ".ho..oh.",
    "..o..o..",
    "........",
]

# Ore colours for contribution levels 1..4.
ORES = {
    1: ("coal", "coal_hi"),
    2: ("copper", "copper_hi"),
    3: ("gold", "gold_hi"),
    4: ("diamond", "diamond_hi"),
}

TUNNEL_KEY = {"t": "tunnel", "e": "tunnel_edge"}

SPARKLE = [
    ".x.",
    "xwx",
    ".x.",
]
SPARKLE_KEY = {"x": "gold_hi", "w": "spark"}

# Ore icon for the closing card.
GEM = [
    ".h.",
    "hoo",
    ".o.",
]

# Walked-through dirt: a darker passage.
PATH = [
    "eeeeeeee",
    "DDDDDDDD",
    "DDdDDDDD",
    "DDDDDDDD",
    "DDDDDdDD",
    "DDDDDDDD",
    "DdDDDDDD",
    "DDDDDDdD",
]
PATH_KEY = {"D": "dirt_dark", "d": "dirt", "e": "tunnel_edge"}

# A mined ore: an empty tunnel with a little rubble in the ore's colour,
# so the finished mine still shows the shape of the contribution graph.
MINED = [
    "eeeeeeee",
    "tttttttt",
    "tttttttt",
    "tttttttt",
    "tttttttt",
    "tttttttt",
    "tthtttot",
    "toohthoo",
]

# --- Miner (faces right, 10x8, fits in one 8x8 tunnel) -----------------------
# Columns 8-9 reach into the next tile, so the pickaxe hits the ore beside him.

MINER_KEY = {
    "y": "gold",
    "w": "gold_hi",
    "k": "skin",
    "e": "bg",
    "r": "shirt",
    "p": "pants",
    "o": "boots",
    "b": "dirt_light",
    "H": "text_dim",
}

# Pickaxe raised: used for walking (two leg poses) and the wind-up.
MINER_UP = [
    ".yyy..HHH.",
    "yyyyw.b..H",
    ".kke..b...",
    ".kkk.b....",
    "rrrrkb....",
    ".rrr......",
    ".ppp......",
    ".o.o......",
]
MINER_STEP = MINER_UP[:6] + [
    ".pp.p.....",
    "o...o.....",
]

# Pickaxe swung into the tile on the right.
MINER_DOWN = [
    ".yyy......",
    "yyyyw.....",
    ".kke....H.",
    ".kkk.....H",
    "rrrrkbbbbH",
    ".rrr.....H",
    ".ppp....H.",
    ".o.o......",
]

# --- 3x5 pixel font -----------------------------------------------------------

# fmt: off
_FONT_SRC = {
    "A": ".#.|#.#|###|#.#|#.#", "B": "##.|#.#|##.|#.#|##.", "C": ".##|#..|#..|#..|.##",
    "D": "##.|#.#|#.#|#.#|##.", "E": "###|#..|##.|#..|###", "F": "###|#..|##.|#..|#..",
    "G": ".##|#..|#.#|#.#|.##", "H": "#.#|#.#|###|#.#|#.#", "I": "###|.#.|.#.|.#.|###",
    "J": "..#|..#|..#|#.#|.#.", "K": "#.#|#.#|##.|#.#|#.#", "L": "#..|#..|#..|#..|###",
    "M": "#.#|###|###|#.#|#.#", "N": "##.|#.#|#.#|#.#|#.#", "O": ".#.|#.#|#.#|#.#|.#.",
    "P": "##.|#.#|##.|#..|#..", "Q": ".#.|#.#|#.#|##.|.##", "R": "##.|#.#|##.|#.#|#.#",
    "S": ".##|#..|.#.|..#|##.", "T": "###|.#.|.#.|.#.|.#.", "U": "#.#|#.#|#.#|#.#|###",
    "V": "#.#|#.#|#.#|#.#|.#.", "W": "#.#|#.#|###|###|#.#", "X": "#.#|#.#|.#.|#.#|#.#",
    "Y": "#.#|#.#|.#.|.#.|.#.", "Z": "###|..#|.#.|#..|###",
    "0": "###|#.#|#.#|#.#|###", "1": ".#.|##.|.#.|.#.|###", "2": "##.|..#|.#.|#..|###",
    "3": "##.|..#|.#.|..#|##.", "4": "#.#|#.#|###|..#|..#", "5": "###|#..|##.|..#|##.",
    "6": ".##|#..|###|#.#|###", "7": "###|..#|.#.|.#.|.#.", "8": "###|#.#|###|#.#|###",
    "9": "###|#.#|###|..#|##.",
    "-": "...|...|###|...|...", " ": "...|...|...|...|...", ":": "...|.#.|...|.#.|...",
    "@": ".#.|#.#|###|#..|.##", "?": "##.|..#|.#.|...|.#.", "/": "..#|..#|.#.|#..|#..",
}
# fmt: on
FONT = {ch: src.split("|") for ch, src in _FONT_SRC.items()}
GLYPH_W, GLYPH_H, GLYPH_ADVANCE = 3, 5, 4


def text_width(text: str) -> int:
    return max(0, len(text) * GLYPH_ADVANCE - 1)
