# -*- coding: utf-8 -*-
with open('scripts/fusion_engine_295.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if '295 期实战号码映射：' in line:
        new_lines.append(line)
        new_lines.append('        "  * 35: 出现于20点位图、上期重号高概、同出协力榜首，综合得分 7.76 荣登全场至尊金胆！",\n')
        new_lines.append('        "  * 12: 出现于20点位图、冷号强反弹高概、点位协力 129.4 全场最高，黄金主力必选！",\n')
        new_lines.append('        "  * 54: 出现于20点位图、边码高概(52邻码)、顶级同出配对，综合得分 7.37，主力必选！",\n')
        new_lines.append('        "  * 50: 出现于20点位图、冷号蓄势反弹、区间完全正交防空，黄金铁三角！",\n')
        new_lines.append('        "  * 64: 出现于20点位图、上期重码高概、七区中枢，主力防守！",\n')
        new_lines.append('        "  * 09: 出现于20点位图、边码高概(07/10夹号)、点位协力 127.2，一区龙头！",\n')
        skip = True
        continue
    if skip:
        if '双重杀号共识排除率高达' in line:
            skip = False
            new_lines.append(line)
        continue
    new_lines.append(line)

with open('scripts/fusion_engine_295.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated mapping successfully!")
