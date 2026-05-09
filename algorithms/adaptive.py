"""
=============================================================
  KOMPONEN 3: ADAPTIVE ALGORITHM
  
  Strategi: Sesuaikan bobot dan keputusan berdasarkan
  KONTEKS PERMAINAN yang berubah-ubah:

  - Game Phase (early/mid/late): prioritas berbeda
  - Gold Constraint: budget-aware decision making
  - Board Pressure: jika kalah terus, switch ke aggressive
  - Synergy Momentum: jika tinggal 1-2 hero lagi ke tier, 
    fokus sana
  - Slot Availability: prioritaskan hero yang sesuai slot
    yang tersedia

  Adaptive menghasilkan Weight Vector [α, β, γ] yang 
  dipakai oleh Hybrid Algorithm untuk menggabungkan
  skor Greedy dan Heuristic.
=============================================================
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List
from data.heroes import HEROES
from data.synergies import SYNERGIES, count_synergies
from core.board import BoardState


@dataclass
class AdaptiveWeights:
    """Bobot adaptif yang dihasilkan Adaptive Controller."""
    alpha_greedy: float     # Bobot komponen Greedy
    beta_heuristic: float   # Bobot komponen Heuristic
    gamma_carry: float      # Bobot carry score langsung
    strategy_mode: str      # "survival" | "snowball" | "balanced" | "transition"
    reasoning: List[str]    # Penjelasan mengapa bobot ini dipilih

    def __str__(self):
        return (
            f"  Mode       : {self.strategy_mode.upper()}\n"
            f"  α (Greedy) : {self.alpha_greedy:.2f}\n"
            f"  β (Heuristic): {self.beta_heuristic:.2f}\n"
            f"  γ (Carry)  : {self.gamma_carry:.2f}\n"
            f"  Alasan     :\n" +
            "\n".join(f"    - {r}" for r in self.reasoning)
        )


class AdaptiveController:
    """
    Adaptive Controller: menganalisis game state dan
    menghasilkan AdaptiveWeights yang optimal.
    """

    # ─────────────────────────────────────────────
    #  Analisis Kondisi Permainan
    # ─────────────────────────────────────────────

    def _analyze_gold_pressure(self, board: BoardState) -> str:
        """Kategori tekanan gold: rich / moderate / poor."""
        if board.current_gold >= 10:
            return "rich"
        elif board.current_gold >= 5:
            return "moderate"
        else:
            return "poor"

    def _analyze_synergy_momentum(self, board: BoardState) -> Dict[str, int]:
        """
        Cek synergy mana yang hanya butuh 1-2 hero lagi
        untuk naik ke tier berikutnya.
        Kembalikan {syn_id: heroes_needed}.
        """
        counts = count_synergies(board.heroes_on_board, HEROES)
        close_to_tier = {}

        for syn_id, count in counts.items():
            if syn_id not in SYNERGIES:
                continue
            next_tier = SYNERGIES[syn_id].get_next_tier(count)
            if next_tier:
                needed = next_tier.required - count
                if needed <= 2:
                    close_to_tier[syn_id] = needed

        return close_to_tier

    def _analyze_carry_status(self, board: BoardState) -> str:
        """
        Status carry di board: none / weak / moderate / strong.
        """
        carries = [
            HEROES[h] for h in board.heroes_on_board
            if h in HEROES and HEROES[h].role == "Carry"
        ]
        if not carries:
            return "none"
        avg_carry = sum(h.carry_score for h in carries) / len(carries)
        if avg_carry < 4:
            return "weak"
        elif avg_carry < 7:
            return "moderate"
        else:
            return "strong"

    def _analyze_slot_saturation(self, board: BoardState) -> float:
        """Rasio slot terisi (0–1)."""
        return len(board.heroes_on_board) / board.max_slots

    # ─────────────────────────────────────────────
    #  Generate Adaptive Weights
    # ─────────────────────────────────────────────

    def compute_weights(self, board: BoardState) -> AdaptiveWeights:
        """
        Hitung bobot adaptif berdasarkan kondisi game saat ini.
        
        Logika Adaptasi:
        ┌──────────────┬──────────┬────────────┬──────────┐
        │ Kondisi      │ α Greedy │ β Heuristic│ γ Carry  │
        ├──────────────┼──────────┼────────────┼──────────┤
        │ Early+poor   │  0.60    │   0.25     │  0.15    │
        │ Early+rich   │  0.35    │   0.45     │  0.20    │
        │ Mid+balanced │  0.30    │   0.40     │  0.30    │
        │ Mid+syn_close│  0.20    │   0.55     │  0.25    │
        │ Late+no_carry│  0.25    │   0.35     │  0.40    │
        │ Late+strong  │  0.30    │   0.45     │  0.25    │
        └──────────────┴──────────┴────────────┴──────────┘
        """
        phase = board.game_phase
        gold_status = self._analyze_gold_pressure(board)
        syn_momentum = self._analyze_synergy_momentum(board)
        carry_status = self._analyze_carry_status(board)
        slot_sat = self._analyze_slot_saturation(board)

        reasoning = []
        alpha, beta, gamma = 0.35, 0.40, 0.25  # default balanced

        # ── Early Game ─────────────────────────────────────
        if phase == "early":
            if gold_status == "poor":
                alpha, beta, gamma = 0.60, 0.25, 0.15
                mode = "survival"
                reasoning.append("Early game + gold terbatas → utamakan nilai langsung (Greedy tinggi)")
            elif gold_status == "rich":
                alpha, beta, gamma = 0.30, 0.50, 0.20
                mode = "snowball"
                reasoning.append("Early game + gold cukup → investasi synergy jangka panjang (Heuristic tinggi)")
            else:
                alpha, beta, gamma = 0.45, 0.35, 0.20
                mode = "balanced"
                reasoning.append("Early game standard → seimbangkan efisiensi dan potensi")

        # ── Mid Game ───────────────────────────────────────
        elif phase == "mid":
            if syn_momentum:
                close_syns = ", ".join(f"{s}({n})" for s, n in syn_momentum.items())
                alpha, beta, gamma = 0.20, 0.55, 0.25
                mode = "transition"
                reasoning.append(f"Synergy hampir naik tier: {close_syns} → prioritas heuristik synergy completion")
            elif carry_status in ("none", "weak"):
                alpha, beta, gamma = 0.30, 0.30, 0.40
                mode = "survival"
                reasoning.append("Carry lemah di mid game → segera dapatkan carry kuat")
            else:
                alpha, beta, gamma = 0.30, 0.42, 0.28
                mode = "balanced"
                reasoning.append("Mid game stabil → balans antara greedy dan heuristik")

        # ── Late Game ──────────────────────────────────────
        else:
            if carry_status == "strong":
                alpha, beta, gamma = 0.28, 0.47, 0.25
                mode = "snowball"
                reasoning.append("Late game + carry kuat → fokus sempurnakan synergy premium")
            elif carry_status in ("none", "weak"):
                alpha, beta, gamma = 0.25, 0.30, 0.45
                mode = "survival"
                reasoning.append("Late game tanpa carry → darurat! Prioritas absolut cari carry cost tinggi")
            else:
                alpha, beta, gamma = 0.30, 0.40, 0.30
                mode = "balanced"
                reasoning.append("Late game moderate → seimbangkan semua aspek")

        # ── Adjustment: board hampir penuh ─────────────────
        if slot_sat >= 0.85:
            # Board hampir penuh → lebih selektif, heuristik lebih penting
            beta = min(beta + 0.10, 0.65)
            alpha = max(alpha - 0.05, 0.15)
            gamma = max(gamma - 0.05, 0.10)
            reasoning.append(f"Board hampir penuh ({slot_sat:.0%}) → lebih selektif, naikkan heuristik")

        # ── Adjustment: synergy momentum kuat ──────────────
        if len(syn_momentum) >= 2:
            beta = min(beta + 0.08, 0.65)
            alpha = max(alpha - 0.04, 0.15)
            gamma = max(gamma - 0.04, 0.10)
            reasoning.append(f"≥2 synergy hampir tier up → booster heuristik synergy")

        # Normalisasi agar total = 1
        total = alpha + beta + gamma
        alpha /= total
        beta /= total
        gamma /= total

        return AdaptiveWeights(
            alpha_greedy=round(alpha, 3),
            beta_heuristic=round(beta, 3),
            gamma_carry=round(gamma, 3),
            strategy_mode=mode,
            reasoning=reasoning,
        )

    def recommend_target_synergies(self, board: BoardState) -> List[str]:
        """
        Rekomendasikan synergy target untuk difokuskan
        berdasarkan hero yang sudah ada di board.
        """
        counts = count_synergies(board.heroes_on_board, HEROES)
        if not counts:
            return ["Mage", "Marksman", "Swiftblade"]  # default starter patch 1.2.54

        # Ranking synergy yang paling dekat tier berikutnya
        candidates = []
        for syn_id, count in counts.items():
            if syn_id not in SYNERGIES:
                continue
            syn = SYNERGIES[syn_id]
            next_tier = syn.get_next_tier(count)
            if next_tier:
                needed = next_tier.required - count
                bonus = next_tier.power_bonus
                # Nilai = bonus / needed (efisiensi naik tier)
                priority = bonus / needed
                candidates.append((syn_id, priority, needed, bonus))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return [c[0] for c in candidates[:3]]
