from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
root=Path(r'C:/Users/txing/.codex/generated_images/01a1c842-85b2-7933-8710-1e80f361c5f3')
items=[('当前小焊',None),('A 复古像素','exec-7ca0991d-94d7-432b-90ff-e826b09d7af3.png'),('B 日系手绘','exec-70eb7e77-137f-4c97-bdf4-e418c140fd68.png'),('C 绘本水彩','exec-b14b4879-bd21-4b63-b72b-18cc29ad3211.png'),('D 羊毛毡','exec-6f4b41e9-7704-4209-82aa-f1a805d6ac71.png'),('E 立体造型','exec-27a1479e-7c67-457a-9166-308496d082d7.png'),('F 简洁线稿','exec-4d929121-9b2c-4c57-94cc-c02c9acfc445.png')]
canvas=Image.new('RGB',(1600,1020),'#edeae5'); d=ImageDraw.Draw(canvas)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',25)
small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
for i,(label,name) in enumerate(items):
    x=(i%4)*400; y=(i//4)*510
    d.rounded_rectangle((x+10,y+10,x+390,y+500),radius=14,fill='#faf9f6')
    if name:
        im=Image.open(root/name).convert('RGBA'); im.thumbnail((360,420))
    else:
        atlas=Image.open('work/xiaohan-original.png').convert('RGBA')
        im=atlas.crop((0,7*208,192,8*208))
        bbox=im.getbbox()
        if bbox: im=im.crop(bbox)
        im.thumbnail((360,400))
        ratio=min(360/im.width,400/im.height)
        im=im.resize((round(im.width*ratio),round(im.height*ratio)),Image.Resampling.LANCZOS)
    canvas.paste(im,(x+(400-im.width)//2,y+20+(420-im.height)//2),im)
    d.text((x+200,y+460),label,font=font,fill='#243140',anchor='mm')
d.text((1400,720),'造型对比',font=font,fill='#243140',anchor='mm')
d.text((1400,765),'当前小焊取自现有动作素材',font=small,fill='#5c626b',anchor='mm')
d.text((1400,800),'其余六款为风格概念图',font=small,fill='#5c626b',anchor='mm')
canvas.save('outputs/xiaohan-seven-style-comparison.jpg',quality=94)
