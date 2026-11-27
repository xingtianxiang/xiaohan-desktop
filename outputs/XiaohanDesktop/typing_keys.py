"""Keycaps that float up from the keys you press on the keyboard in 小汉's typing paintings.

Each outfit and age has its own painted keyboard; assets/typing-keyboards.json gives its ends, the line of its
keys' front edge and the key area's depth, in the 256px canvas (work/build_typing_assets.py measures them).
Windows virtual-key codes are turned into keycap labels only for the animation; the app keeps the last few
in memory and saves none.
"""
ART = 256
ROWS = ('QWERTYUIOP', 'ASDFGHJKL;', 'ZXCVBNM,./')
SPACE = (3, 0)
DIGITS = '1234567890'
KEYCAP_SECONDS = .8
RISE = 46
# Keys sit a little in from the keyboard's rounded ends, the back rows (further away) more so.
END_INSET = 8
BACK_INSET = 8

NAMED = {0x20: '空格', 0x0D: '回车', 0x08: '退格', 0x09: 'Tab', 0x1B: 'Esc', 0x14: 'Caps', 0x2E: 'Del',
         0x10: 'Shift', 0xA0: 'Shift', 0xA1: 'Shift', 0x11: 'Ctrl', 0xA2: 'Ctrl', 0xA3: 'Ctrl',
         0x12: 'Alt', 0xA4: 'Alt', 0xA5: 'Alt', 0x5B: 'Win', 0x5C: 'Win',
         0x25: '←', 0x26: '↑', 0x27: '→', 0x28: '↓'}
OEM = {0xBA: ';', 0xBB: '=', 0xBC: ',', 0xBD: '-', 0xBE: '.', 0xBF: '/', 0xC0: '`',
       0xDB: '[', 0xDC: '\\', 0xDD: ']', 0xDE: "'"}
# Keys with no place on the three letter rows rise from the nearest edge key.
EDGE_SLOTS = {'退格': (0, 9), 'Del': (0, 9), '-': (0, 9), '=': (0, 9), '[': (0, 9), ']': (0, 9),
              'Tab': (0, 0), 'Esc': (0, 0), '`': (0, 0), 'Caps': (1, 0), '回车': (1, 9), '\\': (1, 9),
              "'": (1, 9), 'Shift': (2, 0), '←': (2, 9), '↑': (2, 9), '→': (2, 9), '↓': (2, 9)}


def vk_label(vk):
    """Keycap text for a Windows virtual-key code, or None for keys that get no keycap."""
    if 0x41 <= vk <= 0x5A or 0x30 <= vk <= 0x39:
        return chr(vk)
    if 0x60 <= vk <= 0x69:
        return str(vk - 0x60)
    if 0x70 <= vk <= 0x7B:
        return f'F{vk - 0x6F}'
    return NAMED.get(vk) or OEM.get(vk)


def key_slot(label):
    """(row, column) the keycap rises from: three rows of ten keys, back to front, then row 3, the space bar."""
    for row, letters in enumerate(ROWS):
        if label in letters:
            return row, letters.index(label)
    if label in DIGITS:
        return 0, DIGITS.index(label)
    if label.startswith('F') and label[1:].isdigit():
        return 0, (int(label[1:]) - 1) % 10
    return EDGE_SLOTS.get(label, SPACE)


def key_point(board, row, col):
    """Centre of a key on a painted keyboard, in 256px canvas pixels: its row's share of the key area's depth
    behind the front edge, at its column's place along the keyboard."""
    across = .5 if row == SPACE[0] else (col + .5) / 10
    inset = END_INSET + BACK_INSET * (1 - (row + .5) / 4)
    x = board['left'] + inset + (board['right'] - board['left'] - 2 * inset) * across
    front = board['front'][0] * x + board['front'][1]
    return x, front - board['depth'] + board['depth'] * (row + .5) / 4


def ease_out(t):
    t = min(1., max(0., t))
    return 1 - (1 - t) ** 3


def rounded(canvas, left, top, right, bottom, radius, **options):
    r = max(1., min(radius, (right - left) / 2, (bottom - top) / 2))
    points = (left + r, top, right - r, top, right, top, right, top + r, right, bottom - r, right, bottom,
              right - r, bottom, left + r, bottom, left, bottom, left, bottom - r, left, top + r, left, top)
    return canvas.create_polygon(points, smooth=True, **options)


def keycap_motion(age, start, centre_x):
    """Where a keycap is and how big, age seconds after its key went down: it pops out of the key,
    drifts up and outwards, then shrinks away (the pet window cannot fade)."""
    grow = ease_out(age / .18)
    shrink = 1 - ease_out((age - .55) / (KEYCAP_SECONDS - .55)) if age > .55 else 1.
    travel = ease_out(age / KEYCAP_SECONDS)
    x = start[0] + (start[0] - centre_x) * .35 * travel
    y = start[1] - RISE * travel
    return x, y, (.35 + .65 * grow) * shrink


def draw_keycap(canvas, label, x, bottom, zoom, font_family, ink):
    """A cream keycap standing on (x, bottom), in canvas items so it stays crisp on the keyed window."""
    if zoom < .12:
        return
    width = (30 if len(label) == 1 else 16 + 11 * len(label)) * zoom
    height = 26 * zoom
    left, right = x - width / 2, x + width / 2
    top = bottom - height
    rounded(canvas, left, top + 3 * zoom, right, bottom + 3 * zoom, 6 * zoom, fill='#968c78', outline='', tags='keycap')
    rounded(canvas, left, top, right, bottom, 6 * zoom, fill='#faf4e6', outline='#b0a48c', width=max(1, round(zoom)),
            tags='keycap')
    rounded(canvas, left + 4 * zoom, top + 3 * zoom, right - 4 * zoom, bottom - 5 * zoom, 5 * zoom, fill='#fffbf2',
            outline='', tags='keycap')
    size = max(5, round((12 if len(label) == 1 else 9) * zoom))
    canvas.create_text(x, top + height * .44, text=label, fill=ink, font=(font_family, size, 'bold'), tags='keycap_label')


def draw_typing_keys(canvas, keycaps, now, left, top, size, board, font_family, ink):
    """Float a keycap up from the key of each recent press; keycaps are (time, label)."""
    scale = size / ART
    centre_x = left + size / 2
    for at, label in keycaps:
        age = now - at
        if not 0 <= age < KEYCAP_SECONDS:
            continue
        kx, ky = key_point(board, *key_slot(label))
        x, y, zoom = keycap_motion(age, (left + kx * scale, top + ky * scale), centre_x)
        draw_keycap(canvas, label, x, y, zoom, font_family, ink)
