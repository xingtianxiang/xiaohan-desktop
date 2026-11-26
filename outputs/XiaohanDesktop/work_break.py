"""Session-local work reminder driven by elapsed time and Windows input idle time."""
import math

WORK_SECONDS = 60 * 60
BREAK_SECONDS = 10 * 60
SNOOZE_SECONDS = 5 * 60
ACTIVE_IDLE_SECONDS = 60


class WorkBreak:
    def __init__(self):
        self.work = 0.
        self.idle = 0.
        self.previous = None
        self.next_reminder = WORK_SECONDS

    @property
    def due(self):
        return self.work >= self.next_reminder

    def update(self, now, idle, enabled=True):
        dt = 0 if self.previous is None else max(0., now-self.previous)
        self.previous = now
        self.idle = max(0., idle) if idle is not None else 0.
        if not enabled:
            self.work = 0.
            self.next_reminder = WORK_SECONDS
            return
        if idle is None:
            return
        if idle >= BREAK_SECONDS:
            self.work = 0.
            self.next_reminder = WORK_SECONDS
        elif dt <= 5 and idle < ACTIVE_IDLE_SECONDS:
            # A suspended/blocked UI must not turn its time gap into work.
            self.work += dt

    def snooze(self):
        self.next_reminder = self.work + SNOOZE_SECONDS

    def text(self):
        if self.work >= WORK_SECONDS and self.idle >= ACTIVE_IDLE_SECONDS:
            return f'安心休息，还差 {math.ceil(max(0, BREAK_SECONDS-self.idle)/60)} 分钟'
        if self.due:
            return '工作一阵子啦，陪我休息 10 分钟吧'
        return f'再工作 {math.ceil(max(0, self.next_reminder-self.work)/60)} 分钟，休息 10 分钟'
