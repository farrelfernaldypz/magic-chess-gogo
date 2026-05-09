from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from algorithms.hybrid import HybridOptimizer, OptimizationResult
from algorithms.shop import roll_shop
from core.board import BoardState
from data.heroes import HEROES, Hero


@dataclass
class StrategyProfile:
    key: str
    name: str
    tagline: str
    description: str
    accent: str


@dataclass
class PhaseConfig:
    key: str
    label: str
    subtitle: str
    round_numbers: List[int]
    gold_gains: List[int]


@dataclass
class RecommendationView:
    rank: int
    hero_id: str
    hero_name: str
    cost: int
    role: str
    synergies: List[str]
    greedy: float
    heuristic: float
    carry: float
    hybrid: float
    adjusted: float
    strategy_bonus: float
    reason: str


@dataclass
class PhaseSnapshot:
    phase_key: str
    phase_label: str
    subtitle: str
    round_number: int
    gold_before: int
    gold_after: int
    board_before: List[str]
    board_after: List[str]
    shop_heroes: List[str]
    recommendations: List[RecommendationView]
    chosen_hero_id: Optional[str]
    chosen_reason: str
    adaptive_mode: str
    adaptive_weights: Dict[str, float]
    active_synergies_after: List[Dict[str, str | int]]
    commander_hp_before: int
    commander_hp_after: int
    result: OptimizationResult


@dataclass
class GameRun:
    seed: int
    profile: StrategyProfile
    snapshots: List[PhaseSnapshot] = field(default_factory=list)
    final_board: BoardState | None = None
    final_commander_hp: int = 100

    @property
    def final_power(self) -> float:
        return round(self.final_board.total_power, 2) if self.final_board else 0.0

    @property
    def final_synergies(self) -> List[str]:
        if not self.final_board:
            return []
        return [name for name, _, _ in self.final_board.active_synergies]


PROFILES: Dict[str, StrategyProfile] = {
    "farming": StrategyProfile(
        key="farming",
        name="Economy / Farming",
        tagline="Main aman, fleksibel, dan efisien",
        description="Mengutamakan value per gold, hero murah yang stabil, lalu transisi ke synergy yang paling dekat aktif.",
        accent="#f59e0b",
    ),
    "neobeast": StrategyProfile(
        key="neobeast",
        name="Stacking / Neobeasts",
        tagline="Main sabar buat scaling jangka panjang",
        description="Kalau muncul Neobeasts, algoritma akan memprioritaskan jalur stacking dan menjaga arah build sampai mid–late game.",
        accent="#22c55e",
    ),
    "aggressive": StrategyProfile(
        key="aggressive",
        name="Tempo / Aggressive",
        tagline="Gas dari awal biar HP commander aman",
        description="Mengutamakan kekuatan instan, synergy cepat aktif, dan hero dengan impact langsung agar board tempo lebih kuat.",
        accent="#ef4444",
    ),
}

PHASES: List[PhaseConfig] = [
    PhaseConfig(
        key="early",
        label="Early Game",
        subtitle="Babak 1–2 • fase buka board, farming, jungle, dan cari arah synergy",
        round_numbers=[4, 6],
        gold_gains=[8, 10],
    ),
    PhaseConfig(
        key="mid",
        label="Mid Game",
        subtitle="Babak 3–4 • fase stabilisasi board dan transisi synergy",
        round_numbers=[10, 14],
        gold_gains=[12, 14],
    ),
    PhaseConfig(
        key="late",
        label="Late Game",
        subtitle="Babak 5+ • fase capai core synergy, cari carry, dan rapikan board",
        round_numbers=[20, 26],
        gold_gains=[16, 18],
    ),
]


def _normalized_efficiency(hero: Hero) -> float:
    max_eff = max((h.power_index / max(h.cost, 1)) for h in HEROES.values())
    return (hero.power_index / max(hero.cost, 1)) / max_eff if max_eff else 0.0


def _strategy_adjustment(profile_key: str, hero_id: str, board: BoardState, phase_key: str, base_rec) -> tuple[float, str]:
    hero = HEROES[hero_id]
    counts = board.synergy_counts
    matching_syns = [syn for syn in hero.synergies if counts.get(syn, 0) > 0]
    near_tier_syns = []
    for syn in hero.synergies:
        current = counts.get(syn, 0)
        from data.synergies import SYNERGIES
        obj = SYNERGIES.get(syn)
        if not obj:
            continue
        nxt = obj.get_next_tier(current)
        if nxt and (nxt.required - (current + 1)) <= 1:
            near_tier_syns.append(syn)

    if profile_key == "farming":
        bonus = 0.18 * _normalized_efficiency(hero)
        if hero.cost <= 2:
            bonus += 0.10 if phase_key == "early" else 0.04
        if matching_syns:
            bonus += 0.08
        if near_tier_syns:
            bonus += 0.10
        if phase_key == "early" and hero.cost >= 4:
            bonus -= 0.08
        reason = "Value per gold tinggi"
        if near_tier_syns:
            reason += f", dekat aktifkan {near_tier_syns[0]}"
        elif matching_syns:
            reason += f", nyambung ke {matching_syns[0]}"
        return round(bonus, 4), reason

    if profile_key == "neobeast":
        bonus = 0.05 + 0.10 * base_rec.heuristic_score
        if "Neobeasts" in hero.synergies:
            existing = counts.get("Neobeasts", 0)
            bonus += 0.30 + existing * 0.08
            if phase_key == "late":
                bonus += 0.10
            reason = f"Masuk jalur Neobeasts (stack {existing + 1})"
            return round(bonus, 4), reason
        if matching_syns:
            bonus += 0.06
            return round(bonus, 4), f"Support buat arah scaling {matching_syns[0]}"
        return round(bonus, 4), "Hero fleksibel sambil nunggu core Neobeasts"

    # aggressive
    bonus = 0.14 * base_rec.greedy_score + 0.10 * base_rec.carry_score
    if matching_syns:
        bonus += 0.12
    if near_tier_syns:
        bonus += 0.08
    if hero.cost <= 3:
        bonus += 0.05
    reason = "Power instan bagus"
    if near_tier_syns:
        reason += f", cepat aktifkan {near_tier_syns[0]}"
    elif matching_syns:
        reason += f", langsung nyambung ke {matching_syns[0]}"
    return round(bonus, 4), reason


def _rank_with_profile(profile_key: str, board: BoardState, result: OptimizationResult) -> List[RecommendationView]:
    ranked: List[RecommendationView] = []
    for rec in result.recommendations:
        bonus, reason = _strategy_adjustment(profile_key, rec.hero_id, board, result.game_phase, rec)
        adjusted = round(rec.hybrid_score + bonus, 4)
        ranked.append(
            RecommendationView(
                rank=0,
                hero_id=rec.hero_id,
                hero_name=rec.hero_name,
                cost=rec.cost,
                role=rec.role,
                synergies=rec.synergies,
                greedy=rec.greedy_score,
                heuristic=rec.heuristic_score,
                carry=rec.carry_score,
                hybrid=rec.hybrid_score,
                adjusted=adjusted,
                strategy_bonus=bonus,
                reason=reason,
            )
        )
    ranked.sort(key=lambda x: x.adjusted, reverse=True)
    for idx, item in enumerate(ranked, 1):
        item.rank = idx
    return ranked


def _auto_place(board: BoardState, hero_id: str) -> str:
    hero = HEROES[hero_id]
    if not board.can_afford(hero_id):
        return "skip"

    if not board.board_full:
        board.add_hero(hero_id, to_board=True)
        return "board"

    # evaluasi replacement sederhana jika board penuh
    best_replace: Optional[str] = None
    best_score = board.total_power
    for existing in list(board.heroes_on_board):
        sim = board.copy()
        sim.remove_hero(existing)
        if sim.current_gold < hero.cost:
            continue
        sim.add_hero(hero_id, to_board=True)
        if sim.total_power > best_score + 8:
            best_score = sim.total_power
            best_replace = existing

    if best_replace:
        board.remove_hero(best_replace)
        board.add_hero(hero_id, to_board=True)
        return f"replace:{best_replace}"

    # kalau tidak cukup kuat untuk ganti board, simpan di bench bila bisa
    board.add_hero(hero_id, to_board=False)
    return "bench"


def _simulate_round_damage(board: BoardState, phase_key: str, profile_key: str) -> int:
    target = {"early": 900, "mid": 2200, "late": 4200}[phase_key]
    aggression_boost = 1.06 if profile_key == "aggressive" else 1.0
    scaling_boost = 1.04 if profile_key == "neobeast" and phase_key == "late" else 1.0
    effective_power = board.total_power * aggression_boost * scaling_boost
    ratio = effective_power / target if target else 1.0
    if ratio >= 1.28:
        return 0
    if ratio >= 1.0:
        return 1
    if ratio >= 0.8:
        return 4
    if ratio >= 0.6:
        return 7
    return 10


def simulate_profile_game(seed: int, profile_key: str) -> GameRun:
    rng = random.Random(seed)
    optimizer = HybridOptimizer()
    profile = PROFILES[profile_key]

    board = BoardState(round_number=2, current_gold=5, heroes_on_board=[])
    commander_hp = 100
    snapshots: List[PhaseSnapshot] = []

    for phase in PHASES:
        phase_snap: Optional[PhaseSnapshot] = None
        for round_no, income in zip(phase.round_numbers, phase.gold_gains):
            board.round_number = round_no
            board.max_slots = board._calculate_max_slots()
            board.current_gold += income

            gold_before = board.current_gold
            hp_before = commander_hp
            board_before = board.heroes_on_board.copy()
            shop = roll_shop(board, shop_size=5, rng=rng, exclude_owned=True)
            result = optimizer.recommend(board, candidate_pool=shop.shop_heroes, top_k=5)
            ranked = _rank_with_profile(profile_key, board, result)
            chosen = ranked[0].hero_id if ranked else None
            chosen_reason = ranked[0].reason if ranked else "Tidak ada kandidat"

            if chosen:
                action = _auto_place(board, chosen)
                if action.startswith("replace:"):
                    old = HEROES[action.split(":", 1)[1]].name
                    chosen_reason += f" • mengganti {old}"
                elif action == "bench":
                    chosen_reason += " • disimpan di bench"
                elif action == "skip":
                    chosen_reason += " • gold tidak cukup"

            hp_loss = _simulate_round_damage(board, phase.key, profile_key)
            commander_hp = max(0, commander_hp - hp_loss)

            active_syns = [
                {
                    "name": name,
                    "count": count,
                    "tier": tier.required,
                    "effect": tier.description,
                }
                for name, tier, count in board.active_synergies
            ]

            phase_snap = PhaseSnapshot(
                phase_key=phase.key,
                phase_label=phase.label,
                subtitle=phase.subtitle,
                round_number=round_no,
                gold_before=gold_before,
                gold_after=board.current_gold,
                board_before=board_before,
                board_after=board.heroes_on_board.copy(),
                shop_heroes=shop.shop_heroes,
                recommendations=ranked[:5],
                chosen_hero_id=chosen,
                chosen_reason=chosen_reason,
                adaptive_mode=result.adaptive_weights.strategy_mode,
                adaptive_weights={
                    "greedy": result.adaptive_weights.alpha_greedy,
                    "heuristic": result.adaptive_weights.beta_heuristic,
                    "carry": result.adaptive_weights.gamma_carry,
                },
                active_synergies_after=active_syns,
                commander_hp_before=hp_before,
                commander_hp_after=commander_hp,
                result=result,
            )

        if phase_snap:
            snapshots.append(phase_snap)

    return GameRun(
        seed=seed,
        profile=profile,
        snapshots=snapshots,
        final_board=board,
        final_commander_hp=commander_hp,
    )


def simulate_all_profiles(seed: int) -> Dict[str, GameRun]:
    runs: Dict[str, GameRun] = {}
    for idx, key in enumerate(PROFILES):
        runs[key] = simulate_profile_game(seed + (idx * 97), key)
    return runs
