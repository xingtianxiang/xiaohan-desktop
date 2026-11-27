"""Rules for the four arcade games: catching treats, the cup shuffle, the hurdle run and paw memory.

Only rules live here, in window pixels of GAME_SIZE, so every game can be played headless in tests.
Each game starts in 'ready', runs in 'playing' and stops in 'over'; score is what the best record keeps.
"""
import math
import random

GAME_SIZE = (420, 330)


def smooth(t):
    t = min(1., max(0., t))
    return t * t * (3 - 2 * t)


class MiniGame:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.phase = 'ready'
        self.score = 0
        self.elapsed = 0.

    @property
    def over(self):
        return self.phase == 'over'

    def start(self):
        if self.phase == 'ready':
            self.phase = 'playing'

    def advance(self, dt, pointer=None):
        if self.phase != 'playing':
            return
        self.elapsed += dt
        self.step(dt, pointer)

    def step(self, dt, pointer):
        raise NotImplementedError

    def press(self, x=None, y=None):
        self.start()

    def release(self):
        pass


class Falling:
    VALUES = {'biscuit': 1, 'bone': 3, 'chocolate': 0, 'grapes': 0}

    def __init__(self, kind, x, speed, spin):
        self.kind, self.x, self.y, self.speed, self.spin = kind, x, -24., speed, spin

    @property
    def good(self):
        return self.VALUES[self.kind] > 0


class CatchGame(MiniGame):
    """She runs along the floor after the cursor; treats score, chocolate and grapes cost a heart."""
    FLOOR = 300
    LIVES = 3
    DOG_SPEED = 560.
    LANE = (36, GAME_SIZE[0] - 36)
    CATCH_HALF = 34

    def __init__(self, catch_height, mouth_offset, rng=None):
        super().__init__(rng)
        # Mouth height above the floor and its sideways offset towards the way she faces.
        self.catch_y = self.FLOOR - catch_height
        self.mouth_offset = mouth_offset
        self.x = GAME_SIZE[0] / 2
        self.facing_right = False
        self.moving = False
        self.lives = self.LIVES
        self.combo = 0
        self.items = []
        self.next_spawn = .6
        self.pops = []
        self.hurt_until = -1.

    @staticmethod
    def fall_speed(t):
        return min(470., 150. + 8.5 * t)

    @staticmethod
    def spawn_gap(t):
        return max(.34, .95 - .017 * t)

    @staticmethod
    def bad_chance(t):
        return min(.45, .2 + .0055 * t)

    @property
    def mouth_x(self):
        return self.x + (self.mouth_offset if self.facing_right else -self.mouth_offset)

    def spawn(self):
        t = self.elapsed
        if self.rng.random() < self.bad_chance(t):
            kind = self.rng.choice(('chocolate', 'grapes'))
        else:
            kind = 'bone' if self.rng.random() < .15 else 'biscuit'
        x = self.rng.uniform(30, GAME_SIZE[0] - 30)
        self.items.append(Falling(kind, x, self.fall_speed(t) * self.rng.uniform(.88, 1.12), self.rng.uniform(-90, 90)))

    def step(self, dt, pointer):
        if pointer is not None:
            target = min(self.LANE[1], max(self.LANE[0], pointer[0]))
            move = max(-self.DOG_SPEED * dt, min(self.DOG_SPEED * dt, target - self.x))
            self.moving = abs(move) > .5
            if self.moving:
                self.facing_right = move > 0
            self.x += move
        self.next_spawn -= dt
        while self.next_spawn <= 0:
            self.spawn()
            if self.elapsed > 35 and self.rng.random() < .3:
                self.spawn()
            self.next_spawn += self.spawn_gap(self.elapsed) * self.rng.uniform(.8, 1.2)
        kept = []
        for item in self.items:
            before = item.y
            item.y += item.speed * dt
            if before < self.catch_y <= item.y and abs(item.x - self.mouth_x) <= self.CATCH_HALF:
                self.eat(item)
            elif item.y < self.FLOOR + 30:
                kept.append(item)
            elif item.good:
                self.combo = 0
        self.items = kept
        self.pops = [pop for pop in self.pops if self.elapsed - pop[3] < .8]

    def eat(self, item):
        if item.good:
            self.score += Falling.VALUES[item.kind]
            self.combo += 1
            self.pops.append((item.x, self.catch_y, f'+{Falling.VALUES[item.kind]}', self.elapsed))
            return
        self.lives -= 1
        self.combo = 0
        self.hurt_until = self.elapsed + .8
        self.pops.append((item.x, self.catch_y, '-1 ♥', self.elapsed))
        if self.lives <= 0:
            self.phase = 'over'


class ShellGame(MiniGame):
    """She hides the ball under a cup; the cups swap faster each round and a wrong pick ends the game."""
    BASE = 262
    CUP_SIZE = (70, 66)
    SHOW = (.3, .7, .3)
    REVEAL = 1.1

    def __init__(self, rng=None):
        super().__init__(rng)
        self.round = 0
        self.cups = 0
        self.slot_of = []
        self.ball = 0
        self.stage = 'idle'
        self.timer = 0.
        self.moves = []
        self.move_time = 0.
        self.picked = None
        self.correct = None

    @staticmethod
    def cup_count(round_number):
        return 3 if round_number < 5 else 4

    @staticmethod
    def swap_count(round_number):
        return min(18, 4 + 2 * (round_number - 1))

    @staticmethod
    def swap_seconds(round_number):
        return max(.17, .5 * .88 ** (round_number - 1))

    def slot_x(self, slot):
        left, right = (100, 320) if self.cups == 3 else (75, 345)
        return left + (right - left) * slot / (self.cups - 1)

    def start(self):
        if self.phase == 'ready':
            self.phase = 'playing'
            self.next_round()

    def next_round(self):
        self.round += 1
        cups = self.cup_count(self.round)
        if cups != self.cups:
            self.cups = cups
            self.slot_of = list(range(cups))
        self.ball = self.rng.randrange(self.cups)
        self.picked = self.correct = None
        self.moves = []
        for _ in range(self.swap_count(self.round)):
            first, second = self.rng.sample(range(self.cups), 2)
            pairs = [(first, second)]
            if self.cups == 4 and self.round >= 7 and self.rng.random() < .4:
                pairs.append(tuple(c for c in range(4) if c not in (first, second)))
            self.moves.append(pairs)
        self.stage, self.timer = 'show', 0.
        self.move_time = self.swap_seconds(self.round)

    def cup_position(self, cup):
        """Cup centre x, lift above the ground and depth (-1 behind, 1 in front) for drawing and clicks."""
        x = self.slot_x(self.slot_of[cup])
        lift, depth = 0., 0.
        if self.stage == 'show' and cup == self.ball:
            up, hold, down = self.SHOW
            lift = 46 * (smooth(self.timer / up) if self.timer < up + hold else 1 - smooth((self.timer - up - hold) / down))
        elif self.stage == 'shuffle' and self.moves:
            progress = self.timer / self.move_time
            for index, (a, b) in enumerate(self.moves[0]):
                if cup in (a, b):
                    other = b if cup == a else a
                    start, end = self.slot_x(self.slot_of[cup]), self.slot_x(self.slot_of[other])
                    x = start + (end - start) * smooth(progress)
                    direction = 1 if (cup == a) == (index % 2 == 0) else -1
                    depth = direction * math.sin(math.pi * min(1., progress))
        elif self.stage in ('reveal', 'missed') and cup in (self.picked, self.ball):
            lift = 46 * smooth(self.timer / .3)
        return x, lift, depth

    def step(self, dt, pointer):
        self.timer += dt
        if self.stage == 'show' and self.timer >= sum(self.SHOW):
            self.stage, self.timer = 'shuffle', 0.
        elif self.stage == 'shuffle':
            while self.moves and self.timer >= self.move_time:
                for a, b in self.moves.pop(0):
                    self.slot_of[a], self.slot_of[b] = self.slot_of[b], self.slot_of[a]
                self.timer -= self.move_time
            if not self.moves:
                self.stage, self.timer = 'choose', 0.
        elif self.stage == 'reveal' and self.timer >= self.REVEAL:
            self.next_round()
        elif self.stage == 'missed' and self.timer >= self.REVEAL:
            self.phase = 'over'

    def cup_at(self, x, y):
        width, height = self.CUP_SIZE
        for cup in range(self.cups):
            cx, _, _ = self.cup_position(cup)
            if abs(x - cx) <= width / 2 and self.BASE - height <= y <= self.BASE:
                return cup
        return None

    def press(self, x=None, y=None):
        if self.phase == 'ready':
            self.start()
            return
        if self.phase != 'playing' or self.stage != 'choose' or x is None:
            return
        cup = self.cup_at(x, y)
        if cup is None:
            return
        self.picked = cup
        self.correct = cup == self.ball
        if self.correct:
            self.score += 1
        self.stage, self.timer = ('reveal' if self.correct else 'missed'), 0.


class Hurdle:
    WIDTH = 14
    # A tap peaks near 60px: clear over the low bar, short of the high one, which needs a held jump.
    HEIGHTS = {'low': 30, 'high': 64}

    def __init__(self, kind, x):
        self.kind, self.x = kind, x

    @property
    def height(self):
        return self.HEIGHTS[self.kind]


class HurdleGame(MiniGame):
    """She runs right ever faster; a tap clears low hurdles, holding longer clears the high ones."""
    GROUND = 292
    RUN_X = 118
    JUMP_SPEED = 560.
    HOLD_GRAVITY = 1250.
    FALL_GRAVITY = 2600.
    HOLD_LIMIT = .26
    PIXELS_PER_METRE = 40.

    def __init__(self, half_width, rng=None):
        super().__init__(rng)
        # Half the width of her paws' footprint; she clips a hurdle while her feet are below its bar.
        self.half_width = half_width
        self.height = 0.
        self.rise = 0.
        self.holding = False
        self.hold_time = 0.
        self.distance = 0.
        self.hurdles = []
        self.next_gap = 260.
        self.crashed = None

    @staticmethod
    def speed(t):
        return min(560., 230. + 7.5 * t)

    @property
    def airborne(self):
        return self.height > 0 or self.rise > 0

    def press(self, x=None, y=None):
        if self.phase == 'ready':
            self.start()
            return
        if self.phase == 'playing' and not self.airborne:
            self.rise = self.JUMP_SPEED
            self.holding = True
            self.hold_time = 0.

    def release(self):
        self.holding = False

    def step(self, dt, pointer):
        speed = self.speed(self.elapsed)
        self.distance += speed * dt
        self.score = int(self.distance / self.PIXELS_PER_METRE)
        if self.airborne:
            self.hold_time += dt
            held = self.holding and self.rise > 0 and self.hold_time < self.HOLD_LIMIT
            self.rise -= (self.HOLD_GRAVITY if held else self.FALL_GRAVITY) * dt
            self.height += self.rise * dt
            if self.height <= 0:
                self.height = self.rise = 0.
        for hurdle in self.hurdles:
            hurdle.x -= speed * dt
        self.hurdles = [h for h in self.hurdles if h.x > -40]
        last = self.hurdles[-1].x if self.hurdles else -1e9
        if GAME_SIZE[0] + 30 - last >= self.next_gap:
            self.add_hurdles(speed)
        for hurdle in self.hurdles:
            overlap = abs(hurdle.x - self.RUN_X) <= self.half_width + Hurdle.WIDTH / 2
            if overlap and self.height < hurdle.height:
                self.crashed = hurdle
                self.phase = 'over'
                return

    def add_hurdles(self, speed):
        x = GAME_SIZE[0] + 30
        if self.elapsed > 20 and self.rng.random() < .25:
            self.hurdles += [Hurdle('low', x), Hurdle('low', x + .32 * speed)]
        else:
            self.hurdles.append(Hurdle('high' if self.rng.random() < min(.5, .15 + .012 * self.elapsed) else 'low', x))
        # At least about a second between landings, so every hurdle can be read and jumped.
        self.next_gap = max(220., speed * self.rng.uniform(.95, 1.7))


class MemoryGame(MiniGame):
    """Paw prints light up in order; repeat them. Each round adds a step and plays it faster."""
    PADS = 4
    CENTRES = ((84, 248), (168, 248), (252, 248), (336, 248))
    RADIUS = 36
    START_LENGTH = 3
    INPUT_LIMIT = 4.
    PRESS_LIGHT = .2

    def __init__(self, rng=None):
        super().__init__(rng)
        self.sequence = []
        self.round = 0
        self.stage = 'idle'
        self.timer = 0.
        self.entered = 0
        self.pressed = None
        self.wrong = None

    @staticmethod
    def flash_seconds(round_number):
        return max(.22, .55 * .92 ** (round_number - 1))

    @staticmethod
    def gap_seconds(round_number):
        return max(.08, .25 * .92 ** (round_number - 1))

    def start(self):
        if self.phase == 'ready':
            self.phase = 'playing'
            self.sequence = [self.rng.randrange(self.PADS) for _ in range(self.START_LENGTH - 1)]
            self.next_round()

    def next_round(self):
        self.round += 1
        self.sequence.append(self.rng.randrange(self.PADS))
        self.stage, self.timer, self.entered = 'watch', -.5, 0

    @property
    def lit(self):
        """The pad shown lit right now, or None."""
        if self.stage == 'watch' and self.timer >= 0:
            flash, gap = self.flash_seconds(self.round), self.gap_seconds(self.round)
            index, offset = divmod(self.timer, flash + gap)
            if index < len(self.sequence) and offset < flash:
                return self.sequence[int(index)]
        if self.stage in ('repeat', 'good') and self.pressed is not None and self.pressed[1] > self.elapsed:
            return self.pressed[0]
        if self.stage == 'wrong':
            return self.sequence[self.entered] if int(self.timer * 4) % 2 == 0 else None
        return None

    def step(self, dt, pointer):
        self.timer += dt
        flash, gap = self.flash_seconds(self.round), self.gap_seconds(self.round)
        if self.stage == 'watch' and self.timer >= len(self.sequence) * (flash + gap):
            self.stage, self.timer = 'repeat', 0.
        elif self.stage == 'repeat' and self.timer >= self.INPUT_LIMIT:
            self.wrong = 'slow'
            self.stage, self.timer = 'wrong', 0.
        elif self.stage == 'good' and self.timer >= .6:
            self.next_round()
        elif self.stage == 'wrong' and self.timer >= 1.2:
            self.phase = 'over'

    def pad_at(self, x, y):
        for pad, (cx, cy) in enumerate(self.CENTRES):
            if math.hypot(x - cx, y - cy) <= self.RADIUS:
                return pad
        return None

    def press(self, x=None, y=None):
        if self.phase == 'ready':
            self.start()
            return
        if self.phase != 'playing' or self.stage != 'repeat' or x is None:
            return
        pad = self.pad_at(x, y)
        if pad is None:
            return
        self.pressed = (pad, self.elapsed + self.PRESS_LIGHT)
        if pad != self.sequence[self.entered]:
            self.wrong = pad
            self.stage, self.timer = 'wrong', 0.
            return
        self.entered += 1
        self.timer = 0.
        if self.entered == len(self.sequence):
            self.score = self.round
            self.stage, self.timer = 'good', 0.
