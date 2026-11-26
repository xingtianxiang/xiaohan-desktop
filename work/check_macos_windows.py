"""Windows UI regression after adding macOS-specific branches."""
import ctypes
import json
from pathlib import Path
import sys
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/XiaohanDesktop'))
from app import DesktopPet,KEY
from desktop_platform import UI_FONT,default_data_path
from model import PetState

output=ROOT/'work/desktop-qa/macos-windows';output.mkdir(exist_ok=True)
ctypes.windll.shcore.SetProcessDpiAwareness(1)
root=tk.Tk();root.withdraw();app=DesktopPet(root,output/'pet.json')
app.state=PetState();results=[]
def check(name,value):
    results.append({'name':name,'passed':bool(value)})
    if not value:raise AssertionError(name)
try:
    app.keyboard.ready.wait(2)
    check('windows_keyboard_registration',not app.keyboard.error and app.keyboard.ready.is_set())
    app.keyboard.stop();root.deiconify();root.update()
    check('windows_color_key',KEY=='#ff00ff' and root.wm_attributes('-transparentcolor')==KEY)
    check('windows_font',UI_FONT=='Microsoft YaHei UI')
    check('source_save_unchanged',default_data_path()==ROOT/'outputs/XiaohanDesktop/data/pet.json')
    app.show_toolbar();root.update();check('nine_icons',len(app.buttons)==9)
    app.open_wardrobe();root.update();check('wardrobe',app.chooser.winfo_ismapped())
    app.popup();root.update();check('more_panel',app.more.win.winfo_ismapped())
    app.close_more();app.set_scene('park',walk=False);app.render(time.monotonic())
    check('park_renders',app.scene_photo is not None)
    app.set_scene(None);now=time.monotonic();app.keyboard.record_activity(now,4);app.render(now)
    check('typing_and_fire',app.pose(now)[1] and app.flame.level>0)
finally:
    (output/'result.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    app.close()
print(f'{len(results)} Windows checks passed')
