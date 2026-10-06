import datetime
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageSequence

from contrib_miner import seasons as Z
from contrib_miner import sprites as S
from contrib_miner.fetch import Day, build_query, parse_calendar, sample_calendar, year_range
from contrib_miner.render import (
    FLOOR,
    GRID_Y,
    Scene,
    Timing,
    _merge_duplicates,
    choose_timing,
    plan,
    render_frames,
    render_gif,
)
from contrib_miner.stats import summarize


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

    def test_year_query(self):
        self.assertNotIn("$from", build_query(None))
        self.assertIn("contributionsCollection(from: $from, to: $to)", build_query(2025))
        self.assertEqual(year_range(2025), {"from": "2025-01-01T00:00:00Z", "to": "2025-12-31T23:59:59Z"})
        cal = parse_calendar(payload([]), year=2025)
        self.assertEqual(cal.year, 2025)

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
        last = render_frames(cal)[0][-2]  # the finished mine, just before the card
        self.assertEqual(last.w, 16 + len(cal.weeks) * S.TILE)
        # Stone only appears in unmined ore blocks.
        stone = {S.IDX["stone"], S.IDX["stone_dark"], S.IDX["stone_light"]}
        self.assertFalse(stone & set(last.px[GRID_Y * last.w :]))


def busy_year(seed=3):
    """A calendar with activity on every single day."""
    cal = sample_calendar("busy", seed=seed)
    cal.weeks = [[Day(d.date, 5, 1 + i % 4) if d else None for i, d in enumerate(w)] for w in cal.weeks]
    return cal


class TimingTests(unittest.TestCase):
    def test_short_years_keep_the_natural_speed(self):
        self.assertEqual(choose_timing(moves=50, mines=20, max_seconds=25), Timing())
        self.assertEqual(choose_timing(moves=5000, mines=5000, max_seconds=None), Timing())

    def test_never_faster_than_the_floor(self):
        t = choose_timing(moves=10_000, mines=10_000, max_seconds=5)
        self.assertGreaterEqual(t.step, FLOOR.step)
        self.assertGreaterEqual(t.strike, FLOOR.strike)
        for ms in (t.step, t.wind_up, t.strike):
            self.assertEqual(ms % 10, 0, "GIF delays are stored in 10 ms units")

    def test_loops_fit_the_budget(self):
        for cal, limit in ((sample_calendar("tester"), 25), (busy_year(), 26)):
            frames, durations = render_frames(cal, max_seconds=25)
            self.assertLessEqual(sum(durations) / 1000, limit)

    def test_uncapped_loop_is_longer(self):
        cal = sample_calendar("tester")
        capped = sum(render_frames(cal, max_seconds=25)[1])
        uncapped = sum(render_frames(cal, max_seconds=None)[1])
        self.assertGreater(uncapped, capped)


class StatsTests(unittest.TestCase):
    def test_summary(self):
        counts = [0, 3, 1, 0, 2, 2, 9, 0, 1]  # streaks of 2 and 3, best day 9
        levels = [0, 2, 1, 0, 2, 2, 4, 0, 1]
        days = [Day(f"2026-01-{i + 1:02d}", c, lv) for i, (c, lv) in enumerate(zip(counts, levels, strict=True))]
        cal = sample_calendar("stats")
        cal.weeks = [days[:7], days[7:] + [None] * 5]
        cal.total = sum(counts)
        stats = summarize(cal)
        self.assertEqual(stats.total, 18)
        self.assertEqual(stats.active_days, 6)
        self.assertEqual(stats.best_day, 9)
        self.assertEqual(stats.longest_streak, 3)
        self.assertEqual(stats.ores, {4: 1, 3: 0, 2: 3, 1: 2})

    def test_last_frame_is_the_card_and_holds(self):
        frames, durations = render_frames(sample_calendar("tester"))
        self.assertGreater(durations[-1], 3000)
        self.assertIn(S.IDX["tunnel"], frames[-1].px)  # the card panel


class ThemeTests(unittest.TestCase):
    def test_themes_only_recolour_known_entries(self):
        names = {name for name, _ in S.PALETTE}
        for theme, overrides in S.THEMES.items():
            self.assertLessEqual(set(overrides), names, theme)
            self.assertEqual(len(S.palette_bytes(theme)), 3 * len(S.PALETTE))

    def test_light_theme_renders_with_its_own_palette(self):
        cal = sample_calendar("tester")
        with tempfile.TemporaryDirectory() as tmp:
            out = render_gif(cal, Path(tmp) / "light.gif", scale=1, theme="light")
            first = Image.open(out).convert("RGB")
        self.assertEqual(first.getpixel((0, 0)), tuple(bytes.fromhex(S.THEMES["light"]["bg"][1:])))

    def test_unknown_theme_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(ValueError):
            render_gif(sample_calendar("tester"), Path(tmp) / "x.gif", theme="neon")


class SeasonTests(unittest.TestCase):
    def test_auto_picks_by_date(self):
        cases = {
            datetime.date(2026, 10, 14): None,
            datetime.date(2026, 10, 15): "halloween",
            datetime.date(2026, 11, 1): "halloween",
            datetime.date(2026, 11, 2): None,
            datetime.date(2026, 12, 1): "christmas",
            datetime.date(2026, 12, 26): "christmas",
            datetime.date(2026, 12, 27): None,
            datetime.date(2027, 6, 1): None,
        }
        for day, expected in cases.items():
            season = Z.resolve("auto", today=day)
            self.assertEqual(season.name if season else None, expected, day)

    def test_explicit_and_unknown_choices(self):
        self.assertIsNone(Z.resolve("none"))
        self.assertEqual(Z.resolve("christmas").name, "christmas")
        with self.assertRaises(ValueError):
            Z.resolve("easter")

    def test_seasons_cover_both_themes_with_known_colours(self):
        names = {name for name, _ in S.PALETTE}
        for season in Z.SEASONS.values():
            self.assertEqual(set(season.palette), set(S.THEMES), season.name)
            for overrides in season.palette.values():
                self.assertLessEqual(set(overrides), names, season.name)
            self.assertLessEqual(set(season.hat.values()) | {season.card_border}, names, season.name)

    def test_seasons_only_dress_the_surface(self):
        # Compare the mine background; the miner himself wears a seasonal hat.
        cal = sample_calendar("tester")
        plain = Scene(cal).base
        below = GRID_Y * plain.w
        for season in Z.SEASONS.values():
            for theme in S.THEMES:
                dressed = Scene(cal, theme, season).base
                self.assertEqual(dressed.px[below:], plain.px[below:], f"{season.name}/{theme} changed the mine")

    def test_seasonal_gif_decodes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for season in Z.SEASONS.values():
                out = render_gif(sample_calendar("tester"), Path(tmp) / f"{season.name}.gif", scale=1, season=season)
                bg = Image.open(out).convert("RGB").getpixel((0, 0))
                self.assertEqual(bg, tuple(bytes.fromhex(season.palette["dark"]["bg"][1:])))


if __name__ == "__main__":
    unittest.main()
