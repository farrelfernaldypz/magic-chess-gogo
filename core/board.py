"""
=============================================================
  Board State – Representasi Papan Permainan Magic Chess
=============================================================
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from data.heroes import Hero, HEROES
from data.synergies import (
    count_synergies, evaluate_synergy_score,
    get_active_synergies, SYNERGIES
)


@dataclass
class BoardState:
    """
    Representasi kondisi papan pemain saat ini.
    Menyimpan hero yang dipilih, sinergi aktif, dan kondisi game.
    """
    round_number: int = 1
    current_gold: int = 10
    max_slots: int = 3          # Bertambah seiring round (3→9)
    heroes_on_board: List[str] = field(default_factory=list)   # ID hero aktif
    heroes_in_bench: List[str] = field(default_factory=list)   # ID hero bench
    hero_copies: Dict[str, int] = field(default_factory=dict)   # Total copy untuk star-up

    def __post_init__(self):
        # Sesuaikan slot maksimum berdasarkan round
        self.max_slots = self._calculate_max_slots()
        for hero_id in self.all_heroes:
            self.hero_copies.setdefault(hero_id, self.all_heroes.count(hero_id))

    def _calculate_max_slots(self) -> int:
        """Jumlah slot bertambah sesuai level/round."""
        if self.round_number <= 3:
            return 3
        elif self.round_number <= 6:
            return 5
        elif self.round_number <= 10:
            return 6
        elif self.round_number <= 15:
            return 7
        elif self.round_number <= 20:
            return 8
        elif self.round_number <= 25:
            return 9
        else:
            return 10

    @property
    def all_heroes(self) -> List[str]:
        return self.heroes_on_board + self.heroes_in_bench

    def copies_of(self, hero_id: str) -> int:
        if hero_id in self.hero_copies:
            return self.hero_copies[hero_id]
        return self.all_heroes.count(hero_id)

    def star_level(self, hero_id: str) -> int:
        copies = self.copies_of(hero_id)
        if copies >= 9:
            return 3
        if copies >= 3:
            return 2
        return 1

    def can_star_up(self, hero_id: str) -> bool:
        return hero_id in HEROES and self.copies_of(hero_id) < 9

    def star_power_multiplier(self, hero_id: str) -> float:
        return {1: 1.0, 2: 1.55, 3: 2.35}[self.star_level(hero_id)]

    @property
    def board_full(self) -> bool:
        return len(self.heroes_on_board) >= self.max_slots

    @property
    def synergy_counts(self) -> Dict[str, int]:
        return count_synergies(self.heroes_on_board, HEROES)

    @property
    def synergy_score(self) -> float:
        return evaluate_synergy_score(self.synergy_counts)

    @property
    def active_synergies(self):
        return get_active_synergies(self.synergy_counts)

    @property
    def game_phase(self) -> str:
        """Early / Mid / Late game berdasarkan round."""
        if self.round_number <= 8:
            return "early"
        elif self.round_number <= 18:
            return "mid"
        else:
            return "late"

    @property
    def total_power(self) -> float:
        """Total kekuatan board = power hero + bonus synergy."""
        hero_power = sum(
            HEROES[hid].power_index * self.star_power_multiplier(hid)
            for hid in self.heroes_on_board if hid in HEROES
        )
        return hero_power + self.synergy_score * 10

    def can_afford(self, hero_id: str) -> bool:
        hero = HEROES.get(hero_id)
        return hero is not None and self.current_gold >= hero.cost

    def add_hero(self, hero_id: str, to_board: bool = True) -> bool:
        """Tambah hero ke board atau bench."""
        if hero_id not in HEROES:
            return False
        hero = HEROES[hero_id]
        if self.current_gold < hero.cost:
            return False

        self.current_gold -= hero.cost
        self.hero_copies[hero_id] = self.copies_of(hero_id) + 1

        if hero_id in self.heroes_on_board or hero_id in self.heroes_in_bench:
            return True

        if to_board and not self.board_full:
            self.heroes_on_board.append(hero_id)
        else:
            self.heroes_in_bench.append(hero_id)
        return True

    def remove_hero(self, hero_id: str) -> bool:
        if hero_id in self.heroes_on_board:
            self.heroes_on_board.remove(hero_id)
            self.hero_copies.pop(hero_id, None)
            self.current_gold += HEROES[hero_id].cost // 2  # Jual setengah harga
            return True
        if hero_id in self.heroes_in_bench:
            self.heroes_in_bench.remove(hero_id)
            self.hero_copies.pop(hero_id, None)
            self.current_gold += HEROES[hero_id].cost // 2
            return True
        return False

    def copy(self) -> "BoardState":
        """Buat salinan board state untuk simulasi."""
        return BoardState(
            round_number=self.round_number,
            current_gold=self.current_gold,
            max_slots=self.max_slots,
            heroes_on_board=self.heroes_on_board.copy(),
            heroes_in_bench=self.heroes_in_bench.copy(),
            hero_copies=self.hero_copies.copy(),
        )

    def summary(self) -> str:
        """Ringkasan board state untuk display."""
        lines = [
            f"  Round       : {self.round_number} ({self.game_phase.upper()})",
            f"  Gold        : {self.current_gold}",
            f"  Slots Used  : {len(self.heroes_on_board)}/{self.max_slots}",
            f"  Board Power : {self.total_power:.1f}",
            f"  Heroes      : {', '.join(HEROES[h].name for h in self.heroes_on_board if h in HEROES) or '–'}",
        ]
        if self.active_synergies:
            syn_str = ", ".join(
                f"{s} ({c})" for s, t, c in self.active_synergies
            )
            lines.append(f"  Synergies   : {syn_str}")
        return "\n".join(lines)
