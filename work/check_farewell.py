"""Record the actual exit command and verify the existing save and close behavior."""
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import time
import tkinter as tk

from PIL import Image, ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet
from farewell import FAREWELL_SECONDS
from model import PetState

ctypes.windll.shcore.SetProcessDpiAwareness(1)
out=Path(sys.argv[1])
out.mkdir(parents=True,exist_ok=True)
root=tk.Tk()
root.withdraw()
state=PetState()
state.stage=state.unlocked_stage=2
state.window_position=((root.winfo_screenwidth()-280)//2,80)
state.save(out/'pet.json')
app=DesktopPet(root,out/'pet.json')
root.deiconify()
root.update()
results=[]


def check(name,condition):
    results.append(dict(name=name,passed=bool(condition)))
    if not condition:
        raise AssertionError(name)


def capture_box(canvas):
    user=ctypes.windll.user32
    user.GetClientRect.argtypes=[W.HWND,ctypes.POINTER(W.RECT)]
    user.ClientToScreen.argtypes=[W.HWND,ctypes.POINTER(W.POINT)]
    bounds=W.RECT()
    origin=W.POINT()
    hwnd=canvas.winfo_id()
    if not user.GetClientRect(hwnd,ctypes.byref(bounds)) or not user.ClientToScreen(hwnd,ctypes.byref(origin)):
        raise RuntimeError('无法定位告别窗口')
    return origin.x,origin.y,origin.x+bounds.right,origin.y+bounds.bottom


try:
    check('care_is_in_progress_before_exit',app.start_action('water'))
    app.toggle_pause()
    app.popup(page='settings')
    root.update()
    check('real_settings_exit_button_is_mapped',app.more.exit_button.winfo_ismapped())
    values_before=app.state.values.copy()
    app.more.exit_button.invoke()
    farewell=app.farewell
    check('exit_starts_visible_farewell',app.closing and app.more is None and not app.desktop.winfo_manager()
          and farewell.canvas.find_withtag('farewell_caption'))
    saved=PetState.load(app.data_path)
    check('saves_before_animation_and_does_not_finish_interrupted_care',
          saved.values==values_before and saved.completed==0 and not saved.cooldowns)
    app.request_exit()
    check('repeated_exit_does_not_restart_the_animation',app.farewell is farewell)

    # Use an opaque background only for the bounded recording of this canvas.
    root.wm_attributes('-transparentcolor','')
    farewell.canvas.configure(bg='#f5f2ea')
    root.lift()
    root.update_idletasks()
    box=capture_box(farewell.canvas)
    frames=[]
    times=[]
    widths=[]
    heart_seen=False
    closed=[]

    def record():
        global heart_seen
        timestamp=time.monotonic()-farewell.started
        if timestamp>=FAREWELL_SECONDS:
            return
        heart_seen=heart_seen or bool(farewell.canvas.find_withtag('farewell_heart'))
        widths.append(farewell.picture.width())
        frames.append(ImageGrab.grab(bbox=box,all_screens=True).convert('RGB'))
        times.append(timestamp)
        root.after(24,record)

    root.bind('<Destroy>',lambda event:closed.append(time.monotonic()) if event.widget==root else None)
    root.after(4800,root.destroy)
    record()
    root.mainloop()
    check('window_destroys_after_the_farewell',len(closed)==1
          and FAREWELL_SECONDS<=closed[0]-farewell.started<3.2
          and app.keyboard.stopped.is_set() and not app.keyboard.thread.is_alive())
    check('animated_heart_and_final_shrink_are_visible',heart_seen and widths[0]==240 and min(widths)<80)
    check('save_stays_unchanged_until_exit',PetState.load(app.data_path).__dict__==saved.__dict__)

    width,height=frames[0].size
    cream=(245,242,234)
    corners=((4,4),(width-5,4),(4,height-5),(width-5,height-5))
    check('recording_has_the_complete_canvas',len(frames)>20 and (width,height)==(280,300)
          and all(max(abs(a-b) for a,b in zip(frame.getpixel(point),cream))<12
                  for frame in frames for point in corners))
    palette_sample=Image.new('RGB',(width,height*5),cream)
    for i in range(4):
        palette_sample.paste(frames[i*(len(frames)-1)//3],(0,height*i))
    palette=palette_sample.quantize(colors=256)
    frames.append(Image.new('RGB',(width,height),cream))
    encoded=[frame.quantize(palette=palette,dither=Image.Dither.NONE) for frame in frames]
    intervals=[max(10,10*round(100*(b-a))) for a,b in zip(times,times[1:])]
    intervals.extend([max(10,10*round(100*(FAREWELL_SECONDS-times[-1]))),450])
    encoded[0].save(sys.argv[2],save_all=True,append_images=encoded[1:],duration=intervals,
                    loop=0,disposal=2,optimize=False)
finally:
    (out/'result.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')

print(json.dumps(dict(passed=len(results),checks=results),ensure_ascii=False))
