"""
=============================================================
  Synergy Database Loader
  Magic Chess: Go Go - Patch 1.2.54

  Data utama diambil dari data/raw/synergies_id.json.
=============================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import re


@dataclass
class SynergyTier:
    """Satu tier bonus untuk synergy tertentu."""
    required: int
    description: str
    power_bonus: float


@dataclass
class Synergy:
    """Definisi sebuah synergy."""
    id: str
    name: str
    category: str
    tiers: List[SynergyTier]
    heroes: List[str]
    description: str = ""
    color: str = "#ffffff"

    def get_active_tier(self, hero_count: int) -> SynergyTier | None:
        active = None
        for tier in sorted(self.tiers, key=lambda t: t.required):
            if hero_count >= tier.required:
                active = tier
        return active

    def get_next_tier(self, hero_count: int) -> SynergyTier | None:
        for tier in sorted(self.tiers, key=lambda t: t.required):
            if hero_count < tier.required:
                return tier
        return None

    def completion_ratio(self, hero_count: int) -> float:
        next_tier = self.get_next_tier(hero_count)
        if next_tier is None:
            return 1.0

        prev_required = 0
        for tier in sorted(self.tiers, key=lambda t: t.required):
            if tier.required <= hero_count:
                prev_required = tier.required
            else:
                break

        span = next_tier.required - prev_required
        progress = hero_count - prev_required
        return progress / span if span > 0 else 1.0


def _data_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "raw" / filename


def _load_raw_synergies() -> List[Dict[str, Any]]:
    path = _data_path("synergies_id.json")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _effect_weight(effect: str, required: int) -> float:
    """Ubah deskripsi efek menjadi bobot numerik untuk scoring algoritma."""
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", effect.replace(",", ""))]
    number_score = min(sum(numbers) / 80.0, 90.0) if numbers else 0.0

    keyword_bonus = 0.0
    keywords = {
        "True DMG": 18,
        "DMG": 14,
        "Hybrid ATK": 12,
        "ATK Speed": 10,
        "Shield": 9,
        "HP": 8,
        "DEF": 8,
        "Mana": 7,
        "Gold": 7,
        "Summon": 10,
        "memanggil": 10,
        "mengurangi": 6,
        "tambahan": 4,
    }
    lowered = effect.lower()
    for keyword, bonus in keywords.items():
        if keyword.lower() in lowered:
            keyword_bonus += bonus

    return round(required * 18 + number_score + keyword_bonus, 2)


def _color_for(category: str, index: int) -> str:
    faction_colors = [
        "#7c3aed", "#2563eb", "#059669", "#dc2626", "#d97706",
        "#0891b2", "#be185d", "#4f46e5", "#16a34a", "#9333ea",
        "#ea580c", "#0f766e",
    ]
    role_colors = [
        "#f59e0b", "#ef4444", "#8b5cf6", "#22c55e", "#06b6d4",
        "#64748b", "#14b8a6", "#f97316", "#a855f7",
    ]
    palette = role_colors if category == "role" else faction_colors
    return palette[index % len(palette)]


def _build_synergies() -> Dict[str, Synergy]:
    raw = _load_raw_synergies()
    synergies: Dict[str, Synergy] = {}

    for idx, item in enumerate(raw):
        name = item.get("synergy_name", "Unknown Synergy")
        category = "role" if (item.get("type", "").lower() == "role") else "faction"
        tiers: List[SynergyTier] = []

        for level in item.get("levels", []) or []:
            required = int(level.get("count", 1) or 1)
            effect = level.get("effect", "") or ""
            tiers.append(
                SynergyTier(
                    required=required,
                    description=effect,
                    power_bonus=_effect_weight(effect, required),
                )
            )

        synergies[name] = Synergy(
            id=name,
            name=name,
            category=category,
            tiers=sorted(tiers, key=lambda t: t.required),
            heroes=list(item.get("heroes", []) or []),
            description=item.get("description", ""),
            color=_color_for(category, idx),
        )

    return synergies


SYNERGIES: Dict[str, Synergy] = _build_synergies()


def count_synergies(hero_ids: List[str], hero_db: dict) -> Dict[str, int]:
    """Hitung jumlah hero per synergy dari daftar hero aktif."""
    counts: Dict[str, int] = {}
    for hero_id in hero_ids:
        if hero_id in hero_db:
            for synergy_name in hero_db[hero_id].synergies:
                counts[synergy_name] = counts.get(synergy_name, 0) + 1
    return counts


def evaluate_synergy_score(synergy_counts: Dict[str, int]) -> float:
    """Hitung total skor bonus synergy yang aktif."""
    total = 0.0
    for synergy_name, count in synergy_counts.items():
        synergy = SYNERGIES.get(synergy_name)
        if not synergy:
            continue
        tier = synergy.get_active_tier(count)
        if tier:
            total += tier.power_bonus
    return total


def get_active_synergies(synergy_counts: Dict[str, int]) -> List[Tuple[str, SynergyTier, int]]:
    """Kembalikan list synergy aktif beserta tier-nya."""
    active = []
    for synergy_name, count in synergy_counts.items():
        synergy = SYNERGIES.get(synergy_name)
        if not synergy:
            continue
        tier = synergy.get_active_tier(count)
        if tier:
            active.append((synergy_name, tier, count))
    return sorted(active, key=lambda x: x[1].power_bonus, reverse=True)
