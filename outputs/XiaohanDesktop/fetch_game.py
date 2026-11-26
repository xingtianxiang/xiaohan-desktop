"""Ground-plane perspective and a continuous fetch animation."""
from dataclasses import dataclass
import math
from PIL import Image, ImageDraw, ImageFilter
from animation import HEAD_FRAMES, STEP_FRAMES

CHARGE_SECONDS = 2.
WALK_CYCLE_SECONDS = 15.


def walk_position(elapsed):
    phase=elapsed/WALK_CYCLE_SECONDS*2*math.pi
    return 210-92*math.cos(phase),246.,math.sin(phase)<0


class ThrowCharge:
    def __init__(self):
        self.started = None

    def begin(self, now):
        if self.started is not None:
            return False
        self.started = now
        return True

    def power(self, now):
        return 0. if self.started is None else min(1., max(0., (now-self.started)/CHARGE_SECONDS))

    def release(self, now):
        if self.started is None:
            return None
        power = self.power(now)
        self.cancel()
        return power

    def cancel(self):
        self.started = None


def throw_point(flight, power):
    t = min(1., max(0., flight))
    power = min(1., max(0., power))
    depth = .18+.82*power
    x = 165+(210+130*power-165)*t
    ground = 260+(254-100*depth-260)*t
    radius = 11*(1-.62*depth*t)
    height = 30+75*power
    return x, ground-radius-4*height*t*(1-t), ground, radius


def ramp(value, start, end):
    t = min(1., max(0., (value-start)/(end-start)))
    return t*t*(3-2*t)


def return_distance(progress):
    """Distance for a short push-off, steady trot, then a longer brake."""
    t = min(1., max(0., (progress-.63)/.27))
    push, brake = .18, .28
    travel = 1-(push+brake)/2
    if t < push:
        return t*t/(2*push*travel)
    if t > 1-brake:
        return 1-(1-t)**2/(2*brake*travel)
    return (t-push/2)/travel


@dataclass(frozen=True)
class FetchFrame:
    x: float
    ground: float
    scale: float
    flip: bool
    ball_x: float
    ball_y: float
    ball_ground: float
    radius: float
    carrying: bool
    message: str
    pose: str
    previous_pose: str
    mix: float
    chase_flip: bool
    return_flip: bool
    origin_flip: bool
    previous_flip: bool
    stride_phase: float
    chase_cycles: float
    previous_offset: tuple
    current_offset: tuple
    ball_opacity: float
    gait_frame: int | None
    gait_weight: float


def fetch_frame(progress,power,body_size,anchors,origin=(118.,246.,False)):
    p = min(1., max(0., progress))
    power = min(1., max(0., power))
    depth = .18+.82*power
    ox,oground,oflip=origin
    target_ball,_,target_ground,_=throw_point(1,power)
    chase_flip=target_ball<ox
    returning_flip=ox<target_ball
    direction=-1 if chase_flip else 1
    far_scale=1-.62*depth
    pickup=anchors['pickup']
    radius_base=body_size*pickup['radius']
    far_size=body_size*far_scale
    target_pet=target_ball-direction*far_size*pickup['ball'][0]
    target_body_ground=target_ground+far_size*(pickup['ball'][1]-pickup['radius'])
    outbound=ramp(p,.06,.44)
    inbound=return_distance(p)
    scale=1-(1-far_scale)*outbound*(1-inbound)
    size=body_size*scale
    x=ox+(target_pet-ox)*outbound
    ground=oground+(target_body_ground-oground)*outbound
    bx,by,ball_ground,old_radius=throw_point(p/.30,power)
    radius=radius_base*(old_radius/11)
    by+=old_radius-radius
    if .30 <= p < .42:
        by -= 16*(1-(p-.30)/.12)*abs(math.sin((p-.30)/.12*math.pi*2))
    distance=math.hypot(ox-target_pet,oground-target_body_ground)
    # One four-pose trot cycle covers about half a body length. Integrating
    # perspective scale ties foot cadence to travel, including braking.
    cycles=distance/body_size/.50*(-math.log(far_scale)/(1-far_scale))
    chase_cycles = -math.log1p(-(1-far_scale)*outbound) * distance / (body_size*.50*(1-far_scale))
    # End on the gathered paws; avoid adding an extra half stride to every trip.
    stride_total=max(0,round(cycles-.5))*4+2
    stride_phase=stride_total*math.log((far_scale+(1-far_scale)*inbound)/far_scale)/(-math.log(far_scale))
    step=math.floor(stride_phase)
    pose='walk';previous='origin_walk';mix=ramp(p,0,.08);flip=chase_flip;previous_flip=oflip
    gait_frame = None
    gait_weight = 1.
    if .36 <= p < .44:
        gait_frame = round((HEAD_FRAMES-1)*ramp(p,.375,.44))
        gait_weight = ramp(p,.36,.393)
    previous_offset = current_offset = (0., 0.)
    if p>=.44:
        # Follow the weight transfer around the planted paws before pushing off.
        pivot = ramp(p, .455, .65)
        arc = math.sin(math.pi * pivot) ** 2
        pivot_x = direction * size * .09 * arc
        pivot_ground = size * .035 * arc
        if p<.50:
            pose,previous,flip,previous_flip='pickup','walk',chase_flip,chase_flip
            mix=ramp(p,.44,.50)
        elif p<.55:
            pose,previous,flip,previous_flip='turnquarter','pickup',chase_flip,chase_flip
            mix=ramp(p,.50,.55)
        elif p<.59:
            pose,previous,flip,previous_flip='turnfront','turnquarter',chase_flip,chase_flip
            mix=ramp(p,.55,.59)
        elif p<.63:
            pose,previous,flip,previous_flip='turnquarter','turnfront',returning_flip,chase_flip
            mix=ramp(p,.59,.63)
        elif p<.90:
            pose='run'+str(step%4)
            previous='turnquarter' if step == 0 else 'run'+str((step-1)%4)
            flip=previous_flip=returning_flip
            mix=ramp(stride_phase-step,0.,1.)
            if step:
                mix=stride_phase-step
                gait_frame = 2*HEAD_FRAMES + (step%4)*STEP_FRAMES + round((STEP_FRAMES-1)*(stride_phase-step))
        else:
            # Finish the current stride before lowering the ball, without a
            # sudden change back to the other foot at the arrival boundary.
            pose='drop';previous='run1'
            flip=previous_flip=returning_flip;mix=ramp(p,.90,.923)
            if p>=.97:
                pose,previous,flip,previous_flip='settle','pickup',oflip,returning_flip
                mix=ramp(p,.97,1.)
        if p>=.63:
            bend=math.sin(math.pi*inbound)**2
            bend_width=min(size*.08,abs(ox-target_pet)*.12)
            x=target_pet+(ox-target_pet)*inbound+(-1 if returning_flip else 1)*bend_width*bend
            ground=target_body_ground+(oground-target_body_ground)*inbound+4*bend
        x += pivot_x
        ground += pivot_ground

        def ball_at(key,mirrored):
            key = {'drop':'turnquarter','settle':'pickup'}.get(key,key)
            anchor=anchors[key]
            return (x+(-1 if mirrored else 1)*size*anchor['ball'][0],
                    ground-size*anchor['ball'][1],size*anchor['radius'])
        current=ball_at(pose,previous_flip if pose=='settle' else flip)
        old=(target_ball,target_ground-radius,radius) if previous=='walk' else ball_at(previous,previous_flip)
        bx,by,radius=(a+(b-a)*mix for a,b in zip(old,current))
        if p < .55 or .923 <= p < .97:
            raised = ramp(p,.455,.55) if p<.55 else 1-ramp(p,.923,.97)
            gait_frame = HEAD_FRAMES + round((HEAD_FRAMES-1)*raised)
            low,high = ball_at('pickup',flip),ball_at('turnquarter',flip)
            bx,by,radius = (a+(b-a)*raised for a,b in zip(low,high))
            bow = math.sin(math.pi*raised) if raised<.5 else 2*(1-raised)
            bx += (-1 if flip else 1)*size*.035*bow
        if previous in anchors and pose in anchors:
            # These drawings already contain the ball. Register both mouths to
            # one moving point so blending legs never creates a second ball.
            previous_offset = (bx-old[0], by-old[1])
            current_offset = (bx-current[0], by-current[1])
        ball_ground=ground
    carrying=pose not in ('walk','settle')
    message=('看球！我来啦' if p<.44 else '叼起来啦' if p<.55 else '转个身，回来啦' if p<.63 else '给你带回来啦～' if p<.90 else '放这里，再扔一球吧！')
    return FetchFrame(x,ground,scale,flip,bx,by,ball_ground,radius,carrying,message,pose,previous,mix,chase_flip,returning_flip,oflip,previous_flip,stride_phase,chase_cycles,previous_offset,current_offset,1.-ramp(p,.985,1.),gait_frame,gait_weight)


def paint_ball(frame, sample, shadow=True):
    """Render at 3x for a soft edged ball with a grounded, height-aware shadow."""
    # Supersample only the ball and its shadow, including the blur fringe.
    height = max(0, sample.ball_ground-sample.ball_y)
    reach = sample.radius*(1+height/150) + 6
    left = math.floor(sample.ball_x-reach)
    top = math.floor(sample.ball_y-sample.radius-6)
    width = math.ceil(sample.ball_x+reach)-left
    bottom = math.ceil(max(sample.ball_y+sample.radius, sample.ball_ground+sample.radius*.28)+6)
    tile_size = (width, bottom-top)
    layer = Image.new('RGBA', (width*3, (bottom-top)*3))
    draw = ImageDraw.Draw(layer)
    x,y,r = (sample.ball_x-left)*3,(sample.ball_y-top)*3,sample.radius*3
    if shadow:
        shade = Image.new('RGBA', layer.size)
        d = ImageDraw.Draw(shade)
        sy = (sample.ball_ground-top)*3
        spread = r*(1+height/150)
        d.ellipse((x-spread,sy-r*.28,x+spread,sy+r*.28), fill=(52,65,38,round(70/(1+height/40))))
        layer.alpha_composite(shade.filter(ImageFilter.GaussianBlur(3)))
        draw = ImageDraw.Draw(layer)
    draw.ellipse((x-r,y-r,x+r,y+r),fill='#e6a15b',outline='#a66d40',width=3)
    draw.arc((x-r*.65,y-r,x+r*.4,y+r),70,280,fill='#fff2c4',width=max(2,round(r*.18)))
    draw.ellipse((x-r*.45,y-r*.6,x-r*.05,y-r*.2),fill='#ffe1a1')
    tile = layer.resize(tile_size,Image.Resampling.LANCZOS)
    if sample.ball_opacity < 1:
        tile.putalpha(tile.getchannel('A').point(lambda alpha: round(alpha*sample.ball_opacity)))
    frame.alpha_composite(tile, (left, top))
