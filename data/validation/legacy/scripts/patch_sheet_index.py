# -*- coding: utf-8 -*-
with open("scripts/fusion_engine_294.py", "r", encoding="utf-8") as f:
    text = f.read()

old_block = """            if "图表15选2同出" in book_fx.sheet_names():
                sh15 = book_fx.sheet_by_name("图表15选2同出")"""
new_block = """            if book_fx.nsheets > 14:
                sh15 = book_fx.sheet_by_index(14)"""
text = text.replace(old_block, new_block)

old_block2 = """            if "图表14选2" in book_fx.sheet_names():
                sh14 = book_fx.sheet_by_name("图表14选2")"""
new_block2 = """            if book_fx.nsheets > 13:
                sh14 = book_fx.sheet_by_index(13)"""
text = text.replace(old_block2, new_block2)

with open("scripts/fusion_engine_294.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Sheet index patch applied successfully!")
