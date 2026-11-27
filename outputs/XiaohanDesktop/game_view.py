"""Draw the arcade games on the pet window's canvas, in the same paper-and-glass style as the trip views."""
import math

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

from animation import AGES, frame_names
from desktop_platform import UI_FONT
from minigames import GAME_SIZE, CatchGame, Hurdle, HurdleGame, MemoryGame, ShellGame
from model import ACTIONS
from mouse_play import ART, HEADS
from trip_view import INK, TEAL, draw_scene_button, pill

W, H = GAME_SIZE
CORNER = 12
SS = 4  # supersampling for the hand-drawn props
GAME_EXIT = (340, 10, 408, 42)
CARD = (70, 78, 350, 244)
CARD_BUTTON = (150, 198, 270, 230)
AGE_SCALE = (.70, .88, 1.)
SOLE = 244 / ART
CORAL = '#c4514d'
MUTED = '#6f8580'
SCENES = {'catch': 'home', 'shell': 'park', 'hurdle': 'park', 'memory': 'snow'}
UNITS = {'catch': '分', 'shell': '关', 'hurdle': '米', 'memory': '关'}
HOW_TO = {
    'catch': ('移动鼠标，小汉会跑过去接', '骨头 +3，饼干 +1\n巧克力和葡萄狗狗不能吃，吃到扣一颗心'),
    'shell': ('看好球藏在哪个桶里', '桶换完位置后点出球，猜错就结束\n越往后换得越快，第 5 关变成四个桶'),
    'hurdle': ('按空格或按住鼠标起跳', '矮栏轻按就能过，高栏要按久一点\n越跑越快，撞到栏就结束'),
    'memory': ('记住爪印亮起的顺序', '照着顺序点一遍，每关多一步\n闪得越来越快，点错或停太久就结束'),
}
# Body size for each game's sprite of the idle painting; motion frames are scaled by age.
DOG_SIZE = {'catch': 170, 'shell': 128, 'hurdle': 150, 'memory': 128}
PAW_COLOURS = ((87, 169, 154), (224, 127, 106), (224, 178, 79), (108, 155, 216))
DOG_FEET = 196  # where she sits behind the cups and paw prints


def catch_geometry(stage, size=DOG_SIZE['catch']):
    """Mouth height above the floor and its sideways reach from the body centre, from the idle painting."""
    head = HEADS[stage]
    cx, cy = head['centre']
    mouth_y = cy + .35 * head['radius']
    return (ART * SOLE - mouth_y) / ART * size, (ART / 2 - cx) / ART * size


def hurdle_half_width(stage):
    return round(16 * (.85 + .15 * AGE_SCALE[stage]))


def supersampled(width, height, draw):
    image = Image.new('RGBA', (width * SS, height * SS))
    draw(ImageDraw.Draw(image), SS)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def soft_card(width, height):
    image = Image.new('RGBA', (width * 2, height * 2))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 8, width * 2 - 4, height * 2 - 2), 36, fill=(40, 75, 60, 46))
    image = image.filter(ImageFilter.GaussianBlur(6))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, width * 2 - 4, height * 2 - 8), 36, fill=(255, 250, 242, 244),
                           outline=(255, 255, 250, 255), width=2)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def shadow(width):
    height = max(6, round(width * .2))
    image = Image.new('RGBA', (width + 16, height + 16))
    ImageDraw.Draw(image).ellipse((8, 8, width + 8, height + 8), fill=(42, 52, 40, 70))
    return image.filter(ImageFilter.GaussianBlur(3))


def draw_biscuit(d, s):
    d.ellipse((2*s, 2*s, 32*s, 32*s), fill=(214, 158, 82), outline=(166, 112, 55), width=2*s)
    d.ellipse((6*s, 5*s, 28*s, 27*s), fill=(232, 182, 104))
    for x, y in ((12, 12), (21, 11), (16, 19), (23, 21), (10, 22)):
        d.ellipse(((x-1.6)*s, (y-1.6)*s, (x+1.6)*s, (y+1.6)*s), fill=(150, 98, 48))


def draw_bone(d, s):
    fill, edge = (250, 243, 226), (196, 178, 146)
    for x, y in ((7, 7), (7, 17), (37, 7), (37, 17)):
        d.ellipse(((x-6)*s, (y-6)*s, (x+6)*s, (y+6)*s), fill=fill, outline=edge, width=2*s)
    d.rectangle((7*s, 6*s, 37*s, 18*s), fill=fill)
    d.line((7*s, 6*s, 37*s, 6*s), fill=edge, width=2*s)
    d.line((7*s, 18*s, 37*s, 18*s), fill=edge, width=2*s)


def draw_chocolate(d, s):
    d.rounded_rectangle((2*s, 3*s, 34*s, 27*s), 3*s, fill=(92, 52, 34), outline=(58, 31, 20), width=2*s)
    for x in (12, 23):
        d.line((x*s, 4*s, x*s, 26*s), fill=(70, 38, 25), width=s)
    d.line((3*s, 15*s, 33*s, 15*s), fill=(70, 38, 25), width=s)
    d.polygon(((20*s, 3*s), (34*s, 3*s), (34*s, 16*s), (28*s, 10*s)), fill=(206, 212, 220), outline=(150, 158, 168))


def draw_grapes(d, s):
    d.line((16*s, 2*s, 17*s, 9*s), fill=(104, 86, 54), width=2*s)
    d.polygon(((17*s, 6*s), (27*s, 1*s), (24*s, 9*s)), fill=(120, 170, 86))
    for x, y in ((10, 13), (17, 12), (24, 13), (13, 20), (21, 20), (17, 27), (9, 23), (25, 22)):
        d.ellipse(((x-5)*s, (y-5)*s, (x+5)*s, (y+5)*s), fill=(118, 72, 148), outline=(78, 44, 104), width=s)
        d.ellipse(((x-3)*s, (y-3.5)*s, (x-1)*s, (y-1.5)*s), fill=(190, 160, 214))


ITEMS = {'biscuit': ((34, 34), draw_biscuit), 'bone': ((44, 24), draw_bone),
         'chocolate': ((36, 30), draw_chocolate), 'grapes': ((34, 34), draw_grapes)}


def draw_heart(full):
    def paint(d, s):
        colour = (214, 92, 92) if full else (222, 214, 204)
        d.ellipse((1*s, 2*s, 10*s, 11*s), fill=colour)
        d.ellipse((8*s, 2*s, 17*s, 11*s), fill=colour)
        d.polygon(((1.6*s, 8*s), (16.4*s, 8*s), (9*s, 16*s)), fill=colour)
    return supersampled(18, 18, paint)


def draw_cup(d, s):
    # An upside-down pail: wide rim on the grass, narrow base on top.
    body, dark, band = (214, 104, 86), (168, 74, 60), (250, 236, 214)
    d.polygon(((12*s, 6*s), (58*s, 6*s), (66*s, 60*s), (4*s, 60*s)), fill=body, outline=dark, width=2*s)
    d.ellipse((12*s, 1*s, 58*s, 11*s), fill=(226, 128, 108), outline=dark, width=2*s)
    d.polygon(((6*s, 48*s), (64*s, 48*s), (66*s, 60*s), (4*s, 60*s)), fill=band, outline=dark, width=2*s)
    d.arc((8*s, 14*s, 62*s, 56*s), 200, 340, fill=(250, 236, 214), width=3*s)
    for x, y, r in ((35, 30, 5), (28, 23, 2.4), (35, 21, 2.4), (42, 23, 2.4)):
        d.ellipse(((x-r)*s, (y-r)*s, (x+r)*s, (y+r)*s), fill=(250, 236, 214))


def draw_ball(d, s):
    d.ellipse((1*s, 1*s, 25*s, 25*s), fill=(240, 138, 60), outline=(190, 92, 36), width=2*s)
    d.arc((4*s, 6*s, 22*s, 24*s), 200, 340, fill=(255, 226, 190), width=2*s)
    d.ellipse((6*s, 5*s, 11*s, 10*s), fill=(255, 214, 170))


def draw_hurdle(kind):
    height = Hurdle.HEIGHTS[kind]

    def paint(d, s):
        top = 9
        bottom = top + height
        # Two posts, the far one a little higher, joined by a striped bar seen from the side.
        for x, lift in ((19, 6), (7, 0)):
            d.rounded_rectangle(((x-3)*s, (top-lift-2)*s, (x+3)*s, (bottom-lift)*s), 1.5*s, fill=(246, 246, 240),
                                outline=(130, 138, 132), width=s)
            d.rounded_rectangle(((x-6)*s, (bottom-lift-4)*s, (x+6)*s, (bottom-lift)*s), s, fill=(104, 116, 108))
        for i in range(4):
            x0, x1 = 7 + 3*i, 7 + 3*(i+1)
            d.line((x0*s, (top - 1.5*i)*s, x1*s, (top - 1.5*(i+1))*s),
                   fill=(214, 64, 58) if i % 2 == 0 else (252, 252, 248), width=7*s)
    return supersampled(26, height + 13, paint)


def draw_paw(colour, lit):
    def paint(d, s):
        base = colour if lit else tuple(round(c + (238 - c) * .55) for c in colour)
        if lit:
            d.ellipse((2*s, 2*s, 86*s, 86*s), fill=(*colour, 70))
            d.ellipse((7*s, 7*s, 81*s, 81*s), fill=(255, 252, 236, 120))
        edge = tuple(round(c * .72) for c in base)
        d.ellipse((24*s, 40*s, 64*s, 74*s), fill=base, outline=edge, width=2*s)
        for x, y in ((20, 32), (34, 20), (54, 20), (68, 32)):
            d.ellipse(((x-8)*s, (y-9)*s, (x+8)*s, (y+9)*s), fill=base, outline=edge, width=2*s)
    return supersampled(88, 88, paint)


class GameArt:
    """Caches backdrops, sprites and props as Tk images for one canvas."""

    def __init__(self, master, images, renderer):
        self.master, self.images, self.renderer = master, images, renderer
        self.photos = {}
        self.corners = Image.new('L', GAME_SIZE, 0)
        ImageDraw.Draw(self.corners).rounded_rectangle((0, 0, W - 1, H - 1), CORNER, fill=255)
        self.strip = None
        self.frame_photo = None

    def photo(self, key, make):
        if key not in self.photos:
            self.photos[key] = ImageTk.PhotoImage(make(), master=self.master)
        return self.photos[key]

    def backdrop_image(self, scene):
        image = ImageOps.fit(self.images['scene_' + scene], GAME_SIZE, Image.Resampling.LANCZOS).convert('RGBA')
        image.putalpha(self.corners)
        return image

    def backdrop(self, scene):
        return self.photo(('backdrop', scene), lambda: self.backdrop_image(scene))

    def scrolling(self, scene, offset):
        """The backdrop mirrored end to end so it scrolls without a seam."""
        if self.strip is None:
            # The paintings carry a dark hairline at their edges; trim it so the mirrored joins stay clean.
            tile = ImageOps.fit(self.images['scene_' + scene], (W + 8, H), Image.Resampling.LANCZOS).convert('RGBA')
            tile = tile.crop((4, 0, W + 4, H))
            self.strip = Image.new('RGBA', (W * 3, H))
            for index, part in enumerate((tile, ImageOps.mirror(tile), tile)):
                self.strip.paste(part, (index * W, 0))
        left = round(offset) % (2 * W)
        frame = self.strip.crop((left, 0, left + W, H))
        frame.putalpha(self.corners)
        self.frame_photo = ImageTk.PhotoImage(frame, master=self.master)
        return self.frame_photo

    def dog(self, scene, name, size, flip):
        def make():
            if scene in ('park', 'snow'):
                return self.renderer.sprite(scene, name, size, flip)
            image = self.images[name].resize((size, size), Image.Resampling.LANCZOS)
            return ImageOps.mirror(image) if flip else image
        return self.photo(('dog', scene, name, size, flip), make)

    def shadow(self, width):
        width = max(12, round(width / 4) * 4)
        return self.photo(('shadow', width), lambda: shadow(width))

    def item(self, kind, angle):
        angle = round(angle / 15) * 15 % 360
        size, paint = ITEMS[kind]
        return self.photo(('item', kind, angle),
                          lambda: supersampled(*size, paint).rotate(angle, Image.Resampling.BICUBIC, expand=True))

    def heart(self, full):
        return self.photo(('heart', full), lambda: draw_heart(full))

    def cup(self, scale):
        scale = round(scale * 20) / 20
        return self.photo(('cup', scale), lambda: supersampled(70, 62, draw_cup).resize(
            (round(70 * scale), round(62 * scale)), Image.Resampling.LANCZOS))

    def ball(self):
        return self.photo('ball', lambda: supersampled(26, 26, draw_ball))

    def hurdle(self, kind):
        return self.photo(('hurdle', kind), lambda: draw_hurdle(kind))

    def paw(self, pad, lit):
        return self.photo(('paw', pad, lit), lambda: draw_paw(PAW_COLOURS[pad], lit))

    def card(self):
        box = CARD
        return self.photo('card', lambda: soft_card(box[2] - box[0], box[3] - box[1]))


def place_dog(canvas, art, scene, name, size, flip, x, feet, lift=0.):
    canvas.create_image(x, feet + 8, image=art.shadow(size * .5 * max(.4, 1 - lift / 160)), tags='game_shadow')
    canvas.create_image(x, feet - lift + size * (1 - SOLE), image=art.dog(scene, name, size, flip), anchor='s',
                        tags='game_pet')


def idle_name(outfit, stage):
    return f'{outfit}_{AGES[stage]}'


def motion_size(key, stage):
    return round(DOG_SIZE[key] * AGE_SCALE[stage])


def draw_catch(canvas, art, game, outfit, stage):
    for item in game.items:
        canvas.create_image(item.x, item.y, image=art.item(item.kind, item.spin * game.elapsed), tags='game_item')
    shake = 3 * math.sin(game.elapsed * 60) if game.elapsed < game.hurt_until else 0
    if game.moving and game.phase == 'playing':
        frames = frame_names(outfit, stage, 'walk')
        name = frames[int(game.elapsed * 12) % len(frames)]
        size, flip = motion_size('catch', stage), not game.facing_right
    else:
        name, size, flip = idle_name(outfit, stage), DOG_SIZE['catch'], game.facing_right
    place_dog(canvas, art, 'home', name, size, flip, game.x + shake, CatchGame.FLOOR)
    for x, y, text, born in game.pops:
        age = game.elapsed - born
        canvas.create_text(x, y - 18 - 40 * age, text=text, fill=CORAL if '♥' in text else TEAL,
                           font=(UI_FONT, 12, 'bold'), tags='game_pop')


def draw_shell(canvas, art, game, outfit, stage):
    if game.stage == 'missed' and game.timer > .4:
        frames = frame_names(outfit, stage, 'tired')
        place_dog(canvas, art, 'park', frames[0], motion_size('shell', stage), False, W / 2, DOG_FEET)
    else:
        hop = 12 * math.sin(math.pi * min(1., game.timer / .45)) if game.stage == 'reveal' else 0
        place_dog(canvas, art, 'park', idle_name(outfit, stage), DOG_SIZE['shell'], False, W / 2, DOG_FEET, hop)
    if game.cups == 0:  # before the first round: three cups waiting in their places
        positions = [(100 + 110 * slot, 0., 0.) for slot in range(3)]
        cups = list(range(3))
    else:
        cups = list(range(game.cups))
        positions = [game.cup_position(cup) for cup in cups]
    for cup in cups:
        x, _, depth = positions[cup]
        canvas.create_image(x, ShellGame.BASE + 6 - 5 * depth, image=art.shadow(66 * (1 + .07 * depth)), tags='game_shadow')
    if game.cups and positions[game.ball][1] > 0:
        x = positions[game.ball][0]
        canvas.create_image(x, ShellGame.BASE - 13, image=art.ball(), tags='game_ball')
    for cup in sorted(cups, key=lambda c: positions[c][2]):
        x, lift, depth = positions[cup]
        canvas.create_image(x, ShellGame.BASE - lift + 2 - 5 * depth, image=art.cup(1 + .07 * depth), anchor='s',
                            tags='game_cup')


def draw_hurdle_run(canvas, art, game, outfit, stage):
    size = motion_size('hurdle', stage)
    for hurdle in game.hurdles:
        canvas.create_image(hurdle.x, HurdleGame.GROUND + 4, image=art.hurdle(hurdle.kind), anchor='s', tags='game_hurdle')
    if game.over:
        frames = frame_names(outfit, stage, 'tired')
        place_dog(canvas, art, 'park', frames[0], size, True, HurdleGame.RUN_X, HurdleGame.GROUND)
        return
    frames = frame_names(outfit, stage, 'walk')
    if game.airborne:
        name = frames[1 % len(frames)]
    else:
        name = frames[int(game.distance / 26) % len(frames)] if game.phase == 'playing' else idle_name(outfit, stage)
    if name == idle_name(outfit, stage):
        place_dog(canvas, art, 'park', name, DOG_SIZE['hurdle'], True, HurdleGame.RUN_X, HurdleGame.GROUND)
    else:
        place_dog(canvas, art, 'park', name, size, False, HurdleGame.RUN_X, HurdleGame.GROUND, game.height)


def draw_memory(canvas, art, game, outfit, stage):
    if game.stage == 'wrong' and game.timer > .4:
        frames = frame_names(outfit, stage, 'tired')
        place_dog(canvas, art, 'snow', frames[0], motion_size('memory', stage), False, W / 2, DOG_FEET)
    else:
        hop = 12 * math.sin(math.pi * min(1., game.timer / .45)) if game.stage == 'good' else 0
        place_dog(canvas, art, 'snow', idle_name(outfit, stage), DOG_SIZE['memory'], False, W / 2, DOG_FEET, hop)
    lit = game.lit
    for pad, (x, y) in enumerate(MemoryGame.CENTRES):
        canvas.create_image(x, y, image=art.paw(pad, pad == lit), tags='game_paw')


def hint(key, game):
    if game.phase != 'playing':
        return ''
    if key == 'shell':
        return {'show': '看好球在哪个桶里', 'shuffle': '盯住它…', 'choose': '点球所在的桶',
                'reveal': '猜对了！', 'missed': '球在这儿呢'}.get(game.stage, '')
    if key == 'memory':
        if game.stage == 'repeat':
            return f'轮到你：照顺序点 {game.entered}/{len(game.sequence)}'
        if game.stage == 'wrong':
            return '太慢啦，是这个' if game.wrong == 'slow' else '点错啦，是这个'
        return {'watch': '记住亮起的顺序', 'good': '全对！'}.get(game.stage, '')
    if key == 'hurdle' and game.elapsed < 4:
        return '矮栏轻按，高栏长按'
    if key == 'catch' and game.combo >= 5:
        return f'连接 {game.combo} 个！'
    return ''


def status(key, game):
    if key == 'catch':
        return f'{game.score} 分'
    if key == 'hurdle':
        return f'{game.score} 米'
    return f'第 {max(1, game.round)} 关'


def draw_game(canvas, art, key, game, *, outfit, stage, paused, best, result):
    """Draw one frame; returns the clickable controls as {name: box}."""
    scene = SCENES[key]
    if key == 'hurdle':
        canvas.create_image(0, 0, image=art.scrolling(scene, game.distance), anchor='nw', tags='game_scene')
    else:
        canvas.create_image(0, 0, image=art.backdrop(scene), anchor='nw', tags='game_scene')
    {'catch': draw_catch, 'shell': draw_shell, 'hurdle': draw_hurdle_run, 'memory': draw_memory}[key](
        canvas, art, game, outfit, stage)

    pill(canvas, (12, 10, 326, 42))
    canvas.create_text(26, 26, text=ACTIONS[key]['label'], anchor='w', fill=INK, font=(UI_FONT, 11, 'bold'))
    canvas.create_text(124 if key == 'catch' else 156 if key == 'hurdle' else 140, 26, text=status(key, game),
                       anchor='w', fill=TEAL, font=(UI_FONT, 10, 'bold'), tags='game_score')
    if key == 'catch':
        for index in range(CatchGame.LIVES):
            canvas.create_image(184 + 20 * index, 26, image=art.heart(index < game.lives), tags='game_heart')
    canvas.create_text(312, 26, text=f'最高 {best}' if best else '暂无记录', anchor='e', fill=MUTED, font=(UI_FONT, 9))
    draw_scene_button(canvas, GAME_EXIT, '× 退出', 'game_exit')
    controls = {'leave_game': GAME_EXIT}

    text = hint(key, game)
    if text and not paused:
        half = 12 + 13 * len(text) // 2
        pill(canvas, (W // 2 - half, 50, W // 2 + half, 78))
        canvas.create_text(W / 2, 63, text=text, fill=INK, font=(UI_FONT, 10, 'bold'), tags='game_hint')

    if paused:
        pill(canvas, (W // 2 - 60, H // 2 - 18, W // 2 + 60, H // 2 + 16))
        canvas.create_text(W / 2, H / 2 - 1, text='已暂停', fill=INK, font=(UI_FONT, 11, 'bold'))
        return controls
    if game.phase == 'ready':
        first, second = HOW_TO[key]
        canvas.create_image(CARD[0], CARD[1], image=art.card(), anchor='nw', tags='game_card')
        canvas.create_text(W / 2, 104, text=ACTIONS[key]['label'], fill=INK, font=(UI_FONT, 14, 'bold'))
        canvas.create_text(W / 2, 134, text=first, fill=INK, font=(UI_FONT, 10))
        canvas.create_text(W / 2, 166, text=second, fill=MUTED, font=(UI_FONT, 9), justify='center')
        draw_scene_button(canvas, CARD_BUTTON, '开始 · 空格', 'game_start', active=True)
        controls['start_game'] = CARD_BUTTON
    elif game.over and result is not None:
        canvas.create_image(CARD[0], CARD[1], image=art.card(), anchor='nw', tags='game_card')
        canvas.create_text(W / 2, 108, text=f'{result["score"]} {UNITS[key]}', fill=TEAL, font=(UI_FONT, 20, 'bold'),
                           tags='game_result')
        record = '新纪录！' if result['record'] else f'最高 {best} {UNITS[key]}'
        canvas.create_text(W / 2, 140, text=record, fill=CORAL if result['record'] else INK, font=(UI_FONT, 11, 'bold'))
        canvas.create_text(W / 2, 168, text=result['reward'], fill=MUTED, font=(UI_FONT, 9), width=244, justify='center')
        draw_scene_button(canvas, CARD_BUTTON, '再来一局', 'game_retry', active=True)
        controls['retry_game'] = CARD_BUTTON
    return controls
