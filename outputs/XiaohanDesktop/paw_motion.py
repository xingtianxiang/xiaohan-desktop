"""Register real contact pads when interpolating the four painted trot poses."""
from bisect import bisect_right
from PIL import Image


def pad_x(solid, left, right):
    band = solid.crop((left,0,right,solid.height))
    _,_,_,sole = band.getbbox()
    strip = band.crop((0,max(0,sole-2),band.width,sole))
    xs = [i+left for i,v in enumerate(strip.getprojection()[0]) if v]
    return xs[len(xs)//2]


def interp(x, knots, values):
    j=max(0,min(len(knots)-2,bisect_right(knots,x)-1))
    return values[j]+(values[j+1]-values[j])*(x-knots[j])/(knots[j+1]-knots[j])


def contact_pose_pair(images,mouths,t):
    """Warp both sets of toes to shared positions before transferring weight."""
    width=images[0].width
    sections=[]
    for image,(mx,my) in zip(images,mouths):
        solid=image.getchannel('A').point(lambda a:255 if a>=128 else 0)
        left,top,right,sole=solid.getbbox()
        middle=(left+right)//2
        front=pad_x(solid,middle,right)
        rear=pad_x(solid,left,middle)
        rear=max(left+1,min(middle-1,rear))
        front=max(middle+1,min(right-1,front))
        # Mouth and pads each get their own horizontal control line. The upper
        # body's changing width therefore cannot drag a planted toe sideways.
        mouth=max(left+1,min(right-1,mx))
        jaw=max(top+1,min(sole-3,my))
        ankle=max(jaw+1,sole-max(2,(sole-top)*.13))
        sections.append(((top,jaw,ankle,sole),
                         ((left,mouth,right),(left,mouth,right),
                          (left,rear,front,right),(left,rear,front,right))))
    def between(a,b):
        return a+(b-a)*t
    ys=tuple(round(between(a,b)) for a,b in zip(sections[0][0],sections[1][0]))
    profiles=[tuple(between(a,b) for a,b in zip(first,second))
              for first,second in zip(sections[0][1],sections[1][1])]
    # Include all horizontal control points as grid boundaries.
    cuts=sorted({0,width,*(round(x) for profile in profiles for x in profile)})
    layers=[]
    for image,(source_y,source_x) in zip(images,sections):
        mesh=[]
        for row in range(3):
            if ys[row]==ys[row+1]:
                continue
            for lo,hi in zip(cuts,cuts[1:]):
                quad=(interp(lo,profiles[row],source_x[row]),source_y[row],
                      interp(lo,profiles[row+1],source_x[row+1]),source_y[row+1],
                      interp(hi,profiles[row+1],source_x[row+1]),source_y[row+1],
                      interp(hi,profiles[row],source_x[row]),source_y[row])
                mesh.append(((lo,ys[row],hi,ys[row+1]),quad))
        layers.append(image.convert('RGBa').transform(image.size,Image.Transform.MESH,mesh,Image.Resampling.BILINEAR))
    # Swing legs and tails have no matching pixels in the other drawing.
    # Use a single warped silhouette and blend colour only inside shared fur.
    first,second=(layer.convert('RGBA') for layer in layers)
    outline=first if t<.5 else second
    shared=Image.composite(second,first,second.getchannel('A'))
    colour=Image.blend(first,shared,t)
    interior=Image.composite(colour,outline,first.getchannel('A'))
    interior.putalpha(outline.getchannel('A'))
    return interior,ys[-1]


def trot_cells(poses,steps):
    frames=[]
    for step in range(4):
        a,b=poses[(step-1)%4],poses[step]
        for i in range(steps):
            if i in (0,steps-1):
                frames.append(a[0] if i==0 else b[0])
                continue
            frame,_=contact_pose_pair((a[0],b[0]),(a[1],b[1]),i/(steps-1))
            frames.append(frame)
    return frames
