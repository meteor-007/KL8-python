"""Generate PWA icons"""
from PIL import Image, ImageDraw, ImageFont
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 192x192
img = Image.new('RGBA', (192, 192), (15, 15, 26, 255))
draw = ImageDraw.Draw(img)
draw.ellipse([30, 30, 162, 162], fill=(108, 92, 231, 255))
try:
    font = ImageFont.truetype('arial.ttf', 60)
except:
    font = ImageFont.load_default()
draw.text((96, 96), 'KL8', fill=(255, 255, 255, 255), font=font, anchor='mm')
img.save('static/icons/icon-192.png')
print('icon-192.png created')

# 512x512
img2 = Image.new('RGBA', (512, 512), (15, 15, 26, 255))
draw2 = ImageDraw.Draw(img2)
draw2.ellipse([80, 80, 432, 432], fill=(108, 92, 231, 255))
try:
    font2 = ImageFont.truetype('arial.ttf', 160)
except:
    font2 = ImageFont.load_default()
draw2.text((256, 256), 'KL8', fill=(255, 255, 255, 255), font=font2, anchor='mm')
img2.save('static/icons/icon-512.png')
print('icon-512.png created')
