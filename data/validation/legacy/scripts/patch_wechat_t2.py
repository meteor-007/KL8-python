# -*- coding: utf-8 -*-
for path in ['scripts/fusion_engine_template.py', 'scripts/fusion_engine_2026298.py']:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    old_t2 = """        f"🛡️ T2对冲组1：{t2_defense[0]['nums_str']}",
        f"🛡️ T2对冲组2：{t2_defense[1]['nums_str']}","""

    new_t2 = """        f"🛡️ T2对冲组1：{t2_defense[0]['nums_str']}",
        f"🛡️ T2对冲组2：{t2_defense[1]['nums_str']}",
        f"🛡️ T2对冲组3：{t2_defense[2]['nums_str']}",
        f"🛡️ T2对冲组4：{t2_defense[3]['nums_str']}","""

    if old_t2 in text:
        text = text.replace(old_t2, new_t2)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Updated {path} successfully!")
    else:
        print(f"Target not found in {path}")
