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
    checkpoint_labels: List[str]
    levels: List[int]


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
    checkpoint_label: str
    player_level: int
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
    carry_hero_id: Optional[str]
    carry_reason: str
    decision_algorithm: str
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
        name="Farming / Scavenger",
        tagline="Ambil ekonomi dari Scavenger",
        description="Dipakai saat early mendapat hero Scavenger. Algoritma memprioritaskan Phoveus, Leona, atau Floryn untuk mengaktifkan bonus farming.",
        accent="#f59e0b",
    ),
    "neobeast": StrategyProfile(
        key="neobeast",
        name="Stacking / Neobeasts",
        tagline="Main sabar buat scaling jangka panjang",
        description="Kalau muncul Neobeasts, algoritma akan memprioritaskan jalur stacking dan menjaga arah build sampai midâ€“late game.",
        accent="#22c55e",
    ),
    "normal": StrategyProfile(
        key="normal",
        name="Normal",
        tagline="Main adaptif sesuai shop",
        description="Bermain normal tanpa memaksa farming Scavenger atau stacking Neobeasts. Pilihan hero mengikuti kombinasi power, synergy terdekat, dan carry terbaik yang tersedia.",
        accent="#278dff",
    ),
}

PHASES: List[PhaseConfig] = [
    PhaseConfig(
        key="early",
        label="Early Game",
        subtitle="Checkpoint 2-1 dan 2-5 setelah fate box pertama; Greedy membaca fondasi awal",
        round_numbers=[6, 8],
        gold_gains=[18, 12],
        checkpoint_labels=["2-1", "2-5"],
        levels=[5, 6],
    ),
    PhaseConfig(
        key="mid",
        label="Mid Game",
        subtitle="Checkpoint 3-2 dan 4-1; Heuristic mengevaluasi synergy dan carry transisi",
        round_numbers=[12, 16],
        gold_gains=[14, 16],
        checkpoint_labels=["3-2", "4-1"],
        levels=[7, 8],
    ),
    PhaseConfig(
        key="late",
        label="Late Game",
        subtitle="Checkpoint 5-1 dan 6-1; Adaptive finalisasi carry dan lineup",
        round_numbers=[22, 28],
        gold_gains=[18, 20],
        checkpoint_labels=["5-1", "6-1"],
        levels=[9, 10],
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
        bonus = 0.08 * _normalized_efficiency(hero)
        if "Scavenger" in hero.synergies:
            existing = counts.get("Scavenger", 0)
            bonus += 0.42 + existing * 0.12
            if phase_key == "early":
                bonus += 0.16
            reason = f"Prioritas farming Scavenger ({existing + 1}/3)"
            return round(bonus, 4), reason
        if phase_key == "early" and "Neobeasts" in hero.synergies:
            bonus -= 0.16
        if hero.cost <= 2:
            bonus += 0.04 if phase_key == "early" else 0.02
        if matching_syns:
            bonus += 0.04
        if near_tier_syns:
            bonus += 0.05
        if phase_key == "early" and hero.cost >= 4:
            bonus -= 0.08
        reason = "Opsi sementara sambil mencari Scavenger"
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

    # normal
    bonus = 0.08 * base_rec.greedy_score + 0.10 * base_rec.heuristic_score + 0.08 * base_rec.carry_score
    if matching_syns:
        bonus += 0.08
    if near_tier_syns:
        bonus += 0.06
    if phase_key == "early" and ("Scavenger" in hero.synergies or "Neobeasts" in hero.synergies):
        bonus -= 0.04
    reason = "Pilihan normal paling stabil"
    if near_tier_syns:
        reason += f", dekat aktifkan {near_tier_syns[0]}"
    elif matching_syns:
        reason += f", nyambung ke {matching_syns[0]}"
    return round(bonus, 4), reason


def _phase_algorithm_score(rec, phase_key: str) -> tuple[float, str]:
    if phase_key == "early":
        return rec.greedy_score, "Greedy"
    if phase_key == "mid":
        return rec.heuristic_score + (rec.carry_score * 0.25), "Heuristic"
    return rec.hybrid_score, "Adaptive"


def _carry_priority_bonus(hero_id: str, phase_key: str, current_carry_id: Optional[str]) -> float:
    hero = HEROES[hero_id]
    if hero.role != "Carry":
        return 0.0

    bonus = 0.05
    if phase_key == "early":
        bonus += 0.06
    elif phase_key == "mid":
        bonus += 0.12
    else:
        bonus += 0.18 if hero.cost >= 5 else 0.08

    if current_carry_id:
        current = HEROES[current_carry_id]
        if hero_id == current_carry_id:
            bonus += 0.18
        elif hero.cost > current.cost and hero.cost >= 5:
            bonus += 0.14

    return bonus


def _rank_with_profile(
    profile_key: str,
    board: BoardState,
    result: OptimizationResult,
    current_carry_id: Optional[str] = None,
) -> List[RecommendationView]:
    ranked: List[RecommendationView] = []
    for rec in result.recommendations:
        bonus, reason = _strategy_adjustment(profile_key, rec.hero_id, board, result.game_phase, rec)
        phase_score, algorithm_name = _phase_algorithm_score(rec, result.game_phase)
        carry_bonus = _carry_priority_bonus(rec.hero_id, result.game_phase, current_carry_id)
        adjusted = round(phase_score + bonus + carry_bonus, 4)
        reason = f"{algorithm_name}: {reason}"
        if carry_bonus and HEROES[rec.hero_id].role == "Carry":
            reason += ", kandidat carry"
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


def _best_carry_on_board(board: BoardState) -> Optional[str]:
    carries = [hid for hid in board.heroes_on_board if hid in HEROES and HEROES[hid].role == "Carry"]
    if not carries:
        return None
    return max(carries, key=lambda hid: (HEROES[hid].cost, HEROES[hid].carry_score, HEROES[hid].power_index))


def _should_switch_carry(current_carry_id: Optional[str], candidate_id: str, phase_key: str, current_gold: int) -> bool:
    candidate = HEROES[candidate_id]
    if candidate.role != "Carry":
        return False
    if not current_carry_id:
        return True

    current = HEROES[current_carry_id]
    if candidate_id == current_carry_id:
        return False

    upgrade_value = (candidate.cost - current.cost) * 0.45 + (candidate.carry_score - current.carry_score)
    if phase_key == "late" and candidate.cost >= 5 and current.cost < 5 and current_gold >= candidate.cost:
        return upgrade_value >= 0.35
    if phase_key == "mid" and candidate.cost >= current.cost:
        return upgrade_value >= 0.75
    return upgrade_value >= 1.2


def _auto_place(board: BoardState, hero_id: str, locked_carry_id: Optional[str] = None) -> str:
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
        if existing == locked_carry_id:
            continue
        sim = board.copy()
        sim.remove_hero(existing)
        if sim.current_gold < hero.cost:
            continue
        sim.add_hero(hero_id, to_board=True)
        if sim.total_power > best_score + 260:
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
    aggression_boost = 1.0
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


def _checkpoint_fill_pool(profile_key: str) -> List[str]:
    if profile_key == "farming":
        preferred = ["Scavenger", "Exorcist", "KOF", "Luminexus"]
    elif profile_key == "neobeast":
        preferred = ["Neobeasts", "Marksman", "Mage", "Swiftblade"]
    else:
        preferred = ["Mage", "Marksman", "Swiftblade", "Weapon Master", "Luminexus"]

    pool = [
        hid for hid, hero in HEROES.items()
        if hero.cost <= 4 and any(syn in preferred for syn in hero.synergies)
    ]
    if not pool:
        pool = [hid for hid, hero in HEROES.items() if hero.cost <= 4]
    return pool


def _ensure_checkpoint_board(board: BoardState, target_slots: int, profile_key: str, rng: random.Random) -> None:
    """Simulasikan board yang sudah terbentuk sebelum checkpoint rekomendasi."""
    board.max_slots = target_slots
    pool = [hid for hid in _checkpoint_fill_pool(profile_key) if hid not in board.all_heroes]
    rng.shuffle(pool)

    while len(board.heroes_on_board) < target_slots and pool:
        board.heroes_on_board.append(pool.pop())


def simulate_profile_game(seed: int, profile_key: str) -> GameRun:
    rng = random.Random(seed)
    optimizer = HybridOptimizer()
    profile = PROFILES[profile_key]

    board = BoardState(round_number=2, current_gold=5, heroes_on_board=[])
    commander_hp = 100
    current_carry_id: Optional[str] = None
    snapshots: List[PhaseSnapshot] = []

    for phase in PHASES:
        phase_snap: Optional[PhaseSnapshot] = None
        for round_no, income, checkpoint_label, level in zip(
            phase.round_numbers,
            phase.gold_gains,
            phase.checkpoint_labels,
            phase.levels,
        ):
            board.round_number = round_no
            board.max_slots = level
            _ensure_checkpoint_board(board, level, profile_key, rng)
            board.current_gold += income

            gold_before = board.current_gold
            hp_before = commander_hp
            board_before = board.heroes_on_board.copy()
            shop = roll_shop(board, shop_size=5, rng=rng, exclude_owned=True)
            result = optimizer.recommend(board, candidate_pool=shop.shop_heroes, top_k=5)
            ranked = _rank_with_profile(profile_key, board, result, current_carry_id)
            decision_algorithm = {"early": "Greedy", "mid": "Heuristic", "late": "Adaptive"}[phase.key]
            chosen = ranked[0].hero_id if ranked else None
            chosen_reason = ranked[0].reason if ranked else "Tidak ada kandidat"
            carry_reason = "Belum ada carry utama"

            if current_carry_id and current_carry_id not in board.heroes_on_board:
                current_carry_id = _best_carry_on_board(board)

            if phase.key == "late" and current_carry_id:
                current_carry = HEROES[current_carry_id]
                better_cost5 = next(
                    (
                        item for item in ranked
                        if HEROES[item.hero_id].role == "Carry"
                        and HEROES[item.hero_id].cost >= 5
                        and _should_switch_carry(current_carry_id, item.hero_id, phase.key, board.current_gold)
                    ),
                    None,
                )
                if current_carry.cost >= 5 and not better_cost5:
                    chosen = current_carry_id
                    chosen_reason = (
                        f"Adaptive: pertahankan carry {current_carry.name}; "
                        "late game fokus upgrade/star-up karena carry premium sudah terbentuk"
                    )
                    carry_reason = "Carry late dipertahankan"
                elif better_cost5:
                    chosen = better_cost5.hero_id
                    chosen_reason = better_cost5.reason + ", upgrade carry late ke cost 5"

            if chosen:
                if chosen == current_carry_id and chosen in board.heroes_on_board:
                    action = "hold"
                else:
                    locked = current_carry_id if phase.key == "late" else None
                    action = _auto_place(board, chosen, locked_carry_id=locked)

                if HEROES[chosen].role == "Carry" and action != "skip":
                    if _should_switch_carry(current_carry_id, chosen, phase.key, gold_before):
                        previous = HEROES[current_carry_id].name if current_carry_id else None
                        current_carry_id = chosen
                        carry_reason = (
                            f"Carry utama ditetapkan ke {HEROES[chosen].name}"
                            if not previous
                            else f"Carry diganti dari {previous} ke {HEROES[chosen].name}"
                        )
                    elif not current_carry_id:
                        current_carry_id = _best_carry_on_board(board)
                        if current_carry_id:
                            carry_reason = f"Carry utama sementara: {HEROES[current_carry_id].name}"
                if action.startswith("replace:"):
                    old = HEROES[action.split(":", 1)[1]].name
                    chosen_reason += f" â€¢ mengganti {old}"
                elif action == "bench":
                    chosen_reason += " â€¢ disimpan di bench"
                elif action == "skip":
                    chosen_reason += " â€¢ gold tidak cukup"

            if chosen and action == "hold":
                chosen_reason += " - tidak membeli hero baru"

            if not current_carry_id:
                current_carry_id = _best_carry_on_board(board)
                if current_carry_id:
                    carry_reason = f"Carry utama sementara: {HEROES[current_carry_id].name}"
            elif carry_reason == "Belum ada carry utama":
                carry_reason = f"Carry utama dipertahankan: {HEROES[current_carry_id].name}"

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
                checkpoint_label=checkpoint_label,
                player_level=level,
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
                carry_hero_id=current_carry_id,
                carry_reason=carry_reason,
                decision_algorithm=decision_algorithm,
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

