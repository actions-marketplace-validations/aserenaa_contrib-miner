import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageSequence

from contrib_miner import sprites as S
from contrib_miner.fetch import parse_calendar, sample_calendar
from contrib_miner.render import GRID_Y, _merge_duplicates, plan, render_frames, render_gif


def payload(days_per_week):
    return {
        "data": {
            "user": {
                "login": "octo",
                "contributionsCollection": {
                    "contributionCalendar": {
                        "totalContributions": 9,
                        "weeks": [{"contributionDays": w} for w in days_per_week],
                    }
                },
            }
        }
    }


class ParseTests(unittest.TestCase):
    def test_days_are_placed_by_weekday(self):
        cal = parse_calendar(
            payload(
                [
                    [
                        {
                            "date": "2026-10-03",
                            "weekday": 6,
                            "contributionCount": 9,
                            "contributionLevel": "FOURTH_QUARTILE",
                        }
                    ],
                ]
            )
        )
        self.assertEqual(cal.login, "octo")
        self.assertEqual(cal.total, 9)
        self.assertEqual(cal.weeks[0][:6], [None] * 6)
        self.assertEqual(cal.weeks[0][6].level, 4)

    def test_graphql_errors_raise(self):
        with self.assertRaisesRegex(RuntimeError, "bad login"):
            parse_calendar({"errors": [{"message": "bad login"}]})

    def test_missing_user_raises(self):
        with self.assertRaisesRegex(RuntimeError, "not found"):
            parse_calendar({"data": {"user": None}})


class SpriteTests(unittest.TestCase):
    def test_palette_fits_in_gif(self):
        self.assertLessEqual(len(S.PALETTE), 256)

    def test_sprite_shapes(self):
        for tile in (S.DIRT, S.STONE, S.ORE_MASK):
            self.assertEqual([len(r) for r in tile], [S.TILE] * S.TILE)
        for tile in (S.PATH, S.MINED):
            self.assertEqual([len(r) for r in tile], [S.TILE] * S.TILE)
        for pose in (S.MINER_UP, S.MINER_STEP, S.MINER_DOWN):
            # The miner fits in one tunnel row; two extra columns reach into the next tile.
            self.assertEqual([len(r) for r in pose], [S.TILE + 2] * S.TILE)


class PlanTests(unittest.TestCase):
    def walk(self, cal):
        """Replay the plan, checking every rule, and return the mined cells."""
        ores = {(c, r) for c, week in enumerate(cal.weeks) for r, day in enumerate(week) if day and day.level > 0}
        mined = set()
        steps = plan(cal)
        self.assertEqual((steps[0].kind, steps[0].col, steps[0].row), ("enter", -1, 0))
        col, row = -1, 0
        for step in steps[1:]:
            if step.kind == "move":
                self.assertEqual(abs(step.col - col) + abs(step.row - row), 1, "moves one cell at a time")
                self.assertTrue(0 <= step.row < 7)
                self.assertFalse((step.col, step.row) in ores - mined, "never walks into unmined ore")
                col, row = step.col, step.row
            else:
                self.assertEqual(step.kind, "mine")
                self.assertEqual((step.col - 1, step.row), (col, row), "mines from the left-hand side")
                self.assertIn((step.col, step.row), ores - mined)
                mined.add((step.col, step.row))
        return ores, mined

    def test_sample_route_mines_every_ore_from_the_side(self):
        ores, mined = self.walk(sample_calendar("tester"))
        self.assertEqual(mined, ores)

    def test_dense_and_empty_calendars(self):
        for seed in range(5):
            cal = sample_calendar("dense", seed=seed)
            ores, mined = self.walk(cal)
            self.assertEqual(mined, ores)
        empty = sample_calendar("empty")
        empty.weeks = [[None] * 7 for _ in empty.weeks]
        ores, mined = self.walk(empty)
        self.assertEqual(ores, set())
        self.assertEqual(mined, set())


class RenderTests(unittest.TestCase):
    def test_gif_decodes_to_rendered_frames(self):
        cal = sample_calendar("tester")
        frames, durations = _merge_duplicates(*render_frames(cal))
        with tempfile.TemporaryDirectory() as tmp:
            out = render_gif(cal, Path(tmp) / "out.gif", scale=1)
            # Pillow reuses one Image object while iterating, so copy each frame out.
            decoded = [
                (f.convert("RGB").tobytes(), f.info["duration"]) for f in ImageSequence.Iterator(Image.open(out))
            ]
        self.assertEqual(len(decoded), len(frames))
        for i, ((got, ms), want) in enumerate(zip(decoded, frames, strict=True)):
            self.assertEqual(got, want.to_image(1).convert("RGB").tobytes(), f"frame {i}")
            self.assertEqual(ms, durations[i], f"frame {i} duration")

    def test_every_ore_is_dug_by_the_last_frame(self):
        cal = sample_calendar("tester")
        last = render_frames(cal)[0][-1]
        self.assertEqual(last.w, 16 + len(cal.weeks) * S.TILE)
        # Stone only appears in unmined ore blocks.
        stone = {S.IDX["stone"], S.IDX["stone_dark"], S.IDX["stone_light"]}
        self.assertFalse(stone & set(last.px[GRID_Y * last.w :]))


if __name__ == "__main__":
    unittest.main()
