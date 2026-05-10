"""
=============================================================
  HYBRID ALGORITHM
  
  Menggabungkan ketiga komponen:
    [1] Greedy    → nilai langsung / efisiensi
    [2] Heuristic → potensi jangka menengah
    [3] Adaptive  → penyesuaian bobot kontekstual

  Formula Hybrid Score:
    H_score(hero) = α × S_greedy(hero)
                  + β × S_heuristic(hero)
                  + γ × S_carry(hero)
  
  Dimana (α, β, γ) dihasilkan oleh Adaptive Controller.

  Output:
  - Rekomendasi hero terbaik per langkah
  - Urutan pembelian yang dioptimasi
  - Analisis synergy yang harus dituju
=============================================================
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from data.heroes import HEROES
from data.synergies import SYNERGIES
from core.board import BoardState
from algorithms.greedy import GreedySelector
from algorithms.heuristic import HeuristicEvaluator
from algorithms.adaptive import AdaptiveController, AdaptiveWeights


@dataclass
class HeroRecommendation:
    """Rekomendasi satu hero beserta detail skornya."""
    rank: int
    hero_id: str
    hero_name: str
    cost: int
    synergies: List[str]
    role: str

    # Skor per komponen
    greedy_score: float
    heuristic_score: float
    carry_score: float

    # Bobot adaptif saat itu
    weights: AdaptiveWeights

    # Final hybrid score
    hybrid_score: float

    # Detail heuristik
    h_details: Dict = field(default_factory=dict)

    def __str__(self) -> str:
        syn_str = " | ".join(self.synergies)
        return (
            f"  [{self.rank}] {self.hero_name} (Cost:{self.cost} | {self.role})\n"
            f"      Synergy  : {syn_str}\n"
            f"      Greedy   : {self.greedy_score:.4f} × {self.weights.alpha_greedy:.2f}\n"
            f"      Heuristic: {self.heuristic_score:.4f} × {self.weights.beta_heuristic:.2f}\n"
            f"      Carry    : {self.carry_score:.4f} × {self.weights.gamma_carry:.2f}\n"
            f"      ──────────────────────────\n"
            f"      HYBRID   : {self.hybrid_score:.4f}  ★"
        )


@dataclass
class OptimizationResult:
    """Hasil lengkap satu sesi optimasi."""
    round_number: int
    game_phase: str
    adaptive_weights: AdaptiveWeights
    recommendations: List[HeroRecommendation]
    target_synergies: List[str]
    final_board: BoardState


class HybridOptimizer:
    """
    Hybrid Algorithm: orkestrator utama yang menggabungkan
    Greedy, Heuristic, dan Adaptive.
    """

    def __init__(self):
        self.greedy = GreedySelector()
        self.heuristic = HeuristicEvaluator()
        self.adaptive = AdaptiveController()

    # ─────────────────────────────────────────────
    #  Core Hybrid Scoring
    # ─────────────────────────────────────────────

    def hybrid_score(
        self,
        hero_id: str,
        board: BoardState,
        weights: AdaptiveWeights
    ) -> Tuple[float, Dict]:
        """
        Hitung hybrid score untuk satu hero.
        
        Returns: (final_score, component_details)
        """
        if hero_id not in HEROES:
            return 0.0, {}

        hero = HEROES[hero_id]

        # ── Komponen 1: Greedy Score ──────────────────────
        g_score = self.greedy.score_hero(hero_id, board)

        # ── Komponen 2: Heuristic Score ───────────────────
        h_score, h_details = self.heuristic.evaluate_hero_addition(hero_id, board)

        # ── Komponen 3: Carry Score (dinormalisasi) ────────
        c_score = hero.carry_score / 10.0

        # ── Hybrid Formula ─────────────────────────────────
        final = (weights.alpha_greedy * g_score +
                 weights.beta_heuristic * h_score +
                 weights.gamma_carry * c_score)

        details = {
            "greedy_score": round(g_score, 4),
            "heuristic_score": round(h_score, 4),
            "carry_score_norm": round(c_score, 4),
            "hybrid_score": round(final, 4),
            "h_details": h_details,
        }
        return round(final, 4), details

    # ─────────────────────────────────────────────
    #  Main Recommendation Engine
    # ─────────────────────────────────────────────

    def recommend(
        self,
        board: BoardState,
        candidate_pool: Optional[List[str]] = None,
        top_k: int = 5
    ) -> OptimizationResult:
        """
        Hasilkan rekomendasi hero top-K berdasarkan
        Hybrid Algorithm.

        Parameters:
          board          : kondisi board saat ini
          candidate_pool : daftar hero yang tersedia di shop
                           (None = semua hero)
          top_k          : jumlah rekomendasi yang ingin ditampilkan
        """
        # Pool default = semua hero yang belum ada di board
        if candidate_pool is None:
            candidate_pool = [
                hid for hid in HEROES
                if hid not in board.all_heroes or (board.game_phase in {"mid", "late"} and board.can_star_up(hid))
            ]

        # Filter: hanya yang mampu dibeli
        affordable = [
            hid for hid in candidate_pool
            if board.can_afford(hid)
        ]

        if not affordable:
            affordable = candidate_pool  # show even if can't afford

        # ── Adaptive Weights ──────────────────────────────
        weights = self.adaptive.compute_weights(board)

        # ── Score Semua Kandidat ──────────────────────────
        scored: List[Tuple[str, float, Dict]] = []
        for hid in affordable:
            if hid in board.all_heroes and (board.game_phase == "early" or not board.can_star_up(hid)):
                continue
            score, details = self.hybrid_score(hid, board, weights)
            scored.append((hid, score, details))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        # ── Build Recommendations ─────────────────────────
        recs = []
        for rank, (hid, score, details) in enumerate(top, 1):
            hero = HEROES[hid]
            rec = HeroRecommendation(
                rank=rank,
                hero_id=hid,
                hero_name=hero.name,
                cost=hero.cost,
                synergies=hero.synergies,
                role=hero.role,
                greedy_score=details["greedy_score"],
                heuristic_score=details["heuristic_score"],
                carry_score=details["carry_score_norm"],
                weights=weights,
                hybrid_score=score,
                h_details=details.get("h_details", {}),
            )
            recs.append(rec)

        target_syns = self.adaptive.recommend_target_synergies(board)

        return OptimizationResult(
            round_number=board.round_number,
            game_phase=board.game_phase,
            adaptive_weights=weights,
            recommendations=recs,
            target_synergies=target_syns,
            final_board=board,
        )

    # ─────────────────────────────────────────────
    #  Full Game Simulation
    # ─────────────────────────────────────────────

    def simulate_game(
        self,
        rounds: List[int],
        gold_per_round: List[int],
        verbose: bool = True
    ) -> List[OptimizationResult]:
        """
        Simulasikan pemilihan hero sepanjang beberapa round.
        Setiap round: terima gold → optimizer pilih hero terbaik.
        """
        board = BoardState(round_number=rounds[0], current_gold=gold_per_round[0])
        history: List[OptimizationResult] = []

        for i, (rnd, gold) in enumerate(zip(rounds, gold_per_round)):
            board.round_number = rnd
            board.max_slots = board._calculate_max_slots()
            board.current_gold += gold

            result = self.recommend(board, top_k=3)
            history.append(result)

            # Beli hero terbaik yang mampu dibayar
            best = result.recommendations[0] if result.recommendations else None
            if best and board.can_afford(best.hero_id):
                board.add_hero(best.hero_id)

        return history

    # ─────────────────────────────────────────────
    #  Best Build Finder
    # ─────────────────────────────────────────────

    def find_best_build(
        self,
        max_cost: int = 30,
        max_heroes: int = 6,
        target_synergies: Optional[List[str]] = None
    ) -> Tuple[List[str], float]:
        """
        Cari komposisi hero terbaik dengan budget dan slot terbatas.
        Menggunakan pendekatan beam search sederhana.

        Returns: (list_hero_ids, total_hybrid_score)
        """
        beam_width = 8  # Pertahankan N kandidat board terbaik
        beams: List[Tuple[List[str], float]] = [([], 0.0)]

        # Iterasi sebanyak max_heroes kali
        for step in range(max_heroes):
            new_beams: List[Tuple[List[str], float]] = []

            for current_heroes, _ in beams:
                # Buat board simulasi
                sim_board = BoardState(
                    round_number=20,  # Late game simulation
                    current_gold=max_cost - sum(HEROES[h].cost for h in current_heroes),
                    heroes_on_board=current_heroes.copy(),
                )

                if sim_board.current_gold < 1:
                    new_beams.append((current_heroes, self._evaluate_build(current_heroes)))
                    continue

                weights = self.adaptive.compute_weights(sim_board)

                # Coba tambah setiap hero yang mungkin
                for hid in HEROES:
                    if hid in current_heroes:
                        continue
                    hero = HEROES[hid]
                    if hero.cost > sim_board.current_gold:
                        continue

                    # Filter target synergy jika diberikan
                    if target_synergies:
                        if not any(s in hero.synergies for s in target_synergies):
                            continue

                    new_heroes = current_heroes + [hid]
                    score = self._evaluate_build(new_heroes)
                    new_beams.append((new_heroes, score))

            if not new_beams:
                break

            # Pertahankan beam_width terbaik
            new_beams.sort(key=lambda x: x[1], reverse=True)
            beams = new_beams[:beam_width]

        best = beams[0] if beams else ([], 0.0)
        return best[0], best[1]

    def _evaluate_build(self, hero_ids: List[str]) -> float:
        """Evaluasi kekuatan total sebuah komposisi hero."""
        if not hero_ids:
            return 0.0
        sim_board = BoardState(
            round_number=20,
            current_gold=0,
            heroes_on_board=hero_ids,
        )
        board_score = sim_board.total_power / 1000
        carry_score = self.heuristic.carry_combo_score(sim_board) / 10
        syn_score = self.heuristic.synergy_potential_score(sim_board) / 500
        return board_score * 0.4 + carry_score * 0.35 + syn_score * 0.25
