"""Tug of war with one timed strike per beat."""
import math

BEAT_SECONDS = 1.12
GREEN_START = .57
GREEN_END = .85
BEAT_CENTER = (GREEN_START+GREEN_END)/2
COMBO_STEP = .028
COMBO_BONUS_STEPS = 3


class TugRound:
    def __init__(self, duration):
        self.duration = duration
        self.elapsed = 0.
        self.advantage = 0.
        self.pull = 0.
        self.brace = 0.
        self.hits = 0
        self.combo = 0
        self.best_combo = 0
        self.result = None
        self.started = False
        self.running = False
        self.previous = None
        self.impulse = 0.
        self.last_beat = -1
        self.last_feedback = ''

    @property
    def beat(self):
        return int(self.elapsed/BEAT_SECONDS)

    @property
    def phase(self):
        return self.elapsed/BEAT_SECONDS-self.beat

    @property
    def feedback(self):
        return self.last_feedback if self.last_beat==self.beat else ''

    @property
    def surge(self):
        return max(0., math.sin(self.elapsed*math.tau/2.7+.5))**4

    @property
    def reach(self):
        return min(1.,1.65*self.pull)

    @property
    def lean(self):
        return self.brace*(1-self.reach)-self.reach

    def strike(self, now):
        if self.result is not None:
            return False
        if not self.running:
            self.started=self.running=True
            self.previous=now
            return True
        if self.beat==self.last_beat:
            return False
        self.last_beat=self.beat
        phase=self.phase
        if phase<GREEN_START:
            self.last_feedback='early'
            self.combo=0
        elif phase>GREEN_END:
            self.last_feedback='late'
            self.combo=0
        else:
            accuracy=1-abs(phase-BEAT_CENTER)/(GREEN_END-BEAT_CENTER)
            self.last_feedback='perfect' if accuracy>=.65 else 'hit'
            self.hits+=1
            self.combo+=1
            self.best_combo=max(self.best_combo,self.combo)
            bonus=min(COMBO_BONUS_STEPS,self.combo-1)*COMBO_STEP
            self.advantage=min(1.,self.advantage+.32+.13*accuracy+bonus)
            self.impulse=.82+.35*accuracy+bonus
        return True

    def pause(self):
        self.running=False
        if self.result is None:
            self.impulse=0.

    def advance(self, now):
        dt = 0. if self.previous is None else min(.10, max(0., now-self.previous))
        self.previous = now
        self.pull+=(self.impulse-self.pull)*(1-math.exp(-17*dt))
        self.impulse*=math.exp(-4.5*dt)
        surge=self.surge
        brace_target = (.13+.87*surge) if self.running else 0.
        self.brace += (brace_target-self.brace)*(1-math.exp(-16*dt))
        if not self.running:
            return False
        self.elapsed = min(self.duration, self.elapsed+dt)
        if self.combo and (self.beat>self.last_beat+1
                           or self.beat>self.last_beat and self.phase>GREEN_END):
            self.combo=0
        if self.advantage<1.:
            self.advantage=max(-1.,self.advantage-(.145+.23*surge)*dt)
        if -1. < self.advantage < 1. and self.elapsed < self.duration:
            return False
        if not self.hits:
            self.result = 'idle'
        elif self.advantage > .12:
            self.result = 'player'
        elif self.advantage < -.12:
            self.result = 'dog'
        else:
            self.result = 'tie'
        self.pause()
        return True
