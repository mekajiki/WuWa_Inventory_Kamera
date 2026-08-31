# ステータス画面左パネルの合計ステータス6項目の位置を採寸
import sys, cv2
sys.stdout.reconfigure(encoding='utf-8')
from scraping.utils.common import readTextBoxes

img = cv2.cvtColor(cv2.imread('section_0.png'), cv2.COLOR_BGR2RGB)
h, w = img.shape[:2]
crop = img[int(h*0.35):int(h*0.80), 0:int(w*0.28)]
for x0, y0, x1, y1, text in sorted(readTextBoxes(crop), key=lambda b: b[1]):
    print(f'real({int(x0)},{int(y0+h*0.35)})-({int(x1)},{int(y1+h*0.35)}) 1080p({int(x0/2)},{int((y0+h*0.35)/2)}) {text!r}')
