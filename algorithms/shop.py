"""
=============================================================
  RANDOM SHOP / REFRESH SIMULATOR

  Modul ini meniru alur Magic Chess yang lebih natural:
  hero yang dinilai algoritma bukan semua hero di dataset,
  tetapi hanya hero yang muncul dari hasil refresh shop.

  Flow:
    1. Board saat ini dibuat/diisi.
    2. Shop me-roll 5 hero secara acak berdasarkan fase round.
    3. Hybrid algorithm memberi skor hanya pada hero di shop.
    4. Rekomendasi terbaik bisa dibeli lalu board berubah.
=============================================================
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from data.heroes import HEROES, get_hero_id_by_name
from data.synergies import SYNERGIES
from core.board import BoardState


# Pendekatan sederhana untuk peluang shop berdasarkan round.
# Angka ini bukan data resmi; dipakai agar simulasi terasa random dan masuk akal.
ROUND_COST_ODDS: List[tuple[int, Dict[int, int]]] = [
    (4,  {1: 75, 2: 20, 3: 5,  4: 0,  5: 0}),
    (8,  {1: 55, 2: 30, 3: 12, 4: 3,  5: 0}),
    (12, {1: 35, 2: 35, 3: 22, 4: 7,  5: 1}),
    (18, {1: 18, 2: 28, 3: 32, 4: 17, 5: 5}),
    (24, {1: 8,  2: 18, 3: 35, 4: 28, 5: 11}),
    (99, {1: 3,  2: 10, 3: 30, 4: 35, 5: 22}),
]


@dataclass
class ShopRoll:
    """Hasil satu kali refresh shop."""
    round_number: int
    gold: int
    shop_heroes: List[str]
    seed: Optional[int] = None


def get_cost_odds(round_number: int) -> Dict[int, int]:
    """Ambil distribusi peluang cost sesuai round."""
    for max_round, odds in ROUND_COST_ODDS:
        if round_number <= max_round:
            return odds
    return ROUND_COST_ODDS[-1][1]


def _weighted_cost(rng: random.Random, odds: Dict[int, int]) -> int:
    costs = list(odds.keys())
    weights = list(odds.values())
    return rng.choices(costs, weights=weights, k=1)[0]


def roll_shop(
    board: BoardState,
    shop_size: int = 5,
    seed: Optional[int] = None,
    rng: Optional[random.Random] = None,
    exclude_owned: bool = True,
) -> ShopRoll:
    """
    Roll shop acak berdasarkan round.

    Hero yang sudah dimiliki bisa dikeluarkan dari pool agar rekomendasi
    lebih mudah dibaca untuk tugas/visualisasi.
    """
    local_rng = rng or random.Random(seed)
    odds = get_cost_odds(board.round_number)
    owned = set(board.all_heroes) if exclude_owned else set()
    chosen: List[str] = []

    # Loop dibuat agak panjang supaya tetap dapat 5 hero meski cost tertentu kosong.
    attempts = 0
    while len(chosen) < shop_size and attempts < shop_size * 20:
        attempts += 1
        target_cost = _weighted_cost(local_rng, odds)
        pool = [
            hid for hid, hero in HEROES.items()
            if hero.cost == target_cost and hid not in chosen and hid not in owned
        ]
        if not pool:
            pool = [hid for hid in HEROES if hid not in chosen and hid not in owned]
        if not pool:
            break
        chosen.append(local_rng.choice(pool))

    return ShopRoll(
        round_number=board.round_number,
        gold=board.current_gold,
        shop_heroes=chosen,
        seed=seed,
    )


def random_board_state(seed: Optional[int] = None, rng: Optional[random.Random] = None) -> BoardState:
    """Buat board awal acak yang masih masuk akal berdasarkan salah satu synergy."""
    local_rng = rng or random.Random(seed)
    round_number = local_rng.choice([4, 6, 8, 10, 13, 16, 19, 22, 26])
    gold = local_rng.randint(6, 24)
    board = BoardState(round_number=round_number, current_gold=gold)

    # Pilih synergy yang punya minimal 3 hero valid di dataset.
    valid_synergies = []
    for synergy in SYNERGIES.values():
        hero_ids = [get_hero_id_by_name(name) for name in synergy.heroes]
        hero_ids = [hid for hid in hero_ids if hid in HEROES]
        if len(hero_ids) >= 3:
            valid_synergies.append((synergy.name, hero_ids))

    if not valid_synergies:
        return board

    _, focused_ids = local_rng.choice(valid_synergies)
    target_size = min(board.max_slots, local_rng.randint(2, max(2, board.max_slots - 1)))

    # 60-75% hero board diambil dari synergy fokus, sisanya filler random.
    focus_count = min(len(focused_ids), max(1, int(target_size * local_rng.uniform(0.6, 0.75))))
    selected = local_rng.sample(focused_ids, k=focus_count)

    fillers = [hid for hid in HEROES if hid not in selected]
    local_rng.shuffle(fillers)
    selected.extend(fillers[: max(0, target_size - len(selected))])

    board.heroes_on_board = selected[:target_size]
    return board


def shop_as_rows(shop_heroes: List[str]) -> List[Dict]:
    """Ubah daftar hero shop menjadi format siap visualisasi."""
    rows = []
    for hid in shop_heroes:
        hero = HEROES[hid]
        rows.append(
            {
                "id": hid,
                "name": hero.name,
                "cost": hero.cost,
                "role": hero.role,
                "synergies": hero.synergies,
                "power_index": round(hero.power_index, 2),
                "carry_score": hero.carry_score,
            }
        )
    return rows
