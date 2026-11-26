"""Render the upright duo's action blocking and a full-size rhythm preview."""
from bisect import bisect_right
from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageOps

APP = Path(__file__).resolve().parents[1] / 'outputs/XiaohanDesktop'
sys.path.insert(0, str(APP))
from dance import SECONDS_PER_BEAT
from fetch_game import ramp
from model import DANCE_SECONDS

SIZE = (460, 410)
FLOOR = 343
INTERVAL = 40
HITS = (0., 2.3, 4.85, 6.9, 8., 10., 12.3, 13.85, 15.4, 16.35)


@dataclass(frozen=True)
class Pose:
    # Feet are floor coordinates, independent of the moving hips.
    beat: float
    hips: tuple
    tilt: float
    yaw: float
    hands: tuple
    feet: tuple
    close: float = 0.


# The two kicks switch the supporting foot. The cat enters during the recovery.
DOG = (
    Pose(0., (0, 53), -4, -13, (-41, 21, 34, 22), (-21, 0, 21, 0)),
    Pose(.92, (7, 56), 10, 10, (-30, 29, 54, 2), (-21, 0, 36, 12)),
    Pose(1.7, (15, 56), 16, 24, (-44, -7, 39, -29), (-21, 0, 40, 0)),
    Pose(2.3, (10, 59), -5, 0, (20, -17, -17, -39), (-15, 13, 40, 0)),
    Pose(2.95, (0, 58), -13, -17, (-46, 3, 34, -37), (-23, 0, 40, 0)),
    Pose(3.65, (-8, 53), -5, -4, (-20, -48, 18, -38), (-23, 0, 19, 11)),
    Pose(4.35, (-5, 48), 10, 9, (-19, -20, 24, -18), (-23, 0, 10, 0), .25),
    Pose(4.85, (-3, 55), 12, 0, (-15, -16, 26, -7), (-23, 0, 10, 0), 1.),
    Pose(5.42, (-7, 51), -6, -8, (-37, -13, 38, 2), (-23, 0, 10, 0), .10),
    Pose(6.18, (-14, 48), -11, -11, (-34, 7, 13, -48), (-23, 0, 17, 31)),
    Pose(6.9, (-13, 63), -15, 7, (-34, -23, 24, -49), (-23, 0, 60, 123)),
    Pose(7.32, (-12, 56), -12, 4, (-45, -6, 44, -19), (-23, 0, 42, 83)),
    Pose(8., (-4, 48), 17, 18, (-42, 18, 50, 8), (-23, 0, 15, 0)),
    Pose(8.9, (-13, 53), 6, -12, (-35, -2, 45, 9), (-38, 15, 15, 0)),
    Pose(9.65, (-32, 54), -13, -21, (-45, -12, 42, 13), (-51, 0, 15, 0)),
    Pose(10.6, (-36, 57), 1, 32, (-35, -39, 21, -31), (-51, 0, -17, 15)),
    Pose(11.22, (-38, 57), 11, 114, (-44, -32, 51, 1), (-51, 0, -12, 0)),
    Pose(11.92, (-33, 58), 3, 256, (-47, 14, 47, -22), (-50, 9, -12, 0)),
    Pose(12.45, (-34, 51), -13, 347, (-26, -37, 52, 3), (-53, 0, -12, 0)),
    Pose(13.16, (-28, 48), 14, 353, (-16, -45, 37, 0), (-42, 31, -12, 0)),
    Pose(13.85, (-25, 61), 15, 360, (-21, -46, 40, -17), (-79, 123, -12, 0)),
    Pose(14.24, (-25, 55), 11, 367, (-43, -15, 35, -38), (-79, 72, -12, 0)),
    Pose(14.96, (-34, 51), -3, 358, (-47, 4, 45, -20), (-56, 0, -12, 0)),
    Pose(15.4, (-35, 45), -6, 354, (-49, -6, 46, 4), (-56, 0, -12, 0)),
    Pose(16.35, (-36, 23), -15, 350, (-58, 18, 42, 7), (-56, 0, -12, 0)),
    Pose(17.34, (-36, 25), -12, 352, (-53, 19, 43, 9), (-56, 0, -12, 0)),
)
CAT = (
    Pose(7.7, (127, 54), -13, -22, (-36, 6, 26, 28), (112, 0, 142, 0)),
    Pose(8.35, (105, 56), -11, -28, (-36, -13, 44, 16), (85, 15, 142, 0)),
    Pose(9.0, (86, 54), -15, -15, (-50, 6, 40, -7), (64, 0, 104, 13)),
    Pose(9.67, (55, 56), -15, -19, (-54, -12, 35, -14), (39, 17, 81, 0)),
    Pose(10.28, (32, 55), -12, 0, (-25, -35, 37, -30), (8, 0, 65, 10)),
    Pose(10.9, (12, 52), 5, -13, (-18, -20, 20, -8), (-5, 0, 40, 0), .82),
    Pose(11.6, (7, 55), 2, 66, (-38, -34, 35, -22), (-5, 0, 27, 12)),
    Pose(12.11, (6, 56), -6, 248, (-36, -10, 39, 0), (0, 9, 27, 0)),
    Pose(12.55, (7, 51), 5, 347, (-31, -42, 40, 2), (-8, 0, 27, 0)),
    Pose(13.16, (10, 49), -9, 353, (-32, -1, 18, -43), (-8, 0, 29, 29)),
    Pose(13.85, (8, 57), -13, 360, (-41, -19, 32, -42), (-8, 0, 56, 108)),
    Pose(14.25, (7, 56), -6, 360, (-37, -28, 39, -10), (-8, 0, 54, 72)),
    Pose(15., (4, 51), 17, 370, (-43, 18, 39, -18), (-8, 0, 21, 0)),
    Pose(16.35, (4, 23), 11, 372, (-45, 17, 50, 13), (-8, 0, 21, 0)),
    Pose(17.34, (4, 24), 8, 370, (-44, 19, 45, 16), (-8, 0, 21, 0)),
)


def pose_at(track, beat):
    index = max(0, min(len(track)-2, bisect_right(track, beat, key=lambda p: p.beat)-1))
    a, b = track[index:index+2]
    mix = ramp(beat, a.beat, b.beat)

    def blend(left, right):
        return left + (right-left)*mix

    return Pose(beat, tuple(map(blend, a.hips, b.hips)), blend(a.tilt, b.tilt),
                blend(a.yaw, b.yaw), tuple(map(blend, a.hands, b.hands)),
                tuple(map(blend, a.feet, b.feet)), blend(a.close, b.close))


def atlas(path):
    sheet = Image.open(path).convert('RGBA')
    w, h = sheet.size
    pieces = []
    for row in range(2):
        for col in range(3):
            part = sheet.crop((round(w*col/3), round(h*row/2), round(w*(col+1)/3), round(h*(row+1)/2)))
            a = part.getchannel('A')
            bounds = a.point(lambda opacity: 255 if opacity >= 140 else 0).getbbox()
            if bounds is None:
                raise ValueError(f'Missing sprite in {path} at row {row}, column {col}')
            a = a.point(lambda opacity: max(0, round(255*(opacity-58)/197)))
            part.putalpha(a)
            x0, y0, x1, y1 = bounds
            pieces.append(part.crop((max(0, x0-7), max(0, y0-7), min(part.width, x1+7), min(part.height, y1+7))))
    return pieces


def stamp(canvas, image, center, size, angle=0.):
    sprite = image.resize(tuple(max(2, round(n)) for n in size), Image.Resampling.LANCZOS)
    if abs(angle) > .1:
        sprite = sprite.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    x, y = center
    canvas.alpha_composite(sprite, (round(x-sprite.width/2), round(y-sprite.height/2)))


def limb(canvas, piece, start, end, width, overlap):
    dx, dy = end[0]-start[0], end[1]-start[1]
    midpoint = ((start[0]+end[0])/2, (start[1]+end[1])/2)
    stamp(canvas, piece, midpoint, (width, math.hypot(dx, dy)+overlap),
          math.degrees(math.atan2(dx, dy)))


def bend(start, end, upper, lower, side):
    dx, dy = end[0]-start[0], end[1]-start[1]
    distance = max(.01, math.hypot(dx, dy))
    length = min(upper + lower - .02, max(abs(upper-lower) + .02, distance))
    along = (length*length + upper*upper - lower*lower)/(2*length)
    across = math.sqrt(max(0., upper*upper - along*along)) * side
    ux, uy = dx / distance, dy / distance
    return start[0]+along*ux-across*uy, start[1]+along*uy+across*ux


def fur_back(image, tail):
    # A solid patch from the tail keeps the turn's outlines and avoids introducing a new face.
    inset = max(3, tail.width//11)
    core = tail.getchannel('A').filter(ImageFilter.MinFilter(2*inset+1))
    x, y = next((x, y) for y in range(inset, core.height-inset, 3)
                for x in range(inset, core.width-inset, 3) if core.getpixel((x, y)) >= 220)
    patch = tail.crop((x-inset, y-inset, x+inset, y+inset))
    back = patch.resize(image.size, Image.Resampling.LANCZOS)
    back.putalpha(image.getchannel('A'))
    return back


class Dancer:
    def __init__(self, parts):
        self.head, self.body, self.tail, self.arm, self.leg, self.pad = parts
        # Overlap the painted limb on both sides of its joint.
        self.thigh = self.leg.crop((0, 0, self.leg.width, round(self.leg.height*.66)))
        self.shin = self.leg.crop((0, round(self.leg.height*.42), self.leg.width, round(self.leg.height*.88)))
        self.foot = self.leg.crop((0, round(self.leg.height*.79), self.leg.width, self.leg.height))
        self.foot = self.foot.crop(self.foot.getchannel('A').point(lambda a:255 if a >= 120 else 0).getbbox())
        self.upper_arm = self.arm.crop((0, 0, self.arm.width, round(self.arm.height*.67)))
        self.forearm = self.arm.crop((0, round(self.arm.height*.43), self.arm.width, self.arm.height))
        self.head_back = fur_back(self.head, self.tail)
        self.body_back = fur_back(self.body, self.tail)

    def render(self, canvas, anchor, scale, p):
        if anchor + scale * (p.hips[0]-80) > canvas.width:
            return
        yaw = math.radians(p.yaw)
        face = math.cos(yaw)
        spread = .54 + .46*abs(face)
        lean = math.radians(p.tilt)
        hx, hy = p.hips
        torso = 52 if hy>43 else 44+.19*hy
        sx, sy = hx+torso*math.sin(lean), -hy-torso*math.cos(lean)
        rear = face < -.05
        pad_diameter = 24 + 45*p.close

        def point(x, y):
            return anchor + x*scale, FLOOR + y*scale

        tail_tip = (hx+math.sin(yaw+.9)*34, -hy-12+3*math.sin(p.beat*3.7))
        if not rear:
            tail = self.tail if math.sin(yaw+.9) > 0 else ImageOps.mirror(self.tail)
            stamp(canvas, tail, point(*tail_tip), (54*scale, 55*scale), 12*math.sin((p.beat-.25)*2.3))

        for i, side in enumerate((-1, 1)):
            foot, lift = p.feet[2*i:2*i+2]
            hip = (hx + side*15*spread, -hy)
            ankle = (foot, -lift-5.)
            knee = bend(hip, ankle, 30, 29, -side)
            limb(canvas, self.thigh, point(*hip), point(*knee), 29*scale, 15*scale)
            limb(canvas, self.shin, point(*knee), point(*ankle), 15*scale, 10*scale)
            toes = math.degrees(math.atan2(ankle[0]-knee[0], ankle[1]-knee[1]))
            turn = toes * ramp(lift, 3, 38)
            stamp(canvas, self.foot, point(*ankle), (21*scale, 13*scale), turn)

        torso_stamp = self.body_back if rear else self.body
        stamp(canvas, torso_stamp, point((hx+sx)/2, (-hy+sy)/2), (61*spread*scale, 76*scale), -p.tilt)
        for i, side in enumerate((-1, 1)):
            u, v = p.hands[2*i:2*i+2]
            shoulder = (sx+side*23*spread, sy+5+side*3*math.sin(lean))
            palm = (sx+u, sy+v)
            elbow = bend(shoulder, palm, 29, 27, side)
            limb(canvas, self.upper_arm, point(*shoulder), point(*elbow), 24*scale, 13*scale)
            limb(canvas, self.forearm, point(*elbow), point(*palm), 22*scale, 11*scale)

        head = self.head_back if rear else self.head
        if not rear and math.sin(yaw) < -.5:
            head = ImageOps.mirror(head)
        stamp(canvas, head, point(sx + 12*math.sin(yaw), sy - 23 - 3*p.close),
              ((69+13*abs(face))*scale, 76*scale), -p.tilt*.7)

        if rear:
            stamp(canvas, self.tail, point(*tail_tip), (51*scale, 58*scale), -17)
        if p.close > .16:
            x, y = p.hands[2:4]
            stamp(canvas, self.pad, point(sx+x, sy+y), (pad_diameter*scale, pad_diameter*scale), -17)


@lru_cache(maxsize=1)
def background():
    base = Image.new('RGBA', SIZE, '#211734')
    wash = Image.new('RGBA', SIZE)
    d = ImageDraw.Draw(wash)
    d.ellipse((-105, -90, 385, 438), fill='#4c326f')
    d.ellipse((190, -105, 660, 418), fill='#9a3e74')
    d.ellipse((98, 158, 410, 480), fill='#3d4082')
    base = Image.alpha_composite(base, wash.filter(ImageFilter.GaussianBlur(75)))
    d = ImageDraw.Draw(base)
    d.ellipse((12, FLOOR-30, SIZE[0]-12, FLOOR+36), fill='#231a36', outline='#8d5a8c', width=2)
    d.arc((22, FLOOR-26, SIZE[0]-22, FLOOR+29), 14, 166, fill='#a473ba', width=2)
    return base


def frame(elapsed, dog, cat):
    beat = elapsed / SECONDS_PER_BEAT
    if beat >= HITS[0]:
        hit = math.exp(-9. * (beat - HITS[bisect_right(HITS, beat)-1]))
    else:
        hit = 0.
    layer = background().copy()
    lights = Image.new('RGBA', SIZE)
    d = ImageDraw.Draw(lights)
    for x, shift, color in ((105, -80, (181, 156, 255)), (326, 93, (255, 139, 191))):
        d.polygon(((x-7, 1), (x+7, 1), (x+shift+110, FLOOR), (x+shift-100, FLOOR)),
                  fill=(*color, round(24+66*hit)))
    layer = Image.alpha_composite(layer, lights.filter(ImageFilter.GaussianBlur(15)))
    paint = ImageDraw.Draw(layer)
    for index in range(11):
        x = 26 + 40*index
        y = 55 - 27 * math.sin(math.pi*index/10)
        radius = 1.9 + 1.5*hit
        paint.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(220, 179, 217))

    performers = [(dog, 194, 1.65, pose_at(DOG, beat))]
    if beat > CAT[0].beat:
        performers.append((cat, 333, 1.31, pose_at(CAT, beat)))
    for _, placement, scale, pose in performers:
        x, _ = pose.hips
        center = placement+x*scale
        paint.ellipse((center-43*scale, FLOOR-7, center+43*scale, FLOOR+7), fill='#19132b')
    for performer, placement, scale, pose in performers:
        performer.render(layer, placement, scale, pose)
    return layer.convert('RGB')


def render(dog, cat, output):
    frames = [frame(t/1000, dog, cat) for t in range(0, DANCE_SECONDS*1000, INTERVAL)]
    key_times = (.4, 2.24, 3.18, 4.28, 5.12, 6.4, 7.57)
    board = Image.new('RGB', (368*4, 328*2), '#211734')
    for i, time in enumerate(key_times):
        thumbnail = frames[round(1000*time/INTERVAL)].resize((368, 328))
        board.paste(thumbnail, (368*(i % 4), 328*(i // 4)))
    board.save(output.with_name('key-poses.png'))
    strip = Image.new('RGB', (SIZE[0], SIZE[1]*8))
    for index, at in enumerate(range(0, 200, 25)):
        strip.paste(frames[at], (0, index*SIZE[1]))
    palette = strip.quantize(colors=256)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in frames]
    frames[0].save(output, save_all=True, append_images=frames[1:], duration=INTERVAL, loop=0)


if __name__ == '__main__':
    dog, cat = map(lambda path: Dancer(atlas(path)), sys.argv[1:3])
    render(dog, cat, Path(sys.argv[3]))
