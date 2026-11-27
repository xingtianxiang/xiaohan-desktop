import random
import unittest

from minigames import CatchGame, Falling, Hurdle, HurdleGame, MemoryGame, ShellGame

DT = 1 / 120


def run(game, seconds, pointer=None):
    for _ in range(round(seconds / DT)):
        game.advance(DT, pointer)


class CatchTests(unittest.TestCase):
    def game(self):
        game = CatchGame(catch_height=80, mouth_offset=20, rng=random.Random(1))
        game.press()
        game.next_spawn = 1e9
        return game

    def drop(self, game, kind, x):
        item = Falling(kind, x, 300., 0.)
        item.y = game.catch_y - 30
        game.items.append(item)

    def test_gets_harder_and_levels_off(self):
        self.assertLess(CatchGame.fall_speed(0), CatchGame.fall_speed(30))
        self.assertEqual(CatchGame.fall_speed(500), 470)
        self.assertGreater(CatchGame.spawn_gap(0), CatchGame.spawn_gap(30))
        self.assertEqual(CatchGame.spawn_gap(500), .34)
        self.assertLess(CatchGame.bad_chance(0), CatchGame.bad_chance(30))
        self.assertEqual(CatchGame.bad_chance(500), .45)

    def test_she_runs_after_the_cursor_at_a_limited_speed(self):
        game = self.game()
        game.advance(.1, (400, 0))
        self.assertAlmostEqual(game.x, 210 + CatchGame.DOG_SPEED * .1)
        self.assertTrue(game.facing_right and game.moving)
        run(game, 1, (0, 0))
        self.assertEqual(game.x, CatchGame.LANE[0])
        self.assertFalse(game.facing_right)

    def test_treats_score_and_bad_food_costs_hearts(self):
        game = self.game()
        mouth = game.mouth_x
        self.drop(game, 'biscuit', mouth)
        run(game, .2, (game.x, 0))
        self.drop(game, 'bone', mouth)
        run(game, .2, (game.x, 0))
        self.assertEqual((game.score, game.combo), (4, 2))
        for kind in ('chocolate', 'grapes', 'chocolate'):
            self.drop(game, kind, mouth)
            run(game, .2, (game.x, 0))
        self.assertEqual((game.lives, game.phase, game.combo), (0, 'over', 0))

    def test_a_missed_treat_breaks_the_combo(self):
        game = self.game()
        self.drop(game, 'biscuit', game.mouth_x)
        run(game, .2, (game.x, 0))
        self.drop(game, 'biscuit', game.mouth_x + 120)
        run(game, 1, (game.x, 0))
        self.assertEqual((game.score, game.combo, game.items), (1, 0, []))

    def test_items_keep_coming(self):
        game = CatchGame(80, 20, rng=random.Random(4))
        game.press()
        run(game, 10, (0, 0))
        self.assertTrue(game.items)


class ShellTests(unittest.TestCase):
    def finish_shuffle(self, game):
        while game.stage in ('show', 'shuffle'):
            game.advance(DT)

    def ball_point(self, game):
        x, _, _ = game.cup_position(game.ball)
        return x, ShellGame.BASE - 20

    def test_rounds_get_faster_longer_and_wider(self):
        self.assertEqual((ShellGame.cup_count(4), ShellGame.cup_count(5)), (3, 4))
        self.assertLess(ShellGame.swap_count(1), ShellGame.swap_count(5))
        self.assertGreater(ShellGame.swap_seconds(1), ShellGame.swap_seconds(5))
        self.assertEqual(ShellGame.swap_seconds(40), .17)

    def test_the_ball_stays_under_its_cup_through_the_shuffle(self):
        game = ShellGame(random.Random(3))
        game.press()
        for round_number in range(1, 9):
            self.assertEqual(game.round, round_number)
            self.finish_shuffle(game)
            self.assertEqual(game.stage, 'choose')
            self.assertEqual(game.cup_at(*self.ball_point(game)), game.ball)
            game.press(*self.ball_point(game))
            self.assertEqual((game.score, game.stage), (round_number, 'reveal'))
            run(game, ShellGame.REVEAL + .05)
        self.assertEqual(game.cups, 4)

    def test_clicks_during_the_shuffle_are_ignored(self):
        game = ShellGame(random.Random(5))
        game.press()
        game.advance(.5)
        game.press(*self.ball_point(game))
        self.assertIsNone(game.picked)

    def test_a_wrong_cup_ends_the_game_after_showing_the_ball(self):
        game = ShellGame(random.Random(7))
        game.press()
        self.finish_shuffle(game)
        wrong = next(c for c in range(game.cups) if c != game.ball)
        game.press(game.cup_position(wrong)[0], ShellGame.BASE - 20)
        self.assertEqual((game.stage, game.score), ('missed', 0))
        run(game, .4)
        self.assertGreater(game.cup_position(game.ball)[1], 40)
        run(game, ShellGame.REVEAL)
        self.assertTrue(game.over)


class HurdleTests(unittest.TestCase):
    def game(self):
        game = HurdleGame(half_width=16, rng=random.Random(2))
        game.press()
        game.next_gap = float('inf')
        return game

    def peak(self, hold):
        game = self.game()
        game.press()
        if not hold:
            game.release()
        best = 0.
        while game.airborne or best == 0:
            game.advance(DT)
            best = max(best, game.height)
        return best

    def test_a_tap_clears_low_bars_and_only_a_hold_clears_high_bars(self):
        tap, hold = self.peak(False), self.peak(True)
        self.assertTrue(Hurdle.HEIGHTS['low'] < tap < Hurdle.HEIGHTS['high'], tap)
        self.assertGreater(hold, Hurdle.HEIGHTS['high'] + 20)

    def test_running_into_a_bar_ends_the_run(self):
        game = self.game()
        game.hurdles = [Hurdle('low', HurdleGame.RUN_X + 60)]
        run(game, 1)
        self.assertTrue(game.over)
        self.assertIs(game.crashed, game.hurdles[0])

    def test_a_timed_tap_jumps_a_low_bar(self):
        game = self.game()
        bar = Hurdle('low', HurdleGame.RUN_X + 120)
        game.hurdles = [bar]
        # Tap about a tenth of a second before the bar reaches her paws.
        while bar.x - HurdleGame.RUN_X > game.half_width + Hurdle.WIDTH / 2 + .11 * HurdleGame.speed(game.elapsed):
            game.advance(DT)
        game.press()
        game.release()
        run(game, 1)
        self.assertFalse(game.over)
        self.assertGreater(game.score, 0)

    def test_speed_rises_and_bars_stay_a_second_apart(self):
        self.assertEqual(HurdleGame.speed(0), 230)
        self.assertEqual(HurdleGame.speed(500), 560)
        game = HurdleGame(16, rng=random.Random(8))
        game.press()
        gaps = []
        for _ in range(round(60 / DT)):
            before = list(game.hurdles)
            game.height, game.rise = 1e9, 0.  # float over every bar to watch the spacing
            game.advance(DT)
            new = [h for h in game.hurdles if h not in before]
            if new and before:
                gaps.append((new[0].x - before[-1].x, HurdleGame.speed(game.elapsed)))
        self.assertGreater(len(gaps), 20)
        for gap, speed in gaps:
            self.assertGreaterEqual(gap, min(220., .95 * speed) - 10)


class MemoryTests(unittest.TestCase):
    def repeat(self, game, pads):
        for pad in pads:
            game.press(*MemoryGame.CENTRES[pad])
            game.advance(.05)

    def test_a_correct_repeat_adds_a_step_and_speeds_up(self):
        game = MemoryGame(random.Random(9))
        game.press()
        self.assertEqual(len(game.sequence), MemoryGame.START_LENGTH)
        while game.stage == 'watch':
            game.advance(DT)
        self.repeat(game, game.sequence)
        self.assertEqual((game.stage, game.score), ('good', 1))
        run(game, .7)
        self.assertEqual((game.round, len(game.sequence), game.stage), (2, 4, 'watch'))
        self.assertLess(MemoryGame.flash_seconds(2), MemoryGame.flash_seconds(1))
        self.assertEqual(MemoryGame.flash_seconds(60), .22)

    def test_the_sequence_is_shown_in_order(self):
        game = MemoryGame(random.Random(11))
        game.press()
        flashes = []
        last = None
        while game.stage == 'watch':
            game.advance(DT)
            if game.lit != last and game.lit is not None:
                flashes.append(game.lit)
            last = game.lit
        self.assertEqual(flashes, game.sequence)

    def test_a_wrong_pad_or_waiting_too_long_ends_the_game(self):
        game = MemoryGame(random.Random(12))
        game.press()
        while game.stage == 'watch':
            game.advance(DT)
        wrong = (game.sequence[0] + 1) % MemoryGame.PADS
        game.press(*MemoryGame.CENTRES[wrong])
        self.assertEqual(game.stage, 'wrong')
        run(game, 1.3)
        self.assertTrue(game.over)
        slow = MemoryGame(random.Random(12))
        slow.press()
        run(slow, 30)
        self.assertEqual((slow.over, slow.wrong), (True, 'slow'))


if __name__ == '__main__':
    unittest.main()
