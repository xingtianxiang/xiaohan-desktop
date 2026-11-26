"""Local care state. Actions award effects only after their animation completes."""
import json
import math
import os
import stat
import time
from pathlib import Path

STAGES = ((0, 0, '幼年'), (20*3600, 20, '少年'), (40*3600, 55, '成年'))
OUTFITS = {'blue': '蓝色胸背', 'red': '红色领巾', 'yellow': '暖黄背心'}
SCENES = {'home': '温暖小屋', 'park': '阳光公园', 'snow': '雪地花园'}
# Shared game thresholds for need animations, meter colors and play guards.
NEED_LOW = 25
NEED_CRITICAL = 12
TOILET_REMIND_SECONDS = 2*3600
TOILET_URGENT_SECONDS = 3*3600
TOILET_FULL_SECONDS = 4*3600
TOILET_MIN_INTERVAL = 30*60
NEEDS = {
    'water': ('thirsty','喝水'),
    'food': ('hungry','吃饭'),
    'energy': ('tired','休息'),
    'toilet': ('potty','上厕所'),
}
NEED_ACTIONS = {'food': 'feed', 'water': 'water', 'energy': 'sleep', 'toilet': 'toilet'}
# Antivirus and file indexers briefly open new files without delete sharing.
SAVE_REPLACE_ATTEMPTS = 3
SAVE_RETRY_SECONDS = .1
DANCE_SECONDS = 8
# Tunable first-release game balance; seconds are active companionship, not wall age.
ACTIONS = {
    'feed': dict(label='喂一餐', duration=5, cooldown=30, pose='eat', effects={'food': 25, 'bond': 1, 'mood': 3}),
    'snack': dict(label='小零食', duration=3, cooldown=45, pose='idle', effects={'food': 8, 'bond': 1, 'mood': 6}),
    'water': dict(label='添水喝水', duration=4, cooldown=20, pose='drink', effects={'water': 30, 'bond': .5}),
    'toilet': dict(label='上厕所', duration=8, cooldown=0, pose='walk', effects={'mood': 2}),
    'pet': dict(label='摸摸头', duration=3, cooldown=15, pose='idle', effects={'mood': 8, 'bond': 1}),
    'toy': dict(label='拔玩具', duration=7, cooldown=30, pose='play', effects={'energy': -5, 'mood': 12, 'bond': 2, 'water': -3}),
    'ball': dict(label='扔球接回', duration=10, cooldown=0, pose='play', effects={'energy': -6, 'mood': 12, 'bond': 2, 'water': -4}),
    'walk': dict(label='一起散步', duration=15, cooldown=60, pose='idle', effects={'energy': -8, 'mood': 15, 'bond': 3, 'water': -5, 'food': -4}),
    'sleep': dict(label='睡一小觉', duration=20, cooldown=10, pose='sleep', effects={'energy': 25, 'mood': 3}),
    'tap': dict(label='轻拍一下', duration=3, cooldown=30, pose='shy', effects={'mood': -6, 'bond': -2}),
    'dance': dict(label='跳支舞', duration=DANCE_SECONDS, cooldown=0, pose='idle', effects={}),
}

def make_writable(path):
    """Clear the Windows read-only flag that WeChat puts on files in its received-file folder.

    os.replace onto a read-only target fails with WinError 5 even when the folder is writable.
    """
    if os.name == 'nt' and path.exists() and not os.access(path, os.W_OK):
        path.chmod(stat.S_IREAD | stat.S_IWRITE)


class PetState:
    def __init__(self):
        self.values = dict(food=65., water=65., energy=80., mood=75., bond=10.)
        self.companion_seconds = 0.
        self.toilet_seconds = 0.
        self.stage = 0
        self.unlocked_stage = 0
        self.outfit = 'blue'
        self.scene = 'home'
        self.window_position = None
        self.keyboard_enabled = True
        self.flames = True
        self.break_reminders = True
        self.update_checks = True
        self.cooldowns = {}
        self.completed = 0
        self.created = time.time()

    def tick(self, seconds, active):
        seconds = min(max(seconds, 0), 10)
        self.toilet_seconds=min(TOILET_FULL_SECONDS,self.toilet_seconds+seconds)
        if active:
            self.companion_seconds += seconds
        for key, hourly in [('food', 3), ('water', 4), ('energy', 1), ('mood', .5)]:
            self.values[key] = max(0, self.values[key] - seconds * hourly / 3600)
        self.promote()

    def promote(self):
        for i, (seconds, bond, _) in enumerate(STAGES):
            if self.companion_seconds >= seconds and self.values['bond'] >= bond:
                self.unlocked_stage = max(self.unlocked_stage, i)

    def select_stage(self, stage):
        if type(stage) is not int or stage not in range(len(STAGES)):
            return '没有这个成长形态'
        if stage > self.unlocked_stage:
            return '这个形态还没有解锁'
        self.stage = stage
        return ''

    def growth_progress(self):
        if self.unlocked_stage == len(STAGES)-1:
            return '全部已解锁，选择你想陪伴的模样'
        seconds,bond,title=STAGES[self.unlocked_stage+1]
        minutes=math.ceil(max(0,seconds-self.companion_seconds)/60)
        hours,minutes=divmod(minutes,60)
        remaining=[]
        if hours or minutes:remaining.append(f'陪伴 {hours}小时{minutes:02d}分')
        if self.values['bond']<bond:remaining.append(f'亲密 {math.ceil(bond-self.values["bond"])}')
        return title+'还差：'+' · '.join(remaining)

    def growth_fraction(self):
        if self.unlocked_stage==len(STAGES)-1:return 1.
        start=STAGES[self.unlocked_stage][0]
        end=STAGES[self.unlocked_stage+1][0]
        return min(1.,max(0.,(self.companion_seconds-start)/(end-start)))

    def need_level(self,key):
        if key!='toilet':return self.values[key]
        points=((0,100),(TOILET_REMIND_SECONDS,NEED_LOW),(TOILET_URGENT_SECONDS,NEED_CRITICAL),(TOILET_FULL_SECONDS,0))
        for (start,high),(end,low) in zip(points,points[1:]):
            if self.toilet_seconds<=end:
                return high-(high-low)*(self.toilet_seconds-start)/(end-start)
        return 0.

    def low_needs(self):
        return tuple(sorted((key for key in NEEDS if self.need_level(key)<NEED_LOW or key=='toilet' and self.toilet_seconds>=TOILET_REMIND_SECONDS),key=self.need_level))

    def urgent_needs(self):
        return tuple(key for key in self.low_needs() if self.need_level(key)<NEED_CRITICAL or key=='toilet' and self.toilet_seconds>=TOILET_URGENT_SECONDS)

    def need_text(self):
        needs=self.low_needs()
        if not needs:return ''
        if needs==('toilet',):
            return '憋得好急，带我上厕所吧' if self.urgent_needs() else '想上厕所啦，带我去一下吧'
        prefix='急需' if self.urgent_needs() else '我需要'
        return prefix+'、'.join(NEEDS[key][1] for key in needs)

    def check(self, action, now):
        if action not in ACTIONS:
            return '没有这个互动'
        remaining = ACTIONS[action]['cooldown'] - (now - self.cooldowns.get(action, -1e20))
        if ACTIONS[action]['cooldown'] and remaining > 0:
            return f'让她缓一缓，{math.ceil(remaining)} 秒后再来'
        if action in ('feed', 'snack') and self.values['food'] >= 95:
            return '已经吃饱啦，稍后再喂吧'
        if action == 'water' and self.values['water'] >= 95:
            return '现在不渴，水碗已经备好啦'
        if action == 'toilet' and self.toilet_seconds<TOILET_MIN_INTERVAL:
            return '暂时还不需要上厕所，等一会儿吧'
        if action in ('walk', 'ball', 'toy'):
            urgent=self.urgent_needs()
            if urgent:
                return '先'+NEEDS[urgent[0]][1]+'，再一起玩吧'
        if action == 'sleep' and self.values['energy'] >= 98:
            return '现在精神很好，陪她玩一会儿吧'
        return ''

    def finish(self, action, now, *, already_started=False):
        if not already_started:
            error = self.check(action, now)
            if error:
                return error
        for key, value in ACTIONS[action]['effects'].items():
            self.values[key] = min(100, max(0, self.values[key] + value))
        if action=='toilet':self.toilet_seconds=0.
        self.cooldowns[action] = now
        self.completed += 1
        self.promote()
        return ''

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {'version': 1, **self.__dict__}
        temp = path.with_suffix('.tmp')
        make_writable(temp)
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        for attempt in range(SAVE_REPLACE_ATTEMPTS):
            make_writable(path)
            try:
                temp.replace(path)
                return
            except PermissionError:
                if attempt == SAVE_REPLACE_ATTEMPTS-1:
                    raise
                time.sleep(SAVE_RETRY_SECONDS)

    @classmethod
    def load(cls, path):
        state = cls()
        if not Path(path).exists():
            return state
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('values'), dict) or not isinstance(data.get('cooldowns'), dict):
            raise ValueError('存档结构不合法')
        if data.get('version') != 1:
            raise ValueError('不支持的存档版本')
        def number(value, low, high):
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError('存档数值不合法')
            return value
        state.values = {key: number(data['values'][key], 0, 100) for key in state.values}
        state.companion_seconds = number(data['companion_seconds'], 0, 1e12)
        state.toilet_seconds = number(data.get('toilet_seconds',0.),0,TOILET_FULL_SECONDS)
        state.stage = data['stage']
        if type(state.stage) is not int or state.stage not in range(len(STAGES)):
            raise ValueError('成长阶段不合法')
        # Legacy saves used stage for both appearance and earned growth.
        state.unlocked_stage = data.get('unlocked_stage', state.stage)
        if type(state.unlocked_stage) is not int or state.unlocked_stage not in range(len(STAGES)) or state.stage>state.unlocked_stage:
            raise ValueError('已解锁阶段不合法')
        state.outfit, state.scene = data['outfit'], data['scene']
        if state.outfit not in OUTFITS or state.scene not in SCENES:
            raise ValueError('装扮或场景不合法')
        position = data.get('window_position')
        if isinstance(position,list) and len(position)==2 and all(type(value) is int for value in position):
            state.window_position = tuple(position)
        for key in ('keyboard_enabled', 'flames'):
            if type(data[key]) is not bool:
                raise ValueError('设置不合法')
            setattr(state, key, data[key])
        if type(data.get('break_reminders', True)) is not bool:
            raise ValueError('休息提醒设置不合法')
        state.break_reminders = data.get('break_reminders', True)
        if type(data.get('update_checks', True)) is not bool:
            raise ValueError('检查更新设置不合法')
        state.update_checks = data.get('update_checks', True)
        state.cooldowns = {key: number(value, 0, 1e12) for key, value in data['cooldowns'].items() if key in ACTIONS}
        state.completed = number(data['completed'], 0, 1e12)
        state.created = number(data['created'], 0, 1e12)
        state.promote()
        return state
