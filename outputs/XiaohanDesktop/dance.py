"""Four-paw choreography on a shared beat grid for motion and stage cues."""
from bisect import bisect_right
from functools import lru_cache
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from fetch_game import ramp
from model import DANCE_SECONDS

BPM = 130
SECONDS_PER_BEAT = 60 / BPM
CAT_ENTRANCE = 7.65
ACCENTS = (0, 2, 4, 6, 8, 10.5, 12, 14, 16)

# Measured against the original 256px paintings shared by each age's outfits.
FORELEGS = ((86, 207, 107, 103), (75, 188, 96, 89), (65, 185, 90, 79))
CAT_FORELEG = (48, 183, 68, 63)
ANKLES = ((86, 119, 146, 183), (73, 104, 155, 194), (63, 98, 151, 203))
CAT_ANKLES = (35, 85, 133, 188)
FLAT = ((0., 0.),) * 4

# Beat, head lead, head drop, gesture angle, and delayed tail sweep.
DOG_KEYS = (
    (0, -3, 5, 0, 0), (.65, 5, -6, 0, -3), (1.35, 10, 6, 0, 6),
    (2, 15, -8, 0, 9), (2.6, -15, 2, 0, 6), (3.3, -10, 10, 0, -10),
    (4, 2, -4, 0, -8), (4.85, 13, 16, 0, -6), (5.35, 5, 13, 8, 1),
    (6, -17, -17, 88, 7), (6.46, -16, -14, 79, 12),
    (7.34, 4, 12, 0, 5), (8, 11, -4, 0, -7), (9, 21, 4, 0, 6),
    (9.9, 13, -1, 0, 12), (10.5, -12, 17, 0, 4), (11.25, -13, 2, 0, -6),
    (12, 7, -10, 0, -10), (12.8, 16, 8, 0, 3), (13.3, 1, 13, 6, 6),
    (14, -14, -13, 74, 9), (14.45, -11, -10, 70, 13),
    (15.34, 6, 18, 0, -8), (16, -9, 7, 0, -6), (17.34, -8, 2, 0, 0),
)
CAT_KEYS = (
    (CAT_ENTRANCE, -11, -4, 0, 9), (8.5, -17, 5, 0, -8), (9.4, 2, -7, 0, 11),
    (10.5, 8, 11, 0, -9), (11.1, -8, -13, 48, -13),
    (11.42, -8, -6, 46, -9), (12.1, 7, 10, 0, 11),
    (12.8, 10, -1, 0, 13), (13.3, 3, 12, 2, 3),
    (14, -13, -12, 66, -11), (14.45, -9, -7, 60, -16),
    (15.34, 6, 14, 0, 9), (16, -8, 6, 0, 10), (17.34, -7, 2, 0, 0),
)
DOG_TIMES = tuple(key[0] for key in DOG_KEYS)
CAT_TIMES = tuple(key[0] for key in CAT_KEYS)


def body_at(beat, keys, times):
    index = min(len(keys) - 2, max(0, bisect_right(times, beat) - 1))
    start, end = keys[index:index+2]
    mix = ramp(beat, start[0], end[0])
    return tuple(a + (b - a) * mix for a, b in zip(start[1:], end[1:]))


def footwork(beat, origin, transfers):
    """Move one diagonal pair at a time, holding the other pair at its contacts."""
    feet = [(origin, 0.)] * 4
    for start, finish, distance, height, crossed in transfers:
        duration = finish - start
        for index in range(4):
            half = duration / 2
            delay = half if (index in (0, 3)) == crossed else 0.
            phase = min(1., max(0., (beat - start - delay) / half))
            x, y = feet[index]
            arc = math.sin(math.pi * phase)**2
            feet[index] = (x + distance * ramp(phase, 0, 1), y + height * arc)
    root = sum(x for x, _ in feet) / 4
    return root, tuple((x - root, y) for x, y in feet)


DOG_TRANSFERS = (
    (.3, 1.85, 15, 15, True),
    (2, 3.78, -27, 23, False),
    (7.38, 8.75, -22, 18, True),
    (8.84, 10.1, -18, 17, False),
    (11.12, 12.74, 11, 17, True),
)
CAT_TRANSFERS = (
    (7.65, 8.69, -39, 20, False),
    (8.70, 9.75, -38, 23, True),
    (9.76, 10.8, -36, 18, False),
    (12.12, 13.3, 7, 13, True),
)


class DancePose:
    def __init__(self, standing, foreleg, ankles):
        self.standing = standing
        alpha = standing.getchannel('A')
        self.bounds = alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
        x, y, upper_cut, ankle_cut = foreleg
        self.hinge = x, y
        mask = Image.new('L', standing.size)
        paint = ImageDraw.Draw(mask)
        for row in range(y - 7, standing.height):
            split = round(upper_cut + (ankle_cut - upper_cut) * ramp(row, y + 19, 235))
            paint.line((0, row, split, row), fill=round(255 * ramp(row, y - 7, y + 5)))
        self.body = standing.copy()
        self.body.putalpha(ImageChops.multiply(alpha, ImageChops.invert(mask)))
        self.leg = standing.copy()
        self.leg.putalpha(ImageChops.multiply(alpha, mask))
        self.x_grid = tuple(sorted(set(range(0, standing.width, 12)) | {standing.width, *ankles}))
        self.y_grid = (*range(0, standing.height, 12), standing.height)
        left, top, right, bottom = self.bounds
        self.head_weights = tuple(self.head_weight(x) for x in self.x_grid)
        self.tail_weights = tuple(ramp((x - left) / (right - left), .63, .87) for x in self.x_grid)
        self.ankles = (0, *ankles, standing.width)
        self.height_weights = []
        for row in self.y_grid:
            upper = 1 - ramp(row, top + .42 * (bottom - top), y - 8)
            foot = ramp(row, y - 4, bottom - 24)
            self.height_weights.append((upper, foot))

    def head_weight(self, x):
        left, _, right, _ = self.bounds
        return 1 - ramp((x - left) / (right - left), .35, .66)

    def pose(self, lean, dip, paw, *, tail=0., feet=FLAT):
        only_body = paw > 0
        source = self.body if only_body else self.standing
        contacts = ((0., feet[0][1]), *feet, (0., feet[-1][1]))
        rows = []
        for y, (upper, foot) in zip(self.y_grid, self.height_weights):
            # Invert ordered landing points so lifting a paw cannot duplicate it.
            landings = tuple(x + foot * step for x, (step, _) in zip(self.ankles, contacts))
            row = []
            for x, head, curl in zip(self.x_grid, self.head_weights, self.tail_weights):
                segment = min(4, bisect_right(landings, x) - 1)
                weight = (x - landings[segment]) / (landings[segment+1] - landings[segment])
                left, right = self.ankles[segment:segment+2]
                source_x = left + (right - left) * weight
                _, a = contacts[segment]
                _, b = contacts[segment+1]
                blend = ramp(weight, .25, .75)
                lift = a + (b - a) * blend
                source_x -= upper * (lean * head + tail * curl)
                dy = dip * (1. - foot) * (.64 * head + .36 * upper) - lift * foot
                row.append((source_x, y - dy))
            rows.append(row)
        mesh = []
        for y_index, (y0, y1) in enumerate(zip(self.y_grid, self.y_grid[1:])):
            a, b = rows[y_index:y_index+2]
            for x_index, (x0, x1) in enumerate(zip(self.x_grid, self.x_grid[1:])):
                mesh.append(((x0, y0, x1, y1), (*a[x_index], *b[x_index], *b[x_index+1], *a[x_index+1])))
        bent = source.transform(source.size, Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
        if not only_body:
            return bent
        lifted = self.leg.rotate(-paw, Image.Resampling.BICUBIC, center=self.hinge)
        shoulder = round(dip * .64 * self.head_weight(self.hinge[0]))
        if shoulder:
            lifted = lifted.transform(lifted.size, Image.Transform.AFFINE,
                                      (1, 0, 0, 0, 1, -shoulder), Image.Resampling.BICUBIC)
        gesture = Image.alpha_composite(lifted, bent)
        if paw < 6:
            # Hide the mask's seam while the gesture leaves the planted foot.
            grounded = self.standing.transform(source.size, Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)
            return Image.blend(grounded, gesture, ramp(paw, 0, 6))
        return gesture


@lru_cache(maxsize=4)
def stage_backdrop(width, height):
    layer = Image.new('RGBA', (width, height), '#151427')
    glow = Image.new('RGBA', layer.size)
    paint = ImageDraw.Draw(glow)
    paint.ellipse((-width*.18, -height*.16, width*.77, height*.96), fill='#293861')
    paint.ellipse((width*.25, height*.1, width*1.14, height*1.03), fill='#64335d')
    layer = Image.alpha_composite(layer, glow.filter(ImageFilter.GaussianBlur(width*.2)))
    paint = ImageDraw.Draw(layer)
    paint.arc((width*.08, height*.13, width*.92, height*.84), 195, 345, fill='#674771', width=2)
    paint.arc((width*.13, height*.17, width*.87, height*.79), 202, 338, fill='#4d4167')
    cutout = Image.new('L', layer.size)
    ImageDraw.Draw(cutout).rounded_rectangle((2, 2, width-3, height-3), radius=15, fill=255)
    return layer, cutout


class DanceRoutine:
    def __init__(self, standing, stage, partner=None):
        self.dog = DancePose(standing, FORELEGS[stage], ANKLES[stage])
        self.partner = DancePose(partner, CAT_FORELEG, CAT_ANKLES) if partner is not None else None

    def frame(self, elapsed, width, height):
        beat = min(DANCE_SECONDS, max(0., elapsed)) / SECONDS_PER_BEAT
        stage, cutout = stage_backdrop(width, height)
        stage = stage.copy()
        floor = round(height * .89)
        accent = max(math.exp(-9 * (beat - cue)) for cue in ACCENTS if cue <= beat)
        light = Image.new('RGBA', stage.size)
        paint = ImageDraw.Draw(light)
        for x, hue in ((.22, (120, 170, 255)), (.78, (253, 117, 151))):
            swing = x + .045 * math.sin(beat * .52)
            paint.polygon(((width*swing-7, 0), (width*swing+7, 0),
                           (width*(x+.26), floor), (width*(x-.24), floor)),
                          fill=(*hue, round(21+47*accent)))
        stage = Image.alpha_composite(stage, light.filter(ImageFilter.GaussianBlur(12)))
        paint = ImageDraw.Draw(stage)
        paint.ellipse((9, floor-20, width-10, floor+17), fill='#28213c', outline='#5b4262')
        paint.arc((9, floor-20, width-10, floor+17), 24, 157,
                  fill=(round(167+66*accent), round(102+46*accent), 158, 255), width=2)
        paint.arc((24, floor-16, width-25, floor+11), 204, 336, fill='#66507e')
        for i in range(7):
            x = width * (.11 + .13*i)
            y = height * (.19 - .045*math.sin(math.pi*i/6))
            paint.ellipse((x-2, y-2, x+2, y+2), fill=(round(147+88*accent), 126, 181, 255))

        dog_side = min(round(width * .74), height - 46)
        move, feet = footwork(beat, 0., DOG_TRANSFERS)
        self.draw(stage, self.dog, body_at(beat, DOG_KEYS, DOG_TIMES), feet,
                  width*.49 + move*dog_side/256, floor, dog_side)
        if self.partner is not None and beat > CAT_ENTRANCE:
            cat_side = min(round(width * .44), height - 52)
            cat_move, cat_feet = footwork(beat, 113., CAT_TRANSFERS)
            self.draw(stage, self.partner, body_at(beat, CAT_KEYS, CAT_TIMES), cat_feet,
                      width*.79 + cat_move*cat_side/256, floor-2, cat_side)
        stage.putalpha(ImageChops.multiply(stage.getchannel('A'), cutout))
        return stage

    @staticmethod
    def draw(stage, rig, body, feet, x, floor, side):
        lean, dip, lift, tail = body
        sprite = rig.pose(lean, dip, lift, tail=tail, feet=feet)
        sprite = sprite.resize((side, side), Image.Resampling.LANCZOS)
        y = floor - round(rig.bounds[3] * side / rig.standing.height)
        paint = ImageDraw.Draw(stage)
        paint.ellipse((x-side*.30, floor-6, x+side*.31, floor+4), fill='#191525')
        stage.alpha_composite(sprite, (round(x-side/2), y))
