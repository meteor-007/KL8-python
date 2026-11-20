# -*- coding: utf-8 -*-
"""
数据管理与历史开奖仓储 (SQLite Storage & Real Data Pipeline)
"""
import sqlite3
import json
import os
import random
from typing import List, Optional, Dict
from .models import DrawRecord, LotteryGameSpec, PRESET_GAMES

REAL_KL8_PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\kl8_history_final.txt"
REAL_POINTS_PATH = r"C:\D-pan\Dpanqianyi\Python-Project\data\daily_points.txt"

class DataManager:
    def __init__(self, db_path: str = "lottery_history.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS draw_records (
                    game_id TEXT,
                    draw_id TEXT,
                    draw_date TEXT,
                    main_balls TEXT,
                    extra_balls TEXT,
                    PRIMARY KEY (game_id, draw_id)
                )
            """)
            conn.commit()

    def load_real_kl8_history(self, file_path: str = REAL_KL8_PATH) -> List[DrawRecord]:
        """从 kl8_history_final.txt 加载真实历史开奖数据"""
        if not os.path.exists(file_path):
            return []
        draws = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Format: date:2026-08-27,period:2026229,numbers:56-14-72-...
                parts = line.split(",")
                d_date = ""
                d_period = ""
                d_numbers = []
                for p in parts:
                    if p.startswith("date:"):
                        d_date = p.split("date:")[1]
                    elif p.startswith("period:"):
                        d_period = p.split("period:")[1]
                    elif p.startswith("numbers:"):
                        num_str = p.split("numbers:")[1]
                        d_numbers = [int(x) for x in num_str.split("-") if x.isdigit()]
                if d_period and d_numbers:
                    draws.append(DrawRecord(
                        draw_id=d_period,
                        draw_date=d_date,
                        main_balls=d_numbers
                    ))
        # 文件中头部为最新期，需反转为时间升序 [最早 -> 最新]
        draws.reverse()
        return draws

    def load_daily_points(self, file_path: str = REAL_POINTS_PATH) -> Dict[str, List[int]]:
        """从 daily_points.txt 加载点位数据 {period: [points]}"""
        if not os.path.exists(file_path):
            return {}
        points_map = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                period = ""
                pts = []
                for p in parts:
                    if p.startswith("period:"):
                        period = p.split("period:")[1]
                    elif p.startswith("points:"):
                        pt_str = p.split("points:")[1]
                        pts = [int(x) for x in pt_str.split() if x.isdigit()]
                if period and pts:
                    points_map[period] = pts
        return points_map

    def save_draws(self, game_id: str, draws: List[DrawRecord]):
        self._init_db()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for d in draws:
                cursor.execute("""
                    INSERT OR REPLACE INTO draw_records (game_id, draw_id, draw_date, main_balls, extra_balls)
                    VALUES (?, ?, ?, ?, ?)
                """, (game_id, d.draw_id, d.draw_date, json.dumps(d.main_balls), json.dumps(d.extra_balls)))
            conn.commit()

    def get_draws(self, game_id: str, limit: Optional[int] = None) -> List[DrawRecord]:
        self._init_db()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            sql = "SELECT draw_id, draw_date, main_balls, extra_balls FROM draw_records WHERE game_id = ? ORDER BY CAST(draw_id AS INTEGER) ASC"
            if limit:
                sql += f" LIMIT {limit}"
            cursor.execute(sql, (game_id,))
            rows = cursor.fetchall()
            draws = []
            for r in rows:
                draws.append(DrawRecord(
                    draw_id=r[0],
                    draw_date=r[1],
                    main_balls=json.loads(r[2]),
                    extra_balls=json.loads(r[3])
                ))
            return draws

    @staticmethod
    def generate_synthetic_history(spec: LotteryGameSpec, num_draws: int = 120, seed: int = 42) -> List[DrawRecord]:
        rng = random.Random(seed)
        draws = []
        all_main = list(range(1, spec.main_pool + 1))
        all_extra = list(range(1, spec.extra_pool + 1)) if spec.extra_pool > 0 else []

        for i in range(1, num_draws + 1):
            draw_id = f"{2026000 + i}"
            draw_date = f"2026-{(i//30)%12 + 1:02d}-{(i%28)+1:02d}"
            main_balls = sorted(rng.sample(all_main, spec.main_pick))
            extra_balls = sorted(rng.sample(all_extra, spec.extra_pick)) if spec.extra_pick > 0 else []
            draws.append(DrawRecord(draw_id, draw_date, main_balls, extra_balls))
        return draws
