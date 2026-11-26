"""Runtime scene composition with soft alpha and ground contact lighting."""
from functools import lru_cache
from dataclasses import replace
from pathlib import Path
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from fetch_game import paint_ball, ramp
from paw_motion import contact_pose_pair
from animation import AGES, GAIT_COLUMNS, GAIT_TILE, HEAD_FRAMES, STEP_FRAMES, fetch_asset, frame_names

SCENE_SIZE = (420, 290)


def seat_paws(sprite, floor, head_down):
    """Adjust only the supporting lower legs in a right-facing drawing."""
    solid = sprite.getchannel('A').point(lambda a: 255 if a >= 144 else 0)
    left, top, right, bottom = solid.getbbox()
    width, height = right-left, bottom-top
    split = left+round(width*.49)
    # When reaching for the ball, the muzzle also reaches the lowest rows.
    # Keep it outside the paw search and outside the deformation.
    limit = left+round(width*.68) if head_down else right
    contacts = []
    for start, end in ((left,split),(split,limit)):
        area = solid.crop((start,top,end,bottom))
        bounds = area.getbbox()
        if bounds is None:
            continue
        sole = top+bounds[3]
        row = area.crop((0,bounds[3]-1,area.width,bounds[3])).getprojection()[0]
        columns = [start+i for i,occupied in enumerate(row) if occupied]
        # Separate ties: two paws can reach the same row on a planted frame.
        for col in columns:
            if col == columns[0] or col != last+1:
                contacts.append([col,col,floor-sole])
            else:
                contacts[-1][1] = col
            last = col
    if all(abs(d) < .75 for _,_,d in contacts):
        return sprite

    def reach(column):
        weighted = []
        for first,last,dy in contacts:
            distance = max(first-column,column-last,0)
            weight = 1-ramp(distance,width*.035,width*.16)
            weighted.append((weight,dy))
        weight,dy = max(weighted)
        if head_down:
            weight *= 1-ramp(column,limit,limit+width*.04)
        return weight*dy

    hip = round(floor-height*.45)
    ankle = round(floor-height*.08)
    bands = ((0,hip,0,0),(hip,ankle,0,1),(ankle,sprite.height,1,1))
    mesh = []
    spacing = max(1,round(width*.025))
    for x0 in range(0,sprite.width,spacing):
        x1 = min(x0+spacing,sprite.width)
        d0,d1 = reach(x0),reach(x1)
        for y0,y1,start,end in bands:
            quad = (x0,y0-start*d0,x0,y1-end*d0,x1,y1-end*d1,x1,y0-start*d1)
            mesh.append(((x0,y0,x1,y1),quad))
    return sprite.transform(sprite.size,Image.Transform.MESH,mesh,Image.Resampling.BILINEAR)


class OutdoorRenderer:
    def __init__(self, images):
        self.images = images
        self.backgrounds = {
            name: ImageOps.fit(images['scene_' + name], SCENE_SIZE, Image.Resampling.LANCZOS).convert('RGBA')
            for name in ('park', 'snow')
        }

    def compose_fetch(self,scene,outfit,stage,body_size,sample,origin_name):
        size=round(body_size*sample.scale)
        prefix = outfit if stage==2 else f'{outfit}_{AGES[stage]}'
        def art_name(pose):
            if pose.startswith('run'):
                last_cell=2*HEAD_FRAMES+(int(pose[-1])+1)*STEP_FRAMES-1
                return f'{prefix}_gait@{last_cell}'
            return fetch_asset(outfit,stage,'turnquarter' if pose=='drop' else pose)
        if sample.gait_frame is not None:
            name = f'{prefix}_gait@{sample.gait_frame}'
            # Stance correction registers the soles to the atlas ground line.
            frame = self.compose(scene,name,size,sample.x,sample.ground,sample.flip,
                                 fetch=None if sample.carrying else sample,
                                 footline=size*244/256 if sample.gait_frame<2*HEAD_FRAMES else None)
            if sample.gait_weight < 1:
                walk = self.compose_fetch(scene,outfit,stage,body_size,replace(sample,gait_frame=None),origin_name)
                return Image.blend(walk,frame,sample.gait_weight)
            return frame
        if (0 < sample.mix < 1 and sample.previous_pose not in ('walk','origin_walk')
                and sample.pose not in ('walk','settle')):
            names = [art_name(p) for p in (sample.previous_pose,sample.pose)]
            sprites = [self.sprite(scene,n,size,f) for n,f in zip(names,(sample.previous_flip,sample.flip))]
            pet,footline = self.carry_transition(sprites,sample,size)
            return self.compose(scene,names[1],size,sample.x,sample.ground,sample.flip,pet=pet,footline=footline)
        def pose_frame(pose,flip,offset):
            if pose in ('walk','origin_walk','settle'):
                ball = replace(sample,carrying=False)
                def walking(name):
                    return self.compose(scene,name,size,sample.x,sample.ground,flip,fetch=ball)
                if pose != 'walk':
                    return walking(origin_name)
                cycle = frame_names(outfit,stage,'walk')
                phase = cycle.index(origin_name) + sample.chase_cycles * len(cycle)
                index = int(phase)
                blend = ramp(phase-index,0.,1.)
                start = walking(cycle[index % len(cycle)])
                if blend == 0:
                    return start
                return Image.blend(start,walking(cycle[(index+1) % len(cycle)]),blend)
            return self.compose(scene,art_name(pose),size,sample.x+offset[0],sample.ground,flip)
        if sample.mix == 0:
            return pose_frame(sample.previous_pose,sample.previous_flip,sample.previous_offset)
        current=pose_frame(sample.pose,sample.flip,sample.current_offset)
        if sample.mix<1:
            return Image.blend(pose_frame(sample.previous_pose,sample.previous_flip,sample.previous_offset),current,sample.mix)
        return current

    @staticmethod
    def carry_transition(sprites,sample,size):
        mouths = []
        for sprite,offset in zip(sprites,(sample.previous_offset,sample.current_offset)):
            bottom = sprite.getchannel('A').point(lambda a: 255 if a>=128 else 0).getbbox()[3]
            mouth_x = size/2 + sample.ball_x - sample.x - offset[0]
            mouth_y = bottom + sample.ball_y - sample.ground - offset[1]
            mouths.append((mouth_x,mouth_y))
        return contact_pose_pair(sprites,mouths,sample.mix)

    @lru_cache(maxsize=128)
    def lit_artwork(self, scene, name):
        if '@' in name:
            atlas_name,index=name.rsplit('@',1)
            row,column=divmod(int(index),GAIT_COLUMNS)
            x,y=column*GAIT_TILE,row*GAIT_TILE
            image=self.gait_atlas(atlas_name).crop((x,y,x+GAIT_TILE,y+GAIT_TILE))
        else:
            image = self.images[name]
        # Generated atlases contain nearly transparent background noise. Remove
        # that floor while retaining intermediate alpha for fur antialiasing.
        alpha = image.getchannel('A').point(lambda a: round(max(0, a - 72) * 255 / 183))
        tint = (244, 235, 200) if scene == 'park' else (204, 222, 243)
        rgb = ImageEnhance.Contrast(image.convert('RGB')).enhance(.96)
        rgb = Image.blend(rgb, Image.new('RGB', rgb.size, tint), .055 if scene == 'park' else .085)
        image = rgb.convert('RGBA'); image.putalpha(alpha)
        if '@' in name:
            image = seat_paws(image,round(GAIT_TILE*244/256),int(index)<2*HEAD_FRAMES)
        elif '_fetch_' in name or '_walk' in name:
            floor = alpha.point(lambda a: 255 if a>=144 else 0).getbbox()[3]
            image = seat_paws(image,floor,name.endswith(('pickup','drop')))
        return image

    @lru_cache(maxsize=2)
    def gait_atlas(self,name):
        if name in self.images:
            return self.images[name]
        with Image.open(Path(__file__).resolve().parent/'assets'/(name+'.png')) as image:
            return image.convert('RGBA')

    @lru_cache(maxsize=256)
    def sprite(self, scene, name, size, flip):
        image = self.lit_artwork(scene,name)
        image = image.resize((size, size), Image.Resampling.LANCZOS)
        return ImageOps.mirror(image) if flip else image

    def compose(self, scene, name, size, x, ground, flip=False, flame=None, fetch=None,pet=None,footline=None):
        background = self.backgrounds[scene]
        frame = background.copy()
        if fetch and not fetch.carrying:
            paint_ball(frame, fetch)
        if pet is None:
            pet = self.sprite(scene, name, size, flip)
        alpha = pet.getchannel('A')
        box = alpha.point(lambda a: 255 if a >= 32 else 0).getbbox()
        if box is None:
            raise ValueError('出游素材为空：' + name)
        sole = alpha.point(lambda a: 255 if a>=144 else 0).getbbox()[3]
        left = round(x-size/2)
        top = round(ground) - (sole if footline is None else round(footline))
        body_width = box[2] - box[0]
        center = left + (box[0] + box[2]) / 2
        radius = body_width * .40
        blur = max(2,size*.025)
        pad = round(4*blur)+1
        half_width = round(radius)+pad
        half_height = round(size*.055)+pad
        shadow_mask = Image.new('L', (2*half_width+1,2*half_height+1))
        draw = ImageDraw.Draw(shadow_mask)
        draw.ellipse((half_width-radius, half_height-size*.055, half_width+radius, half_height+size*.04), fill=65)
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur))
        shadow = Image.new('RGBA', shadow_mask.size, (45, 64, 37) if scene == 'park' else (65, 91, 126))
        shadow.putalpha(shadow_mask); frame.alpha_composite(shadow,(round(center)-half_width,round(ground)-half_height))

        # Only pixels meeting the ground cast a tight contact shadow; lifted
        # paws contribute to the softer body shadow instead.
        contact_y = round(ground)-top
        depth = max(2,round(size*.022))
        feet = alpha.crop((box[0],contact_y-depth,box[2],contact_y+1))
        feet = feet.resize((body_width,2*depth+1),Image.Resampling.BILINEAR)
        feet = feet.point(lambda a: round(a*.70)).filter(ImageFilter.GaussianBlur(max(.6,size*.005)))
        contact = Image.new('RGBA', feet.size, (35, 51, 30) if scene == 'park' else (60, 83, 114))
        contact.putalpha(feet)
        frame.alpha_composite(contact, (left+box[0],round(ground)-depth))
        if flame is not None:
            frame.alpha_composite(flame, (round(x-flame.width/2), round(ground-flame.height)))
        # The terrain occludes faint trailing pixels below the planted sole.
        if '@' in name or '_fetch_' in name or '_walk' in name:
            frame.alpha_composite(pet, (left, top), (0,0,pet.width,min(pet.height,contact_y+1)))
        else:
            frame.alpha_composite(pet, (left, top))
        if fetch and fetch.carrying:
            paint_ball(frame, fetch)
        return frame.convert('RGB')
