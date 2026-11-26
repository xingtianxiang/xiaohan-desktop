"""Short care animations that keep the original painted paws in place."""
import math

from PIL import Image, ImageDraw

from fetch_game import ramp

# The three standing drawings share face geometry across all outfits.
SNACK_MOUTH = ((87, 153), (71, 118), (76, 101))


def shift_upper_body(image, x_profile, y_profile, shift):
    mesh = []
    for (left, a), (right, b) in zip(x_profile, x_profile[1:]):
        for (top, c), (bottom, d) in zip(y_profile, y_profile[1:]):
            mesh.append(((left, top, right, bottom),
                         (left, top-shift*a*c, left, bottom-shift*a*d,
                          right, bottom-shift*b*d, right, top-shift*b*c)))
    return image.transform(image.size, Image.Transform.MESH, mesh, Image.Resampling.BILINEAR)


def snack_frame(standing, stage, elapsed):
    mouth_x, mouth_y = SNACK_MOUTH[stage]
    reach = ramp(elapsed,.27,.92)
    chew = ramp(elapsed,.88,1.02)*(1-ramp(elapsed,1.84,2.18))
    nod = 7*math.sin(math.pi*reach) + chew*3*(1-math.cos((elapsed-.92)*math.tau*3.2))
    pet = shift_upper_body(standing, ((0,1),(mouth_x+16,1),(mouth_x+62,0),(256,0)),
                           ((0,1),(mouth_y+10,1),(mouth_y+60,0),(256,0)), nod)
    props = Image.new('RGBA', pet.size)
    paint = ImageDraw.Draw(props)
    remaining = ramp(elapsed,0,.20)*(1-.32*ramp(elapsed,1.04,1.15))*(1-ramp(elapsed,1.54,1.78))
    if remaining:
        x = mouth_x - 46*(1-reach)
        y = mouth_y + 38*(1-reach) + nod
        # A little baked biscuit, drawn separately so it can disappear in bites.
        half = 13*remaining
        radius = 5*remaining
        paint.rounded_rectangle((x-half,y-radius*.53,x+half,y+radius*.53),radius=2,
                                fill='#d79556',outline='#9e542f')
        for tip in (x-half*.85,x+half*.85):
            for offset in (-.48,.48):
                cy = y+radius*offset
                paint.ellipse((tip-radius*.74,cy-radius*.67,tip+radius*.74,cy+radius*.67),
                              fill='#dda264',outline='#a3623a')
        if remaining>.4:
            paint.line((x-half*.45,y-1,x+half*.45,y-1),fill='#f2c68e',width=2)
    for bite in (1.08,1.63):
        flight = (elapsed-bite)/.34
        if 0 <= flight < 1:
            for index in range(3):
                x = mouth_x - (7+5*index)*flight - 4
                y = mouth_y + 3 + 16*flight**2 - (10+6*index)*flight
                radius = (3-index*.45)*(1-flight)
                paint.ellipse((x-radius,y-radius,x+radius,y+radius),fill='#c88348')
    return Image.alpha_composite(pet, props)


def sleep_frame(resting, elapsed):
    breath = (1-math.cos(elapsed*math.tau/2.8))/2
    return shift_upper_body(resting, ((0,0),(88,0),(146,1),(256,.4)),
                            ((0,1),(152,1),(226,0),(256,0)), -3.5*breath)


def bowl_frame(bent, pose, stage, elapsed):
    rim = (210, 212, 219)[stage]
    cycle = .94 if pose=='eat' else .53
    nod = (1-math.cos(elapsed*math.tau/cycle))/2
    # The bowl and both forepaws stay at their painted positions.
    return shift_upper_body(bent, ((0,1),(101,1),(135,0),(256,0)),
                            ((0,1),(rim-27,1),(rim,0),(256,0)), -5*nod)
