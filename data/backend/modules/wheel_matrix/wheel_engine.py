# -*- coding: utf-8 -*-
"""
聪明组合旋转矩阵引擎 (Smart Luck Wheel Core)
依据 Gail Howard 第三章《聪明组合：最省钱的博彩策略》设计
涵盖选6型、选5型经典保奖矩阵与定胆组合
"""
from typing import List, Dict, Optional, Tuple
from .models import GameType, WheelTemplate

# 预设经典 Gail Howard 旋转矩阵库
BUILTIN_WHEELS: Dict[str, WheelTemplate] = {
    # 选6型: 7个号码 5选5中 (6注) - #201
    "W6_7_5_5_6": WheelTemplate(
        template_id="W6_7_5_5_6",
        name="选6型 7码 5选5中 (6注) #201",
        game_type=GameType.PICK_6,
        pool_size=7,
        pick_count=6,
        line_count=6,
        guarantee="5-if-5 (7个号中5个必中5等奖)",
        matrix=[
            [0, 1, 2, 3, 4, 5],
            [0, 1, 2, 3, 4, 6],
            [0, 1, 2, 3, 5, 6],
            [0, 1, 2, 4, 5, 6],
            [0, 1, 3, 4, 5, 6],
            [0, 2, 3, 4, 5, 6],
        ]
    ),
    # 选6型: 10个号码 5选4中 (3注) - #222
    "W6_10_4_5_3": WheelTemplate(
        template_id="W6_10_4_5_3",
        name="选6型 10码 5选4中 (3注) #222",
        game_type=GameType.PICK_6,
        pool_size=10,
        pick_count=6,
        line_count=3,
        guarantee="4-if-5 (10个号中5个必中4等奖)",
        matrix=[
            [0, 1, 2, 3, 4, 5],
            [0, 2, 3, 6, 7, 8],
            [1, 4, 5, 6, 8, 9],
        ]
    ),
    # 选6型: 12个号码 4选4中 (6注) - #301
    "W6_12_4_4_6": WheelTemplate(
        template_id="W6_12_4_4_6",
        name="选6型 12码 4选4中 (6注) #301",
        game_type=GameType.PICK_6,
        pool_size=12,
        pick_count=6,
        line_count=6,
        guarantee="4-if-4 (12个号中4个必中4等奖)",
        matrix=[
            [0, 1, 2, 3, 4, 5],
            [0, 1, 2, 6, 7, 8],
            [0, 3, 4, 6, 9, 10],
            [1, 3, 5, 7, 9, 11],
            [2, 4, 5, 8, 10, 11],
            [6, 7, 8, 9, 10, 11],
        ]
    ),
    # 选5型: 10个号码 4选4中 (6注) - #501
    "W5_10_4_4_6": WheelTemplate(
        template_id="W5_10_4_4_6",
        name="选5型 10码 4选4中 (6注) #501",
        game_type=GameType.PICK_5,
        pool_size=10,
        pick_count=5,
        line_count=6,
        guarantee="4-if-4 (10个号中4个必中4等奖)",
        matrix=[
            [0, 1, 2, 3, 4],
            [0, 1, 5, 6, 7],
            [0, 2, 5, 8, 9],
            [1, 3, 6, 8, 9],
            [2, 4, 6, 7, 8],
            [3, 4, 5, 7, 9],
        ]
    ),
    # 选5型: 12个号码 4选3中 (6注) - #502
    "W5_12_3_4_6": WheelTemplate(
        template_id="W5_12_3_4_6",
        name="选5型 12码 4选3中 (6注) #502",
        game_type=GameType.PICK_5,
        pool_size=12,
        pick_count=5,
        line_count=6,
        guarantee="3-if-4 (12个号中4个必中3等奖)",
        matrix=[
            [0, 1, 2, 3, 4],
            [0, 1, 5, 6, 7],
            [2, 3, 8, 9, 10],
            [4, 5, 8, 9, 11],
            [6, 7, 10, 11, 0],
            [1, 2, 7, 8, 11],
        ]
    ),
}

class WheelEngine:
    @staticmethod
    def get_template(template_id: str) -> Optional[WheelTemplate]:
        return BUILTIN_WHEELS.get(template_id)

    @staticmethod
    def list_templates_for_game(game_type: GameType) -> List[WheelTemplate]:
        return [w for w in BUILTIN_WHEELS.values() if w.game_type == game_type]

    @staticmethod
    def generate_wheel(
        template: WheelTemplate,
        pool: List[int],
        bankers: Optional[List[int]] = None
    ) -> List[List[int]]:
        """
        根据模板生成组合，并支持定胆置换 (Power Numbers)
        """
        bankers = sorted(bankers or [])
        free_pool = sorted([x for x in pool if x not in bankers])
        
        num_bankers = len(bankers)
        needed_free = template.pool_size - num_bankers
        
        if len(free_pool) < needed_free:
            raise ValueError(f"候选号码池不足! 矩阵需要 {template.pool_size} 个号，扣除 {num_bankers} 个胆码后仍需 {needed_free} 个号码，实际提供 {len(free_pool)} 个")

        # 映射表: 前 num_bankers 位放胆码，其余放自由拖码
        mapping = bankers + free_pool[:needed_free]

        tickets = []
        for row in template.matrix:
            ticket = sorted([mapping[idx] for idx in row])
            tickets.append(ticket)

        return tickets
