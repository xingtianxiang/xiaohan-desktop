"""Age-specific artwork selection; adult sequences keep their original assets."""

AGES = ('puppy', 'teen', 'adult')
FETCH_POSES = ('pickup','turnquarter','turnfront','run0','run1','run2','run3','drop')
# Packed artwork: two head movements followed by four cyclic paw transitions.
HEAD_FRAMES = 13
STEP_FRAMES = 7
GAIT_COLUMNS = 8
GAIT_TILE = 192
FRAME_COUNTS = {
    'eat': (2, 2, 2), 'drink': (2, 2, 2), 'sleep': (2, 2, 2),
    'play': (2, 2, 2), 'type': (4, 4, 4), 'walk': (4, 4, 6),
    'hungry': (2,2,2), 'thirsty': (2,2,2), 'tired': (2,2,2),
    'potty': (2,2,2),
}
FPS = {'eat': 2, 'drink': 2, 'sleep': 1, 'play': 3, 'type': 9, 'walk': 7,
       'hungry': 1, 'thirsty': 1, 'tired': 1, 'potty': 2}


def frame_names(outfit, stage, motion):
    prefix = outfit if stage == 2 else f'{outfit}_{AGES[stage]}'
    return tuple(f'{prefix}_{motion}{i}' for i in range(FRAME_COUNTS[motion][stage]))


def motion_frame(outfit, stage, motion, elapsed):
    frames = frame_names(outfit, stage, motion)
    if motion in ('hungry','tired'):
        return frames[int(max(0,elapsed)%4>=3.5)]
    return frames[int(max(0, elapsed) * FPS[motion]) % len(frames)]


def fetch_asset(outfit,stage,pose):
    prefix=outfit if stage==2 else f'{outfit}_{AGES[stage]}'
    return f'{prefix}_fetch_{pose}'


def required_assets(outfits):
    names = []
    for outfit in outfits:
        names.extend(f'{outfit}_{pose}' for pose in (*AGES, 'shy'))
        for stage in range(len(AGES)):
            names.extend(fetch_asset(outfit,stage,pose) for pose in FETCH_POSES)
            for motion in FRAME_COUNTS:
                names.extend(frame_names(outfit, stage, motion))
    return names
