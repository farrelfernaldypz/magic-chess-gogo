from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from algorithms.hybrid import HybridOptimizer, OptimizationResult
from algorithms.shop import roll_shop
from core.board import BoardState
from data.heroes import HEROES, Hero
from data.synergies import SYNERGIES


TIER_SIX = 6
STAR_ROLLS_BY_PHASE = {
    "early": 3,
    "mid": 7,
    "late": 14,
}
CORE_SYNERGY_TARGETS = {
    "farming": ["KOF", "Exorcist", "Luminexus", "Swiftblade", "Marksman", "Mage", "Weapon Master"],
    "neobeast": ["Neobeasts"],
    "normal": ["Swiftblade", "Marksman", "Mage", "Weapon Master", "KOF", "Exorcist", "Luminexus"],
}


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
    star_level: int
    copies: int
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
    board_after_stars: Dict[str, int]
    shop_heroes: List[str]
    recommendations: List[RecommendationView]
    chosen_hero_id: Optional[str]
    chosen_star: int
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


def _synergy_has_tier(synergy_name: str, required: int = TIER_SIX) -> bool:
    synergy = SYNERGIES.get(synergy_name)
    return bool(synergy and any(tier.required == required for tier in synergy.tiers))


def _synergy_can_reach_tier(synergy_name: str, required: int = TIER_SIX) -> bool:
    return _synergy_has_tier(synergy_name, required) and len(_hero_ids_for_synergy(synergy_name)) >= required


def _hero_ids_for_synergy(synergy_name: str, max_cost: int = 5) -> List[str]:
    heroes = [
        hid for hid, hero in HEROES.items()
        if synergy_name in hero.synergies and hero.cost <= max_cost
    ]
    return sorted(
        heroes,
        key=lambda hid: (
            HEROES[hid].role != "Carry",
            -HEROES[hid].cost,
            -HEROES[hid].carry_score,
            HEROES[hid].name,
        ),
    )


def _best_carry_synergy(carry_id: Optional[str], fallback: List[str]) -> Optional[str]:
    if carry_id in HEROES:
        carry = HEROES[carry_id]
        carry_syns = [
            syn for syn in carry.synergies
            if syn not in {"Scavenger", "Mystic Meow"} and _synergy_can_reach_tier(syn)
        ]
        if carry_syns:
            return max(
                carry_syns,
                key=lambda syn: (
                    syn in fallback,
                    len(_hero_ids_for_synergy(syn)),
                    SYNERGIES[syn].get_active_tier(TIER_SIX).power_bonus if SYNERGIES[syn].get_active_tier(TIER_SIX) else 0,
                ),
            )

    for syn in fallback:
        if _synergy_can_reach_tier(syn):
            return syn
    return None


def _target_synergy(profile_key: str, board: BoardState, phase_key: str, current_carry_id: Optional[str]) -> Optional[str]:
    if profile_key == "neobeast":
        return "Neobeasts"
    if profile_key == "farming" and phase_key == "early":
        return "Scavenger"
    fallback = CORE_SYNERGY_TARGETS.get(profile_key, CORE_SYNERGY_TARGETS["normal"])
    return _best_carry_synergy(current_carry_id or _best_carry_on_board(board), fallback)


def _tier_six_targets(hero: Hero, board: BoardState) -> List[tuple[str, int, int, bool]]:
    counts = board.synergy_counts
    targets: List[tuple[str, int, int, bool]] = []

    for syn in hero.synergies:
        current = counts.get(syn, 0)
        synergy = SYNERGIES.get(syn)
        if current <= 0 or not synergy:
            continue
        if not _synergy_can_reach_tier(syn):
            continue
        if current >= TIER_SIX:
            continue

        after = current + 1
        targets.append((syn, current, after, after >= TIER_SIX))

    return sorted(targets, key=lambda item: (item[3], item[2], item[0]), reverse=True)


def _tier_six_progress_bonus(hero_id: str, board: BoardState, phase_key: str) -> float:
    if phase_key not in {"mid", "late"}:
        return 0.0

    hero = HEROES[hero_id]
    targets = _tier_six_targets(hero, board)
    if not targets:
        return 0.0

    best = 0.0
    for _syn, current, after, completes in targets:
        needed_before = TIER_SIX - current
        progress = after / TIER_SIX
        bonus = 0.08 + (hero.cost / 5.0) * 0.12 + progress * 0.10

        if completes:
            bonus += 0.32
        elif needed_before <= 2:
            bonus += 0.16
        elif needed_before <= 3:
            bonus += 0.08

        if hero.role == "Carry" and hero.cost >= 4:
            bonus += 0.08
        if phase_key == "late":
            bonus *= 1.25

        best = max(best, bonus)

    return round(min(best, 0.65), 4)


def _tier_six_reason(hero_id: str, board: BoardState) -> str:
    hero = HEROES[hero_id]
    targets = _tier_six_targets(hero, board)
    if not targets:
        return ""

    syn, _current, after, completes = targets[0]
    if completes:
        return f"aktifkan {syn} 6"
    return f"arah {syn} 6 ({after}/6)"


def _active_synergy_count_after(hero_id: str, board: BoardState) -> int:
    sim = board.copy()
    if hero_id not in sim.heroes_on_board and not sim.board_full:
        sim.heroes_on_board.append(hero_id)
    return len(sim.active_synergies)


def _mystic_meow_bonus(hero_id: str, board: BoardState, phase_key: str) -> float:
    if "Mystic Meow" not in HEROES[hero_id].synergies or phase_key == "early":
        return 0.0
    active_count = _active_synergy_count_after(hero_id, board)
    bonus = 0.08 + min(active_count, 11) * 0.025
    if active_count >= 9:
        bonus += 0.18
    if active_count >= 11:
        bonus += 0.16
    return round(min(bonus, 0.55), 4)


def _mystic_meow_reason(hero_id: str, board: BoardState) -> str:
    active_count = _active_synergy_count_after(hero_id, board)
    if active_count >= 11:
        return "Mystic Meow kuat karena 11 sinergi aktif"
    if active_count >= 9:
        return "Mystic Meow aktif karena 9 sinergi aktif"
    return f"Mystic Meow scaling dari {active_count} sinergi aktif"


def _star_upgrade_bonus(hero_id: str, board: BoardState, phase_key: str, current_carry_id: Optional[str]) -> float:
    if hero_id not in board.all_heroes or not board.can_star_up(hero_id):
        return 0.0

    hero = HEROES[hero_id]
    copies = board.copies_of(hero_id)
    next_copies = copies + 1
    bonus = 0.10 + hero.cost * 0.025

    if next_copies >= 9:
        bonus += 0.70
    elif next_copies >= 3 and copies < 3:
        bonus += 0.42
    elif copies >= 3:
        bonus += 0.16
    else:
        bonus += 0.08

    if hero_id == current_carry_id:
        bonus += 0.30 if phase_key == "late" else 0.16
    elif phase_key == "late" and hero.role == "Carry":
        bonus += 0.12

    if phase_key == "late":
        bonus *= 1.25

    return round(min(bonus, 1.15), 4)


def _star_upgrade_reason(hero_id: str, board: BoardState) -> str:
    hero = HEROES[hero_id]
    copies = board.copies_of(hero_id)
    next_copies = copies + 1
    if next_copies >= 9:
        return f"upgrade {hero.name} ke bintang 3 ({next_copies}/9 copy)"
    if next_copies >= 3 and copies < 3:
        return f"upgrade {hero.name} ke bintang 2 ({next_copies}/3 copy)"
    target = 9 if copies >= 3 else 3
    return f"kumpulkan copy {hero.name} untuk bintang berikutnya ({next_copies}/{target})"


def _target_synergy_bonus(hero_id: str, board: BoardState, phase_key: str, target_syn: Optional[str]) -> float:
    if not target_syn or target_syn not in HEROES[hero_id].synergies:
        return 0.0

    current = board.synergy_counts.get(target_syn, 0)
    after = current + (0 if hero_id in board.heroes_on_board else 1)
    target = TIER_SIX if _synergy_can_reach_tier(target_syn) else 3
    bonus = 0.20 + min(after, target) / target * 0.35

    if after >= target:
        bonus += 0.45
    elif target - after <= 1:
        bonus += 0.26
    elif target - after <= 2:
        bonus += 0.14

    if phase_key == "mid" and target_syn == "Neobeasts":
        bonus *= 1.35
    if phase_key == "late":
        bonus *= 1.18

    return round(min(bonus, 1.15), 4)


def _target_synergy_reason(target_syn: Optional[str], board: BoardState, hero_id: str) -> str:
    if not target_syn:
        return ""
    current = board.synergy_counts.get(target_syn, 0)
    after = current + (0 if hero_id in board.heroes_on_board else 1)
    target = TIER_SIX if _synergy_can_reach_tier(target_syn) else 3
    if after >= target:
        return f"nyalakan {target_syn} {target}"
    return f"kejar {target_syn} {target} ({after}/{target})"


def _strategy_adjustment(profile_key: str, hero_id: str, board: BoardState, phase_key: str, base_rec) -> tuple[float, str]:
    hero = HEROES[hero_id]
    counts = board.synergy_counts
    matching_syns = [syn for syn in hero.synergies if counts.get(syn, 0) > 0]
    near_tier_syns = []
    for syn in hero.synergies:
        current = counts.get(syn, 0)
        obj = SYNERGIES.get(syn)
        if not obj:
            continue
        nxt = obj.get_next_tier(current)
        if nxt and nxt.required == TIER_SIX and (nxt.required - (current + 1)) <= 1:
            near_tier_syns.append(syn)

    if profile_key == "farming":
        bonus = 0.08 * _normalized_efficiency(hero)
        if "Scavenger" in hero.synergies and phase_key != "late":
            existing = counts.get("Scavenger", 0)
            if phase_key == "early":
                bonus += 0.42 + existing * 0.12 + 0.16
                reason = f"Prioritas farming Scavenger ({existing + 1}/3)"
            else:
                bonus += 0.14 + existing * 0.04
                reason = f"Transisi farming Scavenger ({existing + 1}/3)"
            return round(bonus, 4), reason
        if phase_key == "late":
            if "Scavenger" in hero.synergies:
                bonus -= 0.30
            if hero.cost >= 4:
                bonus += 0.08
            if matching_syns:
                bonus += 0.07
            if near_tier_syns:
                bonus += 0.08
            reason = "Farming selesai; fokus carry, star-up, dan synergy 6"
            if near_tier_syns:
                reason += f", dekat aktifkan {near_tier_syns[0]}"
            elif matching_syns:
                reason += f", nyambung ke {matching_syns[0]}"
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
        reason = "Opsi sementara sambil mencari Scavenger" if phase_key == "early" else "Transisi ke carry dan synergy 6"
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

    bonus = 0.03
    if phase_key == "early":
        bonus += 0.05
    elif phase_key == "mid":
        bonus += hero.cost * 0.035
        if hero.cost >= 4:
            bonus += 0.08
        elif hero.cost <= 2:
            bonus -= 0.03
    else:
        if hero.cost <= 2:
            bonus -= 0.14
        elif hero.cost == 3:
            bonus += 0.02
        else:
            bonus += 0.12 + (hero.cost - 4) * 0.08

    if current_carry_id:
        current = HEROES[current_carry_id]
        shared_synergy = bool(set(hero.synergies) & set(current.synergies))
        if hero_id == current_carry_id:
            bonus += 0.18
        elif hero.cost > current.cost:
            bonus += 0.10 if shared_synergy else 0.04
        elif phase_key in {"mid", "late"} and hero.cost < current.cost:
            bonus -= 0.18

    return round(bonus, 4)


def _rank_with_profile(
    profile_key: str,
    board: BoardState,
    result: OptimizationResult,
    current_carry_id: Optional[str] = None,
) -> List[RecommendationView]:
    ranked: List[RecommendationView] = []
    recommendations = result.recommendations
    target_syn = _target_synergy(profile_key, board, result.game_phase, current_carry_id)
    if result.game_phase == "late":
        non_scavenger = [rec for rec in recommendations if "Scavenger" not in HEROES[rec.hero_id].synergies]
        if non_scavenger:
            recommendations = non_scavenger

    for rec in recommendations:
        bonus, reason = _strategy_adjustment(profile_key, rec.hero_id, board, result.game_phase, rec)
        phase_score, algorithm_name = _phase_algorithm_score(rec, result.game_phase)
        carry_bonus = _carry_priority_bonus(rec.hero_id, result.game_phase, current_carry_id)
        is_duplicate = rec.hero_id in board.all_heroes
        tier_six_bonus = 0.0 if is_duplicate else _tier_six_progress_bonus(rec.hero_id, board, result.game_phase)
        mystic_bonus = 0.0 if is_duplicate else _mystic_meow_bonus(rec.hero_id, board, result.game_phase)
        star_bonus = _star_upgrade_bonus(rec.hero_id, board, result.game_phase, current_carry_id)
        target_bonus = 0.0 if is_duplicate else _target_synergy_bonus(rec.hero_id, board, result.game_phase, target_syn)
        off_target_penalty = 0.0
        if target_syn and not is_duplicate and target_syn not in HEROES[rec.hero_id].synergies and result.game_phase != "early":
            off_target_penalty = 0.55 if profile_key == "neobeast" else 0.34
        adjusted = round(phase_score + bonus + carry_bonus + tier_six_bonus + mystic_bonus + star_bonus + target_bonus - off_target_penalty, 4)
        reason = f"{algorithm_name}: {reason}"
        if star_bonus:
            reason = f"{algorithm_name}: {_star_upgrade_reason(rec.hero_id, board)}"
        if target_bonus:
            reason += f", {_target_synergy_reason(target_syn, board, rec.hero_id)}"
        if tier_six_bonus:
            reason += f", {_tier_six_reason(rec.hero_id, board)}"
            if HEROES[rec.hero_id].cost >= 4:
                reason += ", cost tinggi"
        if mystic_bonus:
            reason += f", {_mystic_meow_reason(rec.hero_id, board)}"
        if carry_bonus > 0 and HEROES[rec.hero_id].role == "Carry":
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
                star_level=board.star_level(rec.hero_id),
                copies=board.copies_of(rec.hero_id),
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

    counts = board.synergy_counts

    def tier_six_progress(hid: str) -> int:
        return max(
            (
                counts.get(syn, 0)
                for syn in HEROES[hid].synergies
                if _synergy_can_reach_tier(syn)
            ),
            default=0,
        )

    def carry_key(hid: str) -> tuple[bool, bool, int, int, float, float]:
        hero = HEROES[hid]
        progress = tier_six_progress(hid)
        return progress >= TIER_SIX, progress > 0, progress, hero.cost, hero.carry_score, hero.power_index

    return max(carries, key=carry_key)


def _should_refocus_existing_carry(current_carry_id: Optional[str], candidate_id: Optional[str], phase_key: str) -> bool:
    if not candidate_id or candidate_id == current_carry_id:
        return False
    if not current_carry_id:
        return True
    if phase_key not in {"mid", "late"}:
        return False

    current = HEROES[current_carry_id]
    candidate = HEROES[candidate_id]
    shared_synergy = bool(set(candidate.synergies) & set(current.synergies))

    def has_tier_six_path(hero_id: str) -> bool:
        return any(_synergy_can_reach_tier(syn) for syn in HEROES[hero_id].synergies)

    if phase_key == "late" and has_tier_six_path(candidate_id) and not has_tier_six_path(current_carry_id):
        return True

    if candidate.cost >= 4 and current.cost <= 2:
        return True
    if candidate.cost > current.cost and (shared_synergy or phase_key == "late"):
        return True
    if candidate.cost == current.cost and candidate.carry_score > current.carry_score + 0.6:
        return True
    return False


def _should_switch_carry(current_carry_id: Optional[str], candidate_id: str, phase_key: str, current_gold: int) -> bool:
    candidate = HEROES[candidate_id]
    if candidate.role != "Carry":
        return False
    if not current_carry_id:
        return True

    current = HEROES[current_carry_id]
    if candidate_id == current_carry_id:
        return False

    shared_synergy = bool(set(candidate.synergies) & set(current.synergies))
    if phase_key in {"mid", "late"} and candidate.cost < current.cost:
        return False
    if phase_key == "late" and candidate.cost <= 2 and current.cost >= 3:
        return False

    upgrade_value = (candidate.cost - current.cost) * 0.45 + (candidate.carry_score - current.carry_score)
    if phase_key == "late":
        if candidate.cost >= 4 and candidate.cost >= current.cost and current_gold >= candidate.cost:
            threshold = 0.25 if shared_synergy else 0.65
            if candidate.cost >= 5 and current.cost < 5:
                threshold -= 0.15
            return upgrade_value >= threshold
        return False
    if phase_key == "mid" and candidate.cost >= current.cost:
        threshold = 0.45 if shared_synergy else 0.75
        return upgrade_value >= threshold
    return upgrade_value >= 1.2


def _auto_place(
    board: BoardState,
    hero_id: str,
    locked_carry_id: Optional[str] = None,
    protected_synergy: Optional[str] = None,
) -> str:
    hero = HEROES[hero_id]
    if not board.can_afford(hero_id):
        return "skip"

    if hero_id in board.all_heroes and board.can_star_up(hero_id):
        before = board.star_level(hero_id)
        board.add_hero(hero_id, to_board=False)
        after = board.star_level(hero_id)
        return f"star:{before}->{after}" if after > before else "copy"

    if not board.board_full:
        board.add_hero(hero_id, to_board=True)
        return "board"

    # evaluasi replacement sederhana jika board penuh
    best_replace: Optional[str] = None
    best_score = board.total_power
    for existing in list(board.heroes_on_board):
        if existing == locked_carry_id:
            continue
        if protected_synergy and protected_synergy in HEROES[existing].synergies and protected_synergy not in hero.synergies:
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
        hero_id = pool.pop()
        board.heroes_on_board.append(hero_id)
        board.hero_copies.setdefault(hero_id, 1)


def _replace_for_synergy(board: BoardState, hero_id: str, target_syn: str, protected: set[str]) -> None:
    if hero_id in board.heroes_on_board:
        return

    if not board.board_full:
        board.heroes_on_board.append(hero_id)
        board.hero_copies.setdefault(hero_id, 1)
        return

    candidates = [
        hid for hid in board.heroes_on_board
        if hid not in protected and target_syn not in HEROES[hid].synergies
    ]
    if not candidates:
        candidates = [hid for hid in board.heroes_on_board if hid not in protected]
    if not candidates:
        return

    old = min(
        candidates,
        key=lambda hid: (
            HEROES[hid].role == "Carry",
            HEROES[hid].cost,
            HEROES[hid].power_index,
        ),
    )
    board.heroes_on_board.remove(old)
    board.hero_copies.pop(old, None)
    board.heroes_on_board.append(hero_id)
    board.hero_copies.setdefault(hero_id, 1)


def _force_target_synergy(
    board: BoardState,
    profile_key: str,
    phase_key: str,
    checkpoint_label: str,
    current_carry_id: Optional[str],
    rng: random.Random,
) -> None:
    target_syn = _target_synergy(profile_key, board, phase_key, current_carry_id)
    if not target_syn:
        return

    if profile_key == "neobeast":
        target_count = 6 if phase_key in {"mid", "late"} else 4
    elif profile_key == "farming":
        target_count = 3 if phase_key == "early" else (4 if phase_key == "mid" else 6)
    else:
        target_count = 4 if phase_key == "mid" else (6 if phase_key == "late" else 3)

    target_count = min(target_count, board.max_slots, len(_hero_ids_for_synergy(target_syn)))
    protected = {current_carry_id} if current_carry_id else set()
    pool = _hero_ids_for_synergy(target_syn)

    if profile_key == "farming" and phase_key == "late":
        for hid in list(board.heroes_on_board):
            if "Scavenger" in HEROES[hid].synergies and hid not in protected:
                board.heroes_on_board.remove(hid)
                board.hero_copies.pop(hid, None)

    while board.synergy_counts.get(target_syn, 0) < target_count:
        options = [hid for hid in pool if hid not in board.heroes_on_board]
        if not options:
            break
        hero_id = max(
            options,
            key=lambda hid: (
                HEROES[hid].role == "Carry",
                HEROES[hid].cost <= max(3, board.max_slots - 3) or phase_key != "early",
                HEROES[hid].cost,
                HEROES[hid].carry_score,
            ),
        )
        _replace_for_synergy(board, hero_id, target_syn, protected)


def _ensure_late_carry_synergy(
    board: BoardState,
    profile_key: str,
    current_carry_id: Optional[str],
    rng: random.Random,
) -> Optional[str]:
    if not current_carry_id:
        return None

    fallback = CORE_SYNERGY_TARGETS.get(profile_key, CORE_SYNERGY_TARGETS["normal"])
    target_syn = _best_carry_synergy(current_carry_id, fallback)
    if not target_syn or not _synergy_can_reach_tier(target_syn):
        return target_syn

    board.max_slots = max(board.max_slots, 9)
    _force_target_synergy(board, profile_key, "late", "late", current_carry_id, rng)

    if board.synergy_counts.get(target_syn, 0) < TIER_SIX:
        protected = {current_carry_id}
        pool = _hero_ids_for_synergy(target_syn)
        while board.synergy_counts.get(target_syn, 0) < min(TIER_SIX, board.max_slots, len(pool)):
            options = [hid for hid in pool if hid not in board.heroes_on_board]
            if not options:
                break
            hero_id = max(
                options,
                key=lambda hid: (
                    HEROES[hid].role == "Carry",
                    HEROES[hid].cost,
                    HEROES[hid].carry_score,
                ),
            )
            _replace_for_synergy(board, hero_id, target_syn, protected)

    return target_syn


def _ensure_late_star_three(
    board: BoardState,
    current_carry_id: Optional[str],
    target_syn: Optional[str],
) -> Optional[str]:
    premium_ids = [hid for hid in board.heroes_on_board if hid in HEROES and HEROES[hid].cost >= 4]
    if not premium_ids:
        return None

    current_carry_syns = set(HEROES[current_carry_id].synergies) if current_carry_id in HEROES else set()

    def premium_star_candidate(hid: str) -> bool:
        hero = HEROES[hid]
        if hero.cost < 4:
            return False
        if target_syn and target_syn in hero.synergies:
            if hero.cost >= 5:
                return True
            same_syn_cost_four = [
                other for other in premium_ids
                if other != hid and target_syn in HEROES[other].synergies and HEROES[other].cost == 4
            ]
            return bool(same_syn_cost_four)
        if hid == current_carry_id and hero.cost >= 4:
            return True
        if hero.role == "Carry" and current_carry_syns & set(hero.synergies):
            return True
        return False

    for hid in list(board.hero_copies):
        if board.star_level(hid) >= 3 and not premium_star_candidate(hid):
            board.hero_copies[hid] = 8

    candidates = [hid for hid in premium_ids if premium_star_candidate(hid)]
    if not candidates:
        candidates = [
            hid for hid in premium_ids
            if HEROES[hid].role == "Carry" or hid == current_carry_id
        ]
    if not candidates:
        candidates = premium_ids

    existing_good_star = [
        hid for hid in candidates
        if board.star_level(hid) >= 3
    ]
    if existing_good_star:
        return None

    chosen = max(
        candidates,
        key=lambda hid: (
            bool(target_syn and target_syn in HEROES[hid].synergies),
            HEROES[hid].role == "Carry",
            HEROES[hid].cost >= 5,
            hid == current_carry_id,
            HEROES[hid].cost,
            HEROES[hid].carry_score,
            board.copies_of(hid),
        ),
    )
    board.hero_copies[chosen] = max(board.copies_of(chosen), 9)
    return chosen


def _background_star_shopping(
    board: BoardState,
    profile_key: str,
    phase_key: str,
    current_carry_id: Optional[str],
    rng: random.Random,
) -> List[str]:
    bought: List[str] = []
    target_syn = _target_synergy(profile_key, board, phase_key, current_carry_id)
    roll_count = STAR_ROLLS_BY_PHASE[phase_key]
    if current_carry_id:
        roll_count += 2 if phase_key == "mid" else 6 if phase_key == "late" else 0

    for _ in range(roll_count):
        board.current_gold += 4 if phase_key == "early" else 6 if phase_key == "mid" else 8
        shop = roll_shop(board, shop_size=5, rng=rng, exclude_owned=False)
        priority = []
        for hid in shop.shop_heroes:
            if not board.can_afford(hid):
                continue
            is_carry_copy = hid == current_carry_id and board.can_star_up(hid)
            is_core_copy = hid in board.heroes_on_board and board.can_star_up(hid) and (
                target_syn in HEROES[hid].synergies if target_syn else True
            )
            completes_star = board.copies_of(hid) + 1 in {3, 9}
            if is_carry_copy or (phase_key != "early" and is_core_copy):
                priority.append((is_carry_copy, completes_star, HEROES[hid].cost, hid))
        if not priority:
            continue

        _, _, _, hero_id = max(priority)
        if board.add_hero(hero_id, to_board=hero_id not in board.heroes_on_board):
            bought.append(hero_id)

    return bought


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

            if not current_carry_id:
                current_carry_id = _best_carry_on_board(board)
            elif phase.key == "late":
                current_carry_id = _best_carry_on_board(board) or current_carry_id
            _force_target_synergy(board, profile_key, phase.key, checkpoint_label, current_carry_id, rng)
            if current_carry_id and current_carry_id not in board.heroes_on_board:
                current_carry_id = _best_carry_on_board(board)
            _background_star_shopping(board, profile_key, phase.key, current_carry_id, rng)

            gold_before = board.current_gold
            hp_before = commander_hp
            board_before = board.heroes_on_board.copy()
            shop = roll_shop(board, shop_size=5, rng=rng, exclude_owned=False)
            result = optimizer.recommend(board, candidate_pool=shop.shop_heroes, top_k=5)
            ranked = _rank_with_profile(profile_key, board, result, current_carry_id)
            decision_algorithm = {"early": "Greedy", "mid": "Heuristic", "late": "Adaptive"}[phase.key]
            target_syn = _target_synergy(profile_key, board, phase.key, current_carry_id)
            chosen = ranked[0].hero_id if ranked else None
            chosen_reason = ranked[0].reason if ranked else "Tidak ada kandidat"
            carry_reason = "Belum ada carry utama"

            if target_syn and phase.key in {"mid", "late"}:
                target_goal = 6 if _synergy_can_reach_tier(target_syn) else 3
                if board.synergy_counts.get(target_syn, 0) < min(target_goal, board.max_slots):
                    target_pick = next(
                        (
                            item for item in ranked
                            if target_syn in HEROES[item.hero_id].synergies and item.hero_id not in board.heroes_on_board
                        ),
                        None,
                    )
                    if target_pick:
                        chosen = target_pick.hero_id
                        chosen_reason = target_pick.reason

            if current_carry_id and current_carry_id not in board.heroes_on_board:
                current_carry_id = _best_carry_on_board(board)

            if phase.key == "late" and current_carry_id:
                current_carry = HEROES[current_carry_id]
                star_candidates = [
                    item for item in ranked
                    if item.hero_id in board.all_heroes and board.can_star_up(item.hero_id)
                ]
                best_star = max(
                    star_candidates,
                    key=lambda item: (
                        item.hero_id == current_carry_id,
                        board.copies_of(item.hero_id) + 1 >= 9,
                        board.copies_of(item.hero_id) + 1 >= 3,
                        item.adjusted,
                    ),
                    default=None,
                )
                tier_six_candidates = [
                    item for item in ranked
                    if _tier_six_targets(HEROES[item.hero_id], board)
                ]
                best_tier_six = max(
                    tier_six_candidates,
                    key=lambda item: (HEROES[item.hero_id].cost, item.adjusted),
                    default=None,
                )
                better_cost5 = next(
                    (
                        item for item in ranked
                        if HEROES[item.hero_id].role == "Carry"
                        and HEROES[item.hero_id].cost >= 5
                        and _should_switch_carry(current_carry_id, item.hero_id, phase.key, board.current_gold)
                    ),
                    None,
                )
                if best_star and (best_star.hero_id == current_carry_id or board.copies_of(best_star.hero_id) + 1 >= 3):
                    chosen = best_star.hero_id
                    chosen_reason = best_star.reason
                    if best_star.hero_id == current_carry_id:
                        carry_reason = "Carry diprioritaskan untuk naik bintang"
                elif current_carry.cost >= 5 and not better_cost5:
                    best_tier_targets = _tier_six_targets(HEROES[best_tier_six.hero_id], board) if best_tier_six else []
                    if best_tier_six and (HEROES[best_tier_six.hero_id].cost >= 4 or best_tier_targets[0][3]):
                        chosen = best_tier_six.hero_id
                        chosen_reason = best_tier_six.reason
                    else:
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
                if chosen == current_carry_id and chosen in board.heroes_on_board and not board.can_star_up(chosen):
                    action = "hold"
                else:
                    locked = current_carry_id if phase.key == "late" else None
                    protect = target_syn if phase.key in {"mid", "late"} else None
                    action = _auto_place(board, chosen, locked_carry_id=locked, protected_synergy=protect)

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
                    chosen_reason += f", mengganti {old}"
                elif action.startswith("star:"):
                    chosen_reason += f", naik ke bintang {board.star_level(chosen)}"
                elif action == "copy":
                    chosen_reason += f", copy terkumpul {board.copies_of(chosen)}/{'9' if board.star_level(chosen) >= 2 else '3'}"
                elif action == "bench":
                    chosen_reason += ", disimpan di bench"
                elif action == "skip":
                    chosen_reason += ", gold tidak cukup"

            if chosen and action == "hold":
                chosen_reason += " - tidak membeli hero baru"

            board_carry_id = _best_carry_on_board(board)
            if _should_refocus_existing_carry(current_carry_id, board_carry_id, phase.key):
                previous = HEROES[current_carry_id].name if current_carry_id else None
                current_carry_id = board_carry_id
                carry_reason = (
                    f"Carry utama ditetapkan ke {HEROES[current_carry_id].name}"
                    if not previous
                    else f"Carry diganti dari {previous} ke {HEROES[current_carry_id].name} karena cost/synergy lebih kuat"
                )

            if not current_carry_id:
                current_carry_id = _best_carry_on_board(board)
                if current_carry_id:
                    carry_reason = f"Carry utama sementara: {HEROES[current_carry_id].name}"
            elif carry_reason == "Belum ada carry utama":
                carry_reason = f"Carry utama dipertahankan: {HEROES[current_carry_id].name}"

            forced_late_star = None
            if phase.key == "late":
                target_syn = _ensure_late_carry_synergy(board, profile_key, current_carry_id, rng)
                if current_carry_id and current_carry_id not in board.heroes_on_board:
                    current_carry_id = _best_carry_on_board(board)
                forced_late_star = _ensure_late_star_three(board, current_carry_id, target_syn)
                if target_syn:
                    carry_reason += f"; target utama {target_syn} 6 aktif"
                if forced_late_star:
                    carry_reason += f"; {HEROES[forced_late_star].name} disimulasikan mencapai bintang 3"

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
                board_after_stars={hid: board.star_level(hid) for hid in board.heroes_on_board},
                shop_heroes=shop.shop_heroes,
                recommendations=ranked[:5],
                chosen_hero_id=chosen,
                chosen_star=board.star_level(chosen) if chosen in HEROES else 1,
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

