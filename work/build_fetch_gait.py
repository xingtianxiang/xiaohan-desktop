"""Bake head and paw inbetweens from the approved drawings (offline authoring only).

Requires Pillow, numpy, scipy and opencv-python-headless. The desktop app reads PNGs.
"""
import json
from pathlib import Path
import sys

import cv2
import numpy as np
from PIL import Image
from scipy.interpolate import RBFInterpolator

APP = Path(__file__).resolve().parents[1] / 'outputs/XiaohanDesktop'
sys.path.insert(0, str(APP))
from animation import AGES, GAIT_COLUMNS, GAIT_TILE, HEAD_FRAMES, STEP_FRAMES, fetch_asset
from model import OUTFITS
from paw_motion import trot_cells

ASSETS = APP / 'assets'
SIDE = 256
BASELINE = 244
Y, X = np.mgrid[:SIDE,:SIDE].astype(np.float32)
GRID = np.dstack((X,Y))
COARSE = np.linspace(0, SIDE-1, 33)
COARSE_GRID = np.stack(np.meshgrid(COARSE, COARSE),axis=-1)


def load_pose(name, metadata):
    rgba = np.array(Image.open(ASSETS / (name+'.png')).convert('RGBA'))
    rgba[rgba[:,:,3]<70] = 0
    y,x = np.nonzero(rgba[:,:,3]>=95)
    bottom = y.max()+1
    aligned = cv2.warpAffine(rgba,np.float32([[1,0,0],[0,1,BASELINE-bottom]]),(SIDE,SIDE))
    u,v = metadata[name]['ball']
    mouth = np.array([SIDE*(.5+u),BASELINE-SIDE*v])
    box = (x.min(),y.min()+BASELINE-bottom,x.max()+1,BASELINE)
    return aligned,mouth,box


def empty_mouth(rgba, mouth, radius):
    # Remove just the orange toy at the measured mouth, preserving the black nose above it.
    rgb=rgba[:,:,:3].astype(float)
    red,green,blue=rgb.transpose(2,0,1)
    near=(X-mouth[0])**2+(Y-mouth[1])**2 < (radius*1.65)**2
    toy=near & (red>green+25) & (green>blue+12) & (red>125) & (rgba[:,:,3]>70)
    if not np.any(toy):
        raise ValueError('Missing visible ball at the measured mouth')
    border=cv2.dilate(toy.astype('uint8'),np.ones((3,3),np.uint8)).astype(bool)
    out=rgba.copy()
    out[border & ((Y>=mouth[1]-radius*.45) | toy)] = 0
    return out


def skeleton(mouth,box):
    left,top,right,ground = box
    w,h = right-left,ground-top
    shoulder = np.array([left+.59*w,ground-.48*h])
    forward=mouth-shoulder
    forward/=np.linalg.norm(forward)
    side=np.array([-forward[1],forward[0]])
    controls=[(0,0),(255,0),(0,255),(255,255),
              (left+.19*w,ground-.74*h),(left+.22*w,ground-.42*h),
              (left+.12*w,ground-2),(left+.51*w,ground-2),shoulder,
              mouth, mouth-.13*w*forward+.075*w*side, mouth-.22*w*forward-.12*w*side]
    return np.asarray(controls,dtype=float)


def head_rig(low, high, box):
    # Rotate the same muzzle and ears about the shoulder, with the weight on the
    # paws. This preserves the face throughout the deep reach instead of dissolving it.
    left,top,right,bottom=box
    w,h=right-left,bottom-top
    pivot=np.array([left+.58*w,bottom-.50*h])
    low_vector,high_vector=low[1]-pivot,high[1]-pivot
    angle=np.arctan2(high_vector[1],high_vector[0])-np.arctan2(low_vector[1],low_vector[0])
    bare=premult(empty_mouth(low[0],low[1],low[3]))
    gripped=premult(low[0])
    # Advect backwards in small rigid increments. A single large inverse warp
    # can sample the orange ball twice where the raised head uncovers a leg.
    def transform(t):
        tip=(1-t)*low[1]+t*high[1]+[SIDE*.035*np.sin(t*np.pi),0]
        angle_t=t*angle
        return tip.astype('float32'),np.float32([[np.cos(angle_t),-np.sin(angle_t)],
                                                [np.sin(angle_t),np.cos(angle_t)]])
    def draw(t,layer):
        mapping=GRID.copy()
        times=np.linspace(t,0.,max(2,round(t*32)+1))
        for current,previous in zip(times,times[1:]):
            tip,rotation=transform(current)
            prior,prior_rotation=transform(previous)
            local=(mapping-tip)@rotation
            px=local[:,:,0]+low[1][0]
            py=local[:,:,1]+low[1][1]
            line=left+w*(.47+.20*np.clip((py-top)/h,0.,1.))
            weight=np.clip((px-line)/(.13*w),0.,1.)
            torso=np.clip((mapping[:,:,0]-left-.40*w)/(.20*w),0.,1.)
            weight=(weight*weight*(3-2*weight)*torso*torso*(3-2*torso))[:,:,None]
            mapping+=weight*(prior+local@prior_rotation.T-mapping)
        return to_image(sample(layer,mapping))
    descent=[draw(t,bare) for t in np.linspace(.5,0,HEAD_FRAMES)]
    half=(HEAD_FRAMES-1)//2
    rise=[draw(t,gripped) for t in np.linspace(0,.5,half+1)]
    upright=np.array(rise[-1])
    up_box=Image.fromarray(upright[:,:,3]).point(lambda a:255 if a>95 else 0).getbbox()
    half_mouth=(low[1]+high[1])/2+[SIDE*.035,0]
    finish=inbetweens(upright,high[0],skeleton(half_mouth,up_box),high[2],HEAD_FRAMES-half)
    return descent+rise+finish[1:]


def warp_map(source, target):
    # The smooth inverse map pins paws and shoulder independently of the muzzle.
    displacement=RBFInterpolator(target,source-target,smoothing=.08)(COARSE_GRID.reshape(-1,2))
    displacement=displacement.reshape(33,33,2).astype(np.float32)
    # Remap the displacement grid at its actual node coordinates, including its borders.
    return GRID+cv2.remap(displacement,GRID*(32/(SIDE-1)),None,cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def sample(img,grid):
    return cv2.remap(img,grid,None,cv2.INTER_LINEAR)


def premult(im):
    result=im.astype(np.float32)
    result[:,:,:3]*=result[:,:,3:4]/255
    return result


def to_image(data):
    data=data.copy()
    data[:,:,:3]*=255/np.maximum(1.,data[:,:,3:4])
    return Image.fromarray(data.clip(0,255).astype(np.uint8),'RGBA')


def tracking_image(layer):
    rgb=layer[:,:,:3]+(1-layer[:,:,3:4]/255)*104
    return cv2.cvtColor(rgb.clip(0,255).astype(np.uint8),cv2.COLOR_RGB2GRAY)


def signed_distance(alpha):
    inside=(alpha>=128).astype(np.uint8)
    return cv2.distanceTransform(inside,cv2.DIST_L2,3)-cv2.distanceTransform(1-inside,cv2.DIST_L2,3)


def inbetweens(a,b,controls_a,controls_b,count,bow=0.):
    mid=(controls_a+controls_b)/2
    left=sample(premult(a),warp_map(controls_a,mid))
    right=sample(premult(b),warp_map(controls_b,mid))
    tracker=cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    tracker.setFinestScale(0)
    luma_a,luma_b=tracking_image(left),tracking_image(right)
    fwd=tracker.calc(luma_a,luma_b,None)
    back=tracker.calc(luma_b,luma_a,None)
    sequence=[]
    for i,t in enumerate(np.linspace(0.,1.,count)):
        if i in (0,count-1):
            sequence.append(Image.fromarray(a if i==0 else b))
            continue
        # Solve for source pixels at intermediate limb positions, then sample both drawings there.
        src_a=src_b=GRID
        for _ in range(3):
            src_a=GRID-t*sample(fwd,src_a)
            src_b=GRID-(1-t)*sample(back,src_b)
        # In disoccluded areas there is no matching second paw. Keep the nearer
        # warped drawing opaque for most of the step.
        fade=np.clip((t-.30)/.40,0.,1.)
        blend=fade*fade*(3-2*fade)
        pose_a,pose_b=sample(left,src_a),sample(right,src_b)
        mixed=(1-blend)*pose_a+blend*pose_b
        # When one leg uncovers the other, interpolate the silhouette boundary.
        # Averaging coverage here paints two translucent paws in the gap.
        boundary=(1-blend)*signed_distance(pose_a[:,:,3])+blend*signed_distance(pose_b[:,:,3])
        coverage=np.clip(.5+boundary*.7,0.,1.)*255
        disagreement=np.abs(pose_a[:,:,3]-pose_b[:,:,3])/255
        new_alpha=mixed[:,:,3]*(1-disagreement)+coverage*disagreement
        mixed[:,:,:3]*=(new_alpha/np.maximum(1.,mixed[:,:,3]))[:,:,None]
        mixed[:,:,3]=new_alpha
        target=(1-t)*controls_a+t*controls_b
        target[-3:,0]+=bow*np.sin(np.pi*t)
        sequence.append(to_image(sample(mixed,warp_map(mid,target))))
    return sequence


def bake(outfit,stage,metadata):
    def pose(key):
        name=fetch_asset(outfit,stage,key)
        image,mouth,box=load_pose(name,metadata)
        return image,mouth,skeleton(mouth,box),SIDE*metadata[name]['radius']
    low,high=pose('pickup'),pose('turnquarter')
    footprint=Image.fromarray(low[0][:,:,3]).point(lambda a:255 if a>=95 else 0).getbbox()
    frames=head_rig(low,high,footprint)
    runs=[pose('run'+str(step)) for step in range(4)]
    frames+=trot_cells([(Image.fromarray(r[0]),r[1]) for r in runs],STEP_FRAMES)
    rows=(len(frames)+GAIT_COLUMNS-1)//GAIT_COLUMNS
    atlas=Image.new('RGBA',(GAIT_TILE*GAIT_COLUMNS,GAIT_TILE*rows))
    for i,frame in enumerate(frames):
        atlas.paste(frame.resize((GAIT_TILE,GAIT_TILE),Image.Resampling.LANCZOS),
                    (GAIT_TILE*(i%GAIT_COLUMNS),GAIT_TILE*(i//GAIT_COLUMNS)))
    prefix=outfit if stage==2 else f'{outfit}_{AGES[stage]}'
    atlas.save(ASSETS/(prefix+'_gait.png'))
    print(prefix,flush=True)


if __name__=='__main__':
    cv2.setNumThreads(2)
    meta=json.loads((ASSETS/'fetch-anchors.json').read_text(encoding='utf-8'))
    for outfit in OUTFITS:
        for stage in range(3):
            bake(outfit,stage,meta)
