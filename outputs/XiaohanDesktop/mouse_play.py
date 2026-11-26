"""Pointer play on the desktop pet.

She watches a cursor that comes near her head, lets her head follow a hand resting on it,
flattens her ears and pushes into the hand while being petted, hops round to face a cursor
that settles on her other side, and dances when the cursor circles around her. Only the pointer's current position is read, in memory, while
she is on the desktop; nothing is recorded or saved.
"""
import math

from PIL import Image, ImageOps

ART = 256
# Measured on the 256px idle paintings for each age (puppy, teen, adult); every outfit repaints
# the same dog. body: opaque bounds; centre/radius: head; ears: tips; ear: tip-to-base length.
HEADS = (
    dict(body=(60, 95, 195, 244), centre=(100, 134), radius=36, ears=((87, 96), (120, 102)), ear=14),
    dict(body=(47, 53, 209, 244), centre=(85, 98), radius=42, ears=((70, 52), (108, 60)), ear=18),
    dict(body=(36, 27, 219, 244), centre=(84, 80), radius=50, ears=((68, 27), (116, 34)), ear=24),
)
# Height of the forelegs' shoulder hinge in the same paintings, per age.
SHOULDERS = (207, 188, 185)
# Flattened ears swing their tips back towards the tail and down, as a share of ear length.
EAR_BACK = (.55, .38)
# Mesh spacing: fine around the ears, which bend sharply, and coarse over the smooth neck and tail.
FINE_GRID = 8
COARSE_GRID = 16

# Petting is either pointer travel over her head or back-and-forth strokes over her body.
HEAD_RUB_PX = 90
RUB_WINDOW = 1.2
STROKE_MIN_PX = 14
STROKE_REVERSALS = 3
STROKE_WINDOW = 1.6
PET_HOLD = 1.2
PET_EASE_IN = .3
PET_RELEASE = .6
WAG_HZ = 2.4
WAG_PX = 9.

# Head reach in art pixels; it saturates over HEAD_REACH_PX of pointer offset so a hand on her
# head moves it visibly, and fades out past GAZE_RADIUS screen pixels.
HEAD_REACH = 8.
HEAD_REACH_PX = 25.
HEAD_DOWN_LIMIT = 5.
HEAD_BACK_LIMIT = 3.
PUSH_UP = 2.5
GAZE_RADIUS = 300
GAZE_FADE = 80
EASE = .12
HAND_EARS = .45
ALERT_EARS = -.3

# Dancing: one full turn of the pointer around her middle within CIRCLE_WINDOW seconds, kept
# between CIRCLE_MIN_PX (where the angle gets jumpy) and CIRCLE_MAX_PX of her.
CIRCLE_TURNS = 1.
CIRCLE_WINDOW = 3.5
CIRCLE_MIN_PX = 40
CIRCLE_MAX_PX = 320

# She only turns for a cursor within ATTENTION_RADIUS of her head and clear of her body,
# after it has stayed on that side for FACE_SETTLE, and never twice within TURN_GAP.
ATTENTION_RADIUS = 420
FACE_SETTLE = .45
TURN_GAP = 1.2
TURN_SECONDS = .36
HOP_PX = 10.


def smooth(value):
    value = min(1., max(0., value))
    return value * value * (3 - 2 * value)


def ease(current, target, dt):
    mix = 1 - math.exp(-dt / EASE)
    return current + (target - current) * mix


class StrokeAxis:
    def __init__(self):
        self.reset()

    def reset(self):
        self.last = None
        self.direction = 0
        self.travel = 0.
        self.reversals = []

    def feed(self, value, now):
        if self.last is not None and value != self.last:
            delta = value - self.last
            sign = 1 if delta > 0 else -1
            if self.direction in (0, sign):
                self.travel += abs(delta)
            else:
                if self.travel >= STROKE_MIN_PX:
                    self.reversals.append(now)
                self.travel = abs(delta)
            self.direction = sign
        self.last = value
        self.reversals = [t for t in self.reversals if now - t <= STROKE_WINDOW]
        return len(self.reversals)


class PetDetector:
    """Recognises petting from pointer motion over her fur."""

    def __init__(self):
        self.axes = (StrokeAxis(), StrokeAxis())
        self.reset()

    def reset(self):
        for axis in self.axes:
            axis.reset()
        self.rub = []
        self.last = None

    def feed(self, x, y, now, zone):
        """zone: None off her fur, 'body' or 'head'. Returns True when the motion reads as petting."""
        if zone is None:
            self.reset()
            return False
        if zone == 'head' and self.last is not None:
            self.rub.append((now, math.dist(self.last, (x, y))))
        self.last = (x, y)
        self.rub = [(t, d) for t, d in self.rub if now - t <= RUB_WINDOW]
        counts = [axis.feed(value, now) for axis, value in zip(self.axes, (x, y))]
        if max(counts) >= STROKE_REVERSALS or sum(d for _, d in self.rub) >= HEAD_RUB_PX:
            self.reset()
            return True
        return False


class Petting:
    """How far she is leaning into a hand, easing in when petting starts and out after it stops."""

    def __init__(self):
        self.started = self.until = -1e9

    def hold(self, now, until):
        if not self.active(now):
            self.started = now
        self.until = max(self.until, until)

    def stop(self):
        self.started = self.until = -1e9

    def active(self, now):
        return now < self.until + PET_RELEASE

    def amount(self, now):
        if not self.active(now):
            return 0.
        return min(smooth((now - self.started) / PET_EASE_IN),
                   smooth((self.until + PET_RELEASE - now) / PET_RELEASE))

    def tail(self, now):
        return WAG_PX * self.amount(now) * math.sin(math.tau * WAG_HZ * (now - self.started))


def hop(t):
    """Crouch, spring and land while turning round: (lift px, x scale, y scale) for t in [0, 1)."""
    if t < .22:
        squash = math.sin(math.pi * t / .22)
        return 0., 1 + .04 * squash, 1 - .07 * squash
    if t < .78:
        air = math.sin(math.pi * (t - .22) / .56)
        return HOP_PX * air, 1 - .02 * air, 1 + .03 * air
    squash = math.sin(math.pi * (t - .78) / .22)
    return 0., 1 + .04 * squash, 1 - .06 * squash


def head_point(stage, canvas, left_facing):
    """Screen position of her head centre for a sprite canvas (left, top, scale)."""
    left, top, scale = canvas
    hx, hy = HEADS[stage]['centre']
    return left + (hx if left_facing else ART - hx) * scale, top + hy * scale


def body_centre(stage, canvas, left_facing):
    left, _, scale = canvas
    x0, _, x1, _ = HEADS[stage]['body']
    middle = (x0 + x1) / 2
    return left + (middle if left_facing else ART - middle) * scale, (x1 - x0) / 2 * scale


def body_middle(stage, canvas, left_facing):
    """Screen point at the middle of her body, the centre a dance circle is drawn around."""
    _, top, scale = canvas
    _, y0, _, y1 = HEADS[stage]['body']
    return body_centre(stage, canvas, left_facing)[0], top + (y0 + y1) / 2 * scale


class CircleGesture:
    """Counts how far the pointer has travelled around her middle; one full turn starts a dance.

    Only the stretches off her fur count, so circular rubbing on her stays petting, and a big
    circle that clips an ear just needs a little more circling. Back-and-forth arcs cancel out.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.steps = []
        self.last = None

    def feed(self, pointer, middle, now, on_fur):
        dx, dy = pointer[0] - middle[0], pointer[1] - middle[1]
        if on_fur or not CIRCLE_MIN_PX <= math.hypot(dx, dy) <= CIRCLE_MAX_PX:
            self.last = None
            return False
        angle = math.atan2(dy, dx)
        if self.last is not None:
            step = (angle - self.last + math.pi) % math.tau - math.pi
            if step:
                self.steps.append((now, step))
        self.last = angle
        self.steps = [(t, step) for t, step in self.steps if now - t <= CIRCLE_WINDOW]
        if abs(sum(step for _, step in self.steps)) >= CIRCLE_TURNS * math.tau:
            self.reset()
            return True
        return False


class Facing:
    """Which side she faces, the hop that turns her, and where her head and ears point."""

    def __init__(self):
        self.rest()

    def rest(self):
        """Actions and scenes use their own left-facing poses; start from there afterwards."""
        self.left = True
        self.pending_since = None
        self.turn_started = -1e9
        self.head = self.head_target = (0., 0.)
        self.ears = self.ears_target = 0.
        self.last = None

    def turning(self, now):
        return now - self.turn_started < TURN_SECONDS

    def update(self, now, pointer, stage, canvas, *, petting=0., follow=True):
        dt = 0. if self.last is None else min(.2, now - self.last)
        self.last = now
        if not follow:
            self.left = True
            self.pending_since = None
            self.turn_started = -1e9
        px, py = pointer
        centre, half = body_centre(stage, canvas, self.left)
        hx, hy = head_point(stage, canvas, self.left)
        reach = math.hypot(px - hx, py - hy)
        wanted = None
        if follow and not petting and abs(px - centre) > half and reach <= ATTENTION_RADIUS:
            wanted = px < centre
        if wanted is None or wanted == self.left:
            self.pending_since = None
        elif self.pending_since is None:
            self.pending_since = now
        elif now - self.pending_since >= FACE_SETTLE and now - self.turn_started >= TURN_GAP:
            self.left = wanted
            self.turn_started = now
            self.pending_since = None
            self.head = (0., 0.)
        head = (0., 0.)
        ears = petting
        if follow and not self.turning(now) and reach <= GAZE_RADIUS:
            scale = canvas[2]
            # Painting coordinates face left; mirror the offset when she faces right.
            dx = (px - hx) / scale * (1 if self.left else -1)
            dy = (py - hy) / scale
            distance = math.hypot(dx, dy)
            fade = 1 - smooth((reach - GAZE_RADIUS + GAZE_FADE) / GAZE_FADE)
            if distance:
                # Smaller heads reach proportionally less.
                size = (HEAD_REACH * HEADS[stage]['radius'] / HEADS[-1]['radius']
                        * math.tanh(distance / HEAD_REACH_PX) * fade)
                head = (min(HEAD_BACK_LIMIT, dx / distance * size), min(HEAD_DOWN_LIMIT, dy / distance * size))
            if distance <= HEADS[stage]['radius'] * 1.2:
                ears = max(petting, HAND_EARS)
            elif not petting:
                ears = ALERT_EARS * fade
        if petting:
            # Dogs push up into a petting hand.
            head = (head[0], head[1] - PUSH_UP * petting)
        self.head_target, self.ears_target = head, ears
        self.head = tuple(ease(a, b, dt) for a, b in zip(self.head, head))
        self.ears = ease(self.ears, ears, dt)

    def animating(self, now):
        return (self.turning(now) or math.dist(self.head, self.head_target) > .1
                or abs(self.ears - self.ears_target) > .02)

    def view(self, now):
        """(flip, lift, x scale, y scale) for the idle sprite at this moment."""
        turn = (now - self.turn_started) / TURN_SECONDS
        if not 0 <= turn < 1:
            return not self.left, 0., 1., 1.
        lift, x_scale, y_scale = hop(turn)
        # She swaps sides at the top of the hop.
        return (self.left if turn < .5 else not self.left), lift, x_scale, y_scale


class HeadRig:
    """Bends an idle painting so her head, ears and tail move while all four paws stay planted."""

    def __init__(self, image, stage):
        self.image = image
        geometry = HEADS[stage]
        self.centre, self.radius = geometry['centre'], geometry['radius']
        # The neck bend fades out above the forelegs' shoulder hinge so the legs never shift.
        self.shoulder = SHOULDERS[stage]
        self.ears = geometry['ears']
        self.ear = geometry['ear']
        left, top, right, bottom = image.getchannel('A').getbbox()
        self.bounds = left, top, right, bottom
        xs, ys = set(range(0, ART + 1, COARSE_GRID)), set(range(0, ART + 1, COARSE_GRID))
        for tx, ty in self.ears:
            reach = round(1.6 * self.ear)
            xs.update(range(max(0, tx - reach) // FINE_GRID * FINE_GRID, min(ART, tx + reach) + 1, FINE_GRID))
            ys.update(range(max(0, ty - FINE_GRID) // FINE_GRID * FINE_GRID, min(ART, ty + self.ear + FINE_GRID) + 1,
                            FINE_GRID))
        self.xs, self.ys = sorted(xs), sorted(ys)
        # Grid points beyond every region's reach (plus the largest push) never move; skip them.
        margin = HEAD_REACH + WAG_PX + self.ear
        self.points = [(x, y, self.head_weight(x, y), sum(self.ear_weight(x, y, tip) for tip in self.ears),
                        self.tail_weight(x, y))
                       for y in self.ys for x in self.xs if self.reached(x, y, margin)]

    def reached(self, x, y, margin):
        cx, cy = self.centre
        if math.hypot(x - cx, y - cy) < 1.9 * self.radius + margin:
            return True
        if any(abs(x - tx) < 1.6 * self.ear + margin and y < ty + self.ear + margin for tx, ty in self.ears):
            return True
        left, top, right, bottom = self.bounds
        return x > left + .63 * (right - left) - margin and y < top + .6 * (bottom - top) + margin

    def head_weight(self, x, y):
        distance = math.hypot(x - self.centre[0], y - self.centre[1])
        return ((1 - smooth((distance - .8 * self.radius) / (1.1 * self.radius)))
                * (1 - smooth((y - self.shoulder + 30) / 26)))

    def ear_weight(self, x, y, tip):
        tx, ty = tip
        across = (x - tx) / (.8 * self.ear)
        # exp(-4) is under 2%: treat the ear's influence as ending two widths out.
        if abs(across) >= 2 or y >= ty + self.ear:
            return 0.
        return smooth((ty + self.ear - y) / self.ear) * math.exp(-across * across)

    def tail_weight(self, x, y):
        left, top, right, bottom = self.bounds
        across = smooth(((x - left) / (right - left) - .63) / .24)
        if not across:
            return 0.
        return across * (1 - smooth((y - top - .3 * (bottom - top)) / (.3 * (bottom - top))))

    def displacement(self, x, y, head, ears, tail):
        dx = dy = 0.
        if head != (0., 0.):
            weight = self.head_weight(x, y)
            dx += weight * head[0]
            dy += weight * head[1]
        if ears:
            for tip in self.ears:
                weight = self.ear_weight(x, y, tip) * ears * self.ear
                dx += weight * EAR_BACK[0]
                dy += weight * EAR_BACK[1]
        if tail:
            dx += self.tail_weight(x, y) * tail
        return dx, dy

    def frame(self, head=(0., 0.), ears=0., tail=0.):
        """The bent painting; head is an art-pixel offset and ears runs from -1 (pricked) to 1 (flat)."""
        if head == (0., 0.) and not ears and not tail:
            return self.image
        sources = {}
        ear_x, ear_y = (ears * self.ear * share for share in EAR_BACK)
        for x, y, head_weight, ear_weight, tail_weight in self.points:
            # Invert the forward bend with two fixed-point steps (the first from cached weights)
            # so each part lands where it is pushed rather than where it is sampled from.
            sx = x - head_weight * head[0] - ear_weight * ear_x - tail_weight * tail
            sy = y - head_weight * head[1] - ear_weight * ear_y
            dx, dy = self.displacement(sx, sy, head, ears, tail)
            sources[x, y] = x - dx, y - dy
        mesh = []
        for y0, y1 in zip(self.ys, self.ys[1:]):
            for x0, x1 in zip(self.xs, self.xs[1:]):
                corners = ((x0, y0), (x0, y1), (x1, y1), (x1, y0))
                mesh.append(((x0, y0, x1, y1), tuple(v for c in corners for v in sources.get(c, c))))
        return self.image.transform(self.image.size, Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)


def pose_frame(rig, *, flip, head=(0., 0.), ears=0., tail=0.):
    frame = rig.frame(head, ears, tail)
    return ImageOps.mirror(frame) if flip else frame


def heart_positions(elapsed, x, top, count=5):
    """Hearts float up from her head in a staggered stream: (x, y, font size) for each."""
    hearts = []
    for index in range(count):
        t = elapsed - index * .5
        if 0 <= t < 1.4:
            drift = (-24, 10, -6, 26, -14)[index % 5] + 6 * math.sin(t * 5 + index)
            hearts.append((x + drift, top - t * 60, round(13 + 8 * math.sin(math.pi * t / 1.4))))
    return hearts
