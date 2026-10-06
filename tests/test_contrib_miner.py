import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageSequence

from contrib_miner import sprites as S
from contrib_miner.fetch import parse_calendar, sample_calendar
from contrib_miner.render import _merge_duplicates, render_frames, render_gif


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
        for tile in (S.DIRT, S.STONE, S.ORE_MASK, S.TUNNEL):
            self.assertEqual([len(r) for r in tile], [S.TILE] * S.TILE)
        for pose in (S.MINER_UP, S.MINER_DOWN):
            self.assertEqual(len({len(r) for r in pose}), 1)


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
        ore_colours = {S.IDX[c] for pair in S.ORES.values() for c in pair}
        grid_top = 26
        self.assertFalse(ore_colours & set(last.px[grid_top * last.w :]))


if __name__ == "__main__":
    unittest.main()
