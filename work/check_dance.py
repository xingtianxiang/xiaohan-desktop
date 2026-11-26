"""Use the actual dance entry and export the same frames the app renders."""
import ctypes
import json
from pathlib import Path
import sys
import time
import tkinter as tk

from PIL import Image, ImageChops

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet
from dance import CAT_ENTRANCE, DanceRoutine, SECONDS_PER_BEAT
from model import DANCE_SECONDS, PetState

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
root=tk.Tk()
root.withdraw()
state=PetState()
state.stage=state.unlocked_stage=2
state.save(out/'pet.json')
app=DesktopPet(root,out/'pet.json')
app.keyboard.stop()
root.deiconify()
root.update()
results=[]


def check(name,condition):
    results.append(dict(name=name,passed=bool(condition)))
    if not condition:
        raise AssertionError(name)


def wait(ms):
    done=tk.BooleanVar(root)
    root.after(ms,lambda:done.set(True))
    root.wait_variable(done)


try:
    app.popup()
    root.update()
    check('dance_entry_in_more',app.more.actions['dance'].winfo_ismapped())
    app.more.actions['dance'].invoke()
    app.render(time.monotonic())
    check('dance_renders_on_pet_canvas',app.action=='dance' and app.more is None
          and app.desktop.find_withtag('dance_stage'))
    routine=app.dance_routines['blue_adult']
    width,height=app.width,app.height
    check('cat_art_loads',routine.partner is not None)
    solo=DanceRoutine(routine.dog.standing,stage=2)
    before_entrance=(CAT_ENTRANCE-.1)*SECONDS_PER_BEAT
    check('opening_is_a_solo',routine.frame(before_entrance,width,height).tobytes()
          ==solo.frame(before_entrance,width,height).tobytes())
    duet=routine.frame(5.58,width,height)
    right_half=(width*2//3,40,width-4,height-30)
    check('cat_revealed_on_right',ImageChops.difference(
        duet.crop(right_half).convert('RGB'),
        solo.frame(5.58,width,height).crop(right_half).convert('RGB')).getbbox())
    resting=routine.partner.pose(0,0,0)
    lifting=routine.partner.pose(0,0,42)
    front_paws=(0,209,110,256)
    check('cat_lifts_one_front_paw',resting.getchannel('A').crop(front_paws).tobytes()
          !=lifting.getchannel('A').crop(front_paws).tobytes()
          and resting.getchannel('A').crop((73,236,95,244)).tobytes()
          ==lifting.getchannel('A').crop((73,236,95,244)).tobytes())
    interval=40
    frames=[]
    for i in range(1000*DANCE_SECONDS//interval):
        frame=routine.frame(i*interval/1000,width,height)
        backdrop=Image.new('RGBA',(width,height),'#121019')
        frames.append(Image.alpha_composite(backdrop,frame).convert('RGB'))
    palette_sample=Image.new('RGB',(width,8*height))
    for i in range(8):
        palette_sample.paste(frames[len(frames)*i//8],(0,i*height))
    palette=palette_sample.quantize(colors=256)
    encoded=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    encoded[0].save(sys.argv[2],save_all=True,append_images=encoded[1:],duration=interval,
                    loop=0,disposal=2,optimize=False)
    sheet=Image.new('RGB',(width*3,height*2))
    for index,elapsed in enumerate((.27,1.4,2.77,4.16,5.12,6.46)):
        sheet.paste(frames[round(elapsed*1000/interval)],(width*(index%3),height*(index//3)))
    sheet.save(out/'frames.png')
    check('dance_frames_have_distinct_motion',len(set(frame.tobytes() for frame in frames))>160)
    with Image.open(sys.argv[2]) as recording:
        elapsed=0
        for index in range(recording.n_frames):
            recording.seek(index)
            elapsed+=recording.info['duration']
        check('export_is_eight_seconds',elapsed==DANCE_SECONDS*1000)

    app.toggle_pause()
    before=app.pause_started-app.action_started
    wait(140)
    app.toggle_pause()
    check('pause_resumes_same_dance_position',abs(time.monotonic()-app.action_started-before)<.11)
    app.escape_fetch()
    check('escape_cancels_without_completion',app.action is None and app.state.completed==0)
    check('dance_can_be_replayed',app.start_action('dance'))
    app.action_started=time.monotonic()-DANCE_SECONDS-.2
    wait(180)
    check('finished_dance_returns_to_pet',app.action is None and app.state.completed==1
          and app.desktop.find_withtag('pet_sprite'))
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    app.close()

print(json.dumps(dict(passed=len(results),checks=results),ensure_ascii=False))
