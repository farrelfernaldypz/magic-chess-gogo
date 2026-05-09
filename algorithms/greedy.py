"""
=============================================================
  KOMPONEN 1: GREEDY ALGORITHM
  
  Strategi: Pilih hero terbaik berdasarkan nilai SAAT INI
  tanpa melihat ke depan. Cocok untuk early game dan situasi
  darurat saat gold terbatas.

  Kriteria Greedy:
  - Nilai hero per gold (efficiency)
  - Kontribusi synergy langsung ke board
  - Power index hero itu sendiri
=============================================================
"""

from typing import List, Dict, Tuple, Optional
from data.heroes import HEROES, Hero
from data.synergies import (
    count_synergies, evaluate_synergy_score, SYNERGIES
)
from core.board import BoardState


class GreedySelector:
    """
    Komponen Greedy: memilih hero dengan nilai tertinggi
    berdasarkan kondisi board saat ini.
    """

    def __init__(self, weight_power: float = 0.4,
                 weight_synergy: float = 0.4,
                 weight_efficiency: float = 0.2):
        self.w_power = weight_power
        self.w_synergy = weight_synergy
        self.w_efficiency = weight_efficiency

    def score_hero(self, hero_id: str, board: BoardState) -> float:
        """
        Hitung skor greedy untuk satu hero.
        
        Formula:
          score = w_power * power_norm
                + w_synergy * synergy_gain_norm
                + w_efficiency * (power / cost)_norm
        """
        if hero_id not in HEROES:
            return 0.0
        hero = HEROES[hero_id]

        # ── 1. Power Index (dinormalisasi 0–1) ────────────────
        max_power = max(h.power_index for h in HEROES.values())
        power_norm = hero.power_index / max_power

        # ── 2. Synergy Gain ──────────────────────────────────
        # Seberapa besar synergy score naik jika hero ini ditambah
        current_score = evaluate_synergy_score(board.synergy_counts)
        sim_counts = board.synergy_counts.copy()
        for syn in hero.synergies:
            sim_counts[syn] = sim_counts.get(syn, 0) + 1
        new_score = evaluate_synergy_score(sim_counts)
        synergy_gain = new_score - current_score

        max_syn = 160  # max single-tier bonus (referensi)
        synergy_norm = min(synergy_gain / max_syn, 1.0)

        # ── 3. Efficiency: power per gold ─────────────────────
        efficiency = hero.power_index / hero.cost
        max_eff = max(h.power_index / h.cost for h in HEROES.values())
        efficiency_norm = efficiency / max_eff

        # ── Final Score ───────────────────────────────────────
        score = (self.w_power * power_norm +
                 self.w_synergy * synergy_norm +
                 self.w_efficiency * efficiency_norm)

        return round(score, 4)

    def rank_candidates(
        self,
        candidates: List[str],
        board: BoardState,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Rangking kandidat hero berdasarkan skor greedy.
        Kembalikan top-K (hero_id, score).
        """
        scored = []
        for hid in candidates:
            if hid in board.all_heroes:
                continue  # Skip yang sudah ada
            if not board.can_afford(hid):
                continue  # Skip yang tidak mampu beli
            score = self.score_hero(hid, board)
            scored.append((hid, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def select_best(
        self,
        candidates: List[str],
        board: BoardState
    ) -> Optional[str]:
        """Pilih satu hero terbaik secara greedy."""
        ranked = self.rank_candidates(candidates, board, top_k=1)
        return ranked[0][0] if ranked else None

    def explain_score(self, hero_id: str, board: BoardState) -> Dict:
        """Penjelasan detail komponen skor untuk satu hero."""
        if hero_id not in HEROES:
            return {}
        hero = HEROES[hero_id]

        max_power = max(h.power_index for h in HEROES.values())
        power_norm = hero.power_index / max_power

        current_score = evaluate_synergy_score(board.synergy_counts)
        sim_counts = board.synergy_counts.copy()
        for syn in hero.synergies:
            sim_counts[syn] = sim_counts.get(syn, 0) + 1
        new_score = evaluate_synergy_score(sim_counts)
        synergy_gain = new_score - current_score

        efficiency = hero.power_index / hero.cost
        max_eff = max(h.power_index / h.cost for h in HEROES.values())
        efficiency_norm = efficiency / max_eff

        total = self.score_hero(hero_id, board)

        return {
            "hero": hero.name,
            "cost": hero.cost,
            "power_index": round(hero.power_index, 2),
            "power_norm": round(power_norm, 3),
            "synergy_gain": round(synergy_gain, 2),
            "efficiency_norm": round(efficiency_norm, 3),
            "total_greedy_score": total,
        }
