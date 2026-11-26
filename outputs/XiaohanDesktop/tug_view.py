"""Draw the original red toy with a moveable grip for the user's end."""
import math
from statistics import median
from PIL import Image

from desktop_platform import UI_FONT
from fetch_game import ramp
from trip_view import INK, TEAL, draw_scene_button, pill
from tug_game import GREEN_START, GREEN_END

TUG_SIZE = (384, 314)
TUG_EXIT = (304, 9, 372, 41)
TUG_RETRY = (270, 259, 368, 299)
POSE_STEPS = 24
RESULT_TEXT = {'player':'你拉赢啦！', 'dog':'小汉赢了这轮！', 'tie':'这轮打成平手！',
               'idle':'踩准绿区才有拉力'}
TAP_TEXT = {'perfect':'正中节拍！','hit':'拉住了！','early':'这拍按早了','late':'这拍按晚了'}


def toy_tip(image):
    # The dangling end is the rightmost red cloth in the play pose.
    pixels = image.load()
    candidates = []
    for y in range(image.height*3//5,image.height):
        for x in range(image.width*2//3,image.width):
            r,g,b,a = pixels[x,y]
            if a>=128 and r>g+32 and r>b+25:
                candidates.append((x,y))
    tip = max(x for x,_ in candidates)
    return tip,median(y for x,y in candidates if x>=tip-6)


def tug_pose(image, lean):
    """Move the body in either direction while pinning the painted feet."""
    if not lean:
        return image
    width,height = image.size
    xs = (*range(0,width,8),width)
    ys = (*range(0,height,8),height)
    nodes = {}
    for y in ys:
        for x in xs:
            hip = (1-ramp(x,70,119))*(1-ramp(y,164,208))
            neck = ramp(x,80,128)*(1-ramp(y,188,225))
            cloth = ramp(x,175,202)*ramp(y,188,226)
            if lean>0:
                dx=9*hip+29*neck+15*cloth
                dy=-25*hip+25*neck+13*cloth
            else:
                # The shoulder and muzzle give more than the tip of the toy.
                # Keep the end of the painted cloth clear of the sprite edge.
                cloth_travel=16-9*ramp(x,200,244)
                dx=7*hip+31*neck+cloth_travel*cloth
                dy=2*hip+9*neck+3*cloth
            nodes[x,y] = (x+lean*dx,y+lean*dy)
    mesh = []
    for top,bottom in zip(ys,ys[1:]):
        for left,right in zip(xs,xs[1:]):
            mesh.append(((left,top,right,bottom),
                         (*nodes[left,top],*nodes[left,bottom],*nodes[right,bottom],*nodes[right,top])))
    return image.transform(image.size,Image.Transform.MESH,mesh,Image.Resampling.BILINEAR)


def draw_tug(canvas, sprite, size, tip, rest_tip, game, paused, blocked=''):
    center = 130 + 23*game.advantage+6*game.reach
    baseline = 241
    canvas.create_oval(center-58,baseline-15,center+55,baseline-3,fill='#e4e6d9',outline='')
    canvas.create_image(center,baseline,image=sprite,anchor='s',tags='tug_pet')
    left = center-size/2
    join_x = left + tip[0]*size/256
    join_y = baseline-size + tip[1]*size/256
    grip_x = min(TUG_SIZE[0]-28,left+rest_tip[0]*size/256+49+game.pull*35+game.advantage*9)
    grip_y = baseline-size+rest_tip[1]*size/256-8-game.pull*10
    sag = 9*(1-max(game.reach,game.brace))
    cord = (join_x-5,join_y, (join_x+grip_x)/2, (join_y+grip_y)/2+sag, grip_x-10,grip_y)
    canvas.create_line(*cord,fill='#733b36',width=12,smooth=True,capstyle='round',tags='tug_cord')
    canvas.create_line(*cord,fill='#c4514d',width=8,smooth=True,capstyle='round')
    canvas.create_line(*cord,fill='#e07867',width=2,smooth=True,capstyle='round')
    grip = (grip_x-15,grip_y-13,grip_x+15,grip_y+13)
    canvas.create_oval(*grip,fill='#fff4da',outline='#b44b45',width=6,tags='tug_grip')
    if game.pull>.18 and not paused:
        canvas.create_oval(grip_x-18,grip_y-16,grip_x+18,grip_y+16,outline='#f4d79b',width=2)

    pill(canvas,(12,10,287,70))
    canvas.create_text(27,25,text='拔玩具',anchor='w',fill=INK,font=(UI_FONT,12,'bold'))
    remaining = math.ceil(game.duration-game.elapsed)
    if game.elapsed>0 and game.result is None:
        canvas.create_text(270,25,text=f'剩 {remaining} 秒',anchor='e',fill=INK,font=(UI_FONT,9))
    streak=game.best_combo if game.result else game.combo
    if streak>=2:
        combo_text=f'最高 {streak} 连击' if game.result else f'{streak} 连击'
        canvas.create_text(149,25,text=combo_text,fill='#a34733',font=(UI_FONT,11,'bold'),tags='tug_combo')
    canvas.create_text(29,51,text='小汉',anchor='w',fill=INK,font=(UI_FONT,9))
    canvas.create_text(269,51,text='你',anchor='e',fill=INK,font=(UI_FONT,9))
    canvas.create_line(65,51,240,51,fill='#e0e9de',width=8,capstyle='round')
    middle = (65+240)/2
    canvas.create_line(middle,44,middle,58,fill='#839b91',width=1)
    marker = middle+game.advantage*80
    canvas.create_oval(marker-6,45,marker+6,57,fill=TEAL,outline='#fffaf0',width=1,tags='tug_score')
    draw_scene_button(canvas,TUG_EXIT,'× 退出','tug_exit')

    if paused:
        return
    if game.result:
        box = (13,259,260,299) if game.result=='idle' else (65,259,319,299)
        draw_scene_button(canvas,box,RESULT_TEXT[game.result],'tug_status')
        if game.result=='idle':
            draw_scene_button(canvas,TUG_RETRY,'再试一次','tug_retry')
        return

    pill(canvas,(12,248,372,306))
    message = blocked or ('按空格继续' if game.started else '按空格开始')
    timing_ready = game.running and not game.feedback and GREEN_START<=game.phase<=GREEN_END
    if game.running:
        message=TAP_TEXT.get(game.feedback,'现在按空格！' if timing_ready else '指针进绿区时按空格')
    color = TEAL if timing_ready or game.feedback in ('perfect','hit') else INK
    canvas.create_text(192,265,text=message,fill=color,font=(UI_FONT,10,'bold'),tags='tug_status')
    left,right,y = 34,350,288
    canvas.create_line(left,y,right,y,fill='#dce5db',width=9,capstyle='round',tags='tug_timing')
    glow = '#55a48a' if timing_ready else '#82b8a1'
    canvas.create_line(left+(right-left)*GREEN_START,y,left+(right-left)*GREEN_END,y,
                       fill=glow,width=9,capstyle='round',tags='tug_timing')
    marker = left+(right-left)*game.phase
    canvas.create_oval(marker-5,y-5,marker+5,y+5,fill='#fff9e9',outline=TEAL,width=2,tags='tug_beat')
