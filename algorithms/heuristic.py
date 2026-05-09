"""
=============================================================
  KOMPONEN 2: HEURISTIC ALGORITHM
  
  Strategi: Evaluasi potensi MASA DEPAN dengan look-ahead.
  Heuristik mengestimasi nilai akhir sebuah pilihan hero
  berdasarkan:
  
  - Synergy Completion Potential: seberapa dekat ke tier bonus
  - Carry Combo Score: sinergi hero carry dengan support/tank
  - Roster Diversity: keseimbangan role di board
  - Chaining Potential: apakah hero ini membuka path ke hero 
    cost tinggi yang lebih kuat

  Look-ahead depth: 2 langkah ke depan (simulasi)
=============================================================
"""

from typing import List, Dict, Tuple, Optional
from data.heroes import HEROES, Hero
from data.synergies import SYNERGIES, count_synergies, evaluate_synergy_score
from core.board import BoardState


class HeuristicEvaluator:
    """
    Komponen Heuristic: evaluasi potensi masa depan sebuah 
    komposisi hero menggunakan beberapa heuristik.
    """

    def __init__(self):
        # Bobot heuristik
        self.w_synergy_potential = 0.35
        self.w_carry_combo = 0.25
        self.w_diversity = 0.15
        self.w_chain_potential = 0.25

    # ─────────────────────────────────────────────
    #  H1: Synergy Completion Potential
    # ─────────────────────────────────────────────

    def synergy_potential_score(self, board: BoardState) -> float:
        """
        Hitung potensi synergy: bonus dari tier yang sudah aktif
        + estimasi nilai tier berikutnya yang hampir tercapai.
        
        Tier "hampir tercapai" = butuh ≤ 2 hero lagi.
        """
        counts = board.synergy_counts
        total = 0.0

        for syn_id, count in counts.items():
            if syn_id not in SYNERGIES:
                continue
            syn = SYNERGIES[syn_id]

            # Bonus aktif
            active = syn.get_active_tier(count)
            if active:
                total += active.power_bonus

            # Estimasi bonus tier berikutnya
            next_tier = syn.get_next_tier(count)
            if next_tier:
                needed = next_tier.required - count
                if needed <= 2:
                    # Semakin dekat, semakin tinggi estimasinya
                    discount = 0.8 if needed == 1 else 0.5
                    total += next_tier.power_bonus * discount

        return total

    # ─────────────────────────────────────────────
    #  H2: Carry Combo Score
    # ─────────────────────────────────────────────

    def carry_combo_score(self, board: BoardState) -> float:
        """
        Nilai komposisi carry: seberapa baik hero carry didukung
        oleh tank dan support di board yang sama.
        
        Carry butuh: setidaknya 1 tank (frontline) dan 1 support
        atau synergy yang memberikan sustain.
        """
        if not board.heroes_on_board:
            return 0.0

        heroes = [HEROES[h] for h in board.heroes_on_board if h in HEROES]

        carries = [h for h in heroes if h.role == "Carry"]
        tanks = [h for h in heroes if h.role == "Tank"]
        supports = [h for h in heroes if h.role == "Support"]

        if not carries:
            return 0.0

        # Skor carry murni
        carry_score = sum(h.carry_score for h in carries) / len(carries)

        # Multiplier berdasarkan support & tank
        support_bonus = min(len(supports) * 0.15, 0.45)
        tank_bonus = min(len(tanks) * 0.10, 0.30)
        combo_multiplier = 1.0 + support_bonus + tank_bonus

        # Synergy carry bonus: jika ada Fighter/Assassin/Marksman aktif
        syn_counts = board.synergy_counts
        carry_synergies = ["Marksman", "Mage", "Swiftblade", "Weapon Master", "Phasewarper", "Scavenger"]
        syn_carry_bonus = 0.0
        for cs in carry_synergies:
            if cs in syn_counts and syn_counts[cs] >= 2:
                syn_carry_bonus += 0.15

        total = carry_score * combo_multiplier * (1 + syn_carry_bonus)
        return min(total, 10.0)

    # ─────────────────────────────────────────────
    #  H3: Role Diversity Score
    # ─────────────────────────────────────────────

    def diversity_score(self, board: BoardState) -> float:
        """
        Nilai keseimbangan role. Board ideal memiliki campuran
        Carry, Tank, Support – menghindari board mono-role
        yang mudah di-counter.
        """
        if not board.heroes_on_board:
            return 0.0

        heroes = [HEROES[h] for h in board.heroes_on_board if h in HEROES]
        role_counts: Dict[str, int] = {}
        for h in heroes:
            role_counts[h.role] = role_counts.get(h.role, 0) + 1

        total = len(heroes)
        # Ideal ratio: ~50% Carry, ~30% Tank/Fighter, ~20% Support
        ideal = {"Carry": 0.50, "Tank": 0.20, "Fighter": 0.10, "Support": 0.20}

        score = 0.0
        for role, ideal_ratio in ideal.items():
            actual_ratio = role_counts.get(role, 0) / total
            # Nilai mendekati ideal = lebih tinggi
            diff = abs(actual_ratio - ideal_ratio)
            score += max(0, 1.0 - diff * 4)

        return score / len(ideal)  # 0–1

    # ─────────────────────────────────────────────
    #  H4: Chain Potential
    # ─────────────────────────────────────────────

    def chain_potential_score(self, hero_id: str, board: BoardState) -> float:
        """
        Nilai "chaining": apakah menambah hero ini membuka
        path synergy menuju hero cost tinggi yang lebih kuat?
        
        Contoh: hero dengan Marksman/Mage/Swiftblade dapat membuka jalur ke carry premium patch baru.
        """
        if hero_id not in HEROES:
            return 0.0

        hero = HEROES[hero_id]
        hero_synergies = set(hero.synergies)

        # Cari hero cost tinggi (4–5) yang punya overlap synergy
        chain_value = 0.0
        for other_id, other in HEROES.items():
            if other.cost < 4:
                continue
            if other_id in board.all_heroes:
                continue

            overlap = hero_synergies & set(other.synergies)
            if overlap:
                # Nilai berdasarkan cost hero premium dan carry score-nya
                value = (other.cost / 5.0) * (other.carry_score / 10.0)
                chain_value += value * len(overlap)

        return min(chain_value, 5.0)  # cap di 5

    # ─────────────────────────────────────────────
    #  COMBINED HEURISTIC SCORE
    # ─────────────────────────────────────────────

    def evaluate_board(self, board: BoardState) -> float:
        """Hitung total nilai heuristik sebuah board state."""
        syn_score = self.synergy_potential_score(board)
        carry_score = self.carry_combo_score(board)
        div_score = self.diversity_score(board)

        # Normalisasi
        syn_norm = min(syn_score / 500, 1.0)
        carry_norm = carry_score / 10.0
        div_norm = div_score  # sudah 0–1

        total = (self.w_synergy_potential * syn_norm +
                 self.w_carry_combo * carry_norm +
                 self.w_diversity * div_norm)

        return round(total, 4)

    def evaluate_hero_addition(
        self, hero_id: str, board: BoardState
    ) -> Tuple[float, Dict]:
        """
        Hitung peningkatan nilai heuristik jika hero ditambahkan.
        Kembalikan (delta_score, komponen_detail).
        """
        if hero_id not in HEROES:
            return 0.0, {}

        # Simulasi penambahan hero
        sim_board = board.copy()
        sim_board.current_gold += HEROES[hero_id].cost  # bypass gold check
        sim_board.heroes_on_board.append(hero_id)

        before = self.evaluate_board(board)
        after = self.evaluate_board(sim_board)
        delta = after - before

        chain = self.chain_potential_score(hero_id, board)

        details = {
            "heuristic_before": round(before, 4),
            "heuristic_after": round(after, 4),
            "heuristic_delta": round(delta, 4),
            "chain_potential": round(chain, 4),
            "combined_h_score": round(
                delta * (1 - self.w_chain_potential) +
                (chain / 5.0) * self.w_chain_potential, 4
            ),
        }
        return details["combined_h_score"], details

    def rank_candidates(
        self,
        candidates: List[str],
        board: BoardState,
        top_k: int = 5
    ) -> List[Tuple[str, float, Dict]]:
        """Rangking kandidat berdasarkan skor heuristik."""
        scored = []
        for hid in candidates:
            if hid in board.all_heroes:
                continue
            if not board.can_afford(hid):
                continue
            score, details = self.evaluate_hero_addition(hid, board)
            scored.append((hid, score, details))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
