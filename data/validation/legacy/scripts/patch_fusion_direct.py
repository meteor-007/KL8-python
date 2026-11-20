# -*- coding: utf-8 -*-
with open('scripts/fusion_engine_295.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the 295 live mapping
old_target = """295 期实战号码映射：
  * 53: 出现于20点位图、重号高概、Sheet 13同出榜首 #1 霸主对(23-53同出169次)与 #6 对(53-77同出158次)，得分 9.75 全场至尊金胆！
  * 77: 出现于重号高概、边号高概、与53同出158次(Out=0)，综合得分 8.29，主力必选！
  * 23: 出现于20点位图、重号高概、与53同出169次(Out=0)全场第一配对，主力必选！
  * 09: 出现于20点位图、关注冷号高概，点位协力 127.2，冷反弹龙头！
  * 44: 出现于重号高概、边号高概，双重形态共振！"""

new_target = """295 期实战号码映射：
  * 35: 出现于20点位图、上期重号高概、同出协力榜首，综合得分 7.76 荣登全场至尊金胆！
  * 12: 出现于20点位图、冷号强反弹高概、点位协力 129.4 全场最高，黄金主力必选！
  * 54: 出现于20点位图、边码高概(52邻码)、顶级同出配对，综合得分 7.37，主力必选！
  * 50: 出现于20点位图、冷号蓄势反弹、区间完全正交防空，黄金铁三角！
  * 64: 出现于20点位图、上期重码高概、七区中枢，主力防守！
  * 09: 出现于20点位图、边码高概(07/10夹号)、点位协力 127.2，一区龙头！"""

text = text.replace(old_target.replace('\r\n', '\n'), new_target.replace('\r\n', '\n'))
text = text.replace(old_target, new_target)
text = text.replace('在 294 期融合算法中，对思静系列二', '在 295 期融合算法中，对思静系列二')
text = text.replace('41 期全景加权均值与 293 期实开比对', '41 期全景加权均值与 294 期实开比对')

with open('scripts/fusion_engine_295.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Direct patch to fusion_engine_295.py applied!")
