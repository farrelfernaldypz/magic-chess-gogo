"""
=============================================================
  Hero Database Loader
  Magic Chess: Go Go - Patch 1.2.54

  Data utama diambil dari data/raw/heroes_id.json.
  File ini menggantikan database lama yang masih hardcoded.
=============================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List
import json
import re


@dataclass
class Hero:
    """Representasi satu hero Magic Chess."""
    id: str
    name: str
    cost: int
    role: str
    synergies: List[str]
    base_atk: float
    base_hp: float
    atk_speed: float
    attack_range: int
    mana_initial: int
    mana_max: int
    carry_score: float
    skill_power: float
    skill_name: str = ""
    description: str = ""
    base_stats: Dict[str, List[float]] = field(default_factory=dict)

    @property
    def power_index(self) -> float:
        """
        Indeks kekuatan hero untuk scoring algoritma.
        Dibuat dari ATK, HP, attack speed, range, cost, carry score,
        dan kekuatan skill agar cocok dengan dataset patch baru.
        """
        mana_efficiency = 1.0
        if self.mana_max:
            mana_efficiency += min(self.mana_initial / self.mana_max, 1.0) * 0.20

        return (
            self.base_atk * max(self.atk_speed, 0.1) * 2.8
            + self.base_hp * 0.055
            + self.attack_range * 18
            + self.cost * 65
            + self.carry_score * 75
            + self.skill_power * 45
        ) * mana_efficiency


def _data_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "raw" / filename


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "hero"


def _as_number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        match = re.search(r"-?\d+(?:\.\d+)?", value.replace(",", ""))
        if match:
            return float(match.group(0))
    return default


def _first(stats: Dict[str, List[Any]], key: str, default: float = 0.0) -> float:
    values = stats.get(key) or []
    return _as_number(values[0], default) if values else default


def _max_skill_number(skill: Dict[str, Any]) -> float:
    """Ambil angka terbesar dari atribut skill sebagai pendekatan skill power."""
    values: List[float] = []
    for attr in skill.get("skill_attributes", []) or []:
        for raw in attr.get("values", []) or []:
            values.append(_as_number(raw))

    # Tambahan: baca juga dari deskripsi karena beberapa skill menyimpan angka di teks.
    desc = skill.get("description", "") or ""
    for match in re.findall(r"\d+(?:\.\d+)?%?", desc):
        values.append(_as_number(match))

    return max(values) if values else 0.0


def _infer_role(name: str, synergies: List[str], hp: float, atk: float, atk_range: int) -> str:
    syns = set(synergies)

    if "Defender" in syns:
        return "Tank"
    if "Bruiser" in syns and hp >= 2600:
        return "Tank"
    if "Dauntless" in syns and hp >= 3000:
        return "Tank"
    if syns & {"Stargazer", "Mystic Meow", "Heartbond"} and atk < 145 and atk_range <= 3:
        return "Support"
    if syns & {"Mage", "Marksman", "Swiftblade", "Weapon Master", "Phasewarper", "Scavenger"}:
        return "Carry"
    if syns & {"Bruiser", "Dauntless"}:
        return "Fighter"
    return "Flex"


def _load_raw_heroes() -> List[Dict[str, Any]]:
    path = _data_path("heroes_id.json")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _build_heroes() -> Dict[str, Hero]:
    raw_heroes = _load_raw_heroes()

    # Statistik global untuk normalisasi.
    hp_values = [_first(h.get("base_stats", {}), "hp", 1) for h in raw_heroes]
    atk_values = [
        max(
            _first(h.get("base_stats", {}), "physical_atk", 1),
            _first(h.get("base_stats", {}), "magic_atk", 1),
        )
        for h in raw_heroes
    ]
    skill_values = [_max_skill_number(h.get("skill", {})) for h in raw_heroes]

    max_hp = max(hp_values) if hp_values else 1
    max_atk = max(atk_values) if atk_values else 1
    max_skill = max(skill_values) if skill_values else 1

    heroes: Dict[str, Hero] = {}
    used_ids: Dict[str, int] = {}

    for item in raw_heroes:
        name = item.get("hero_name", "Unknown Hero")
        base_id = _slugify(name)
        used_ids[base_id] = used_ids.get(base_id, 0) + 1
        hero_id = base_id if used_ids[base_id] == 1 else f"{base_id}_{used_ids[base_id]}"

        stats = item.get("base_stats", {}) or {}
        hp = _first(stats, "hp", 0)
        physical = _first(stats, "physical_atk", 0)
        magic = _first(stats, "magic_atk", 0)
        atk = max(physical, magic)
        atk_speed = _first(stats, "atk_speed", 0.65)
        atk_range = int(_first(stats, "attack_range", 1))
        mana_initial = int(_first(stats, "mana_initial", 0))
        mana_max = int(_first(stats, "mana_max", 0))
        cost = int(item.get("cost", 1) or 1)
        synergies = list(item.get("synergies", []) or [])
        skill = item.get("skill", {}) or {}
        raw_skill_value = _max_skill_number(skill)

        role = _infer_role(name, synergies, hp, atk, atk_range)

        # Carry score 0-10: menggabungkan cost, damage, attack speed, range, dan skill.
        atk_component = (atk / max_atk) * 2.6
        hp_component = (hp / max_hp) * 1.1
        cost_component = (cost / 5) * 2.0
        speed_component = min(atk_speed / 1.0, 1.2) * 0.9
        range_component = min(atk_range / 4, 1.0) * 0.9
        skill_component = (raw_skill_value / max_skill) * 2.0 if max_skill else 0.0
        role_bonus = {"Carry": 0.9, "Fighter": 0.55, "Tank": 0.25, "Support": 0.15}.get(role, 0.35)
        carry_score = min(10.0, round(1.0 + atk_component + hp_component + cost_component + speed_component + range_component + skill_component + role_bonus, 2))

        # Skill power 0-10: fokus ke atribut skill + sedikit pengaruh cost.
        skill_power = min(10.0, round(2.0 + (raw_skill_value / max_skill) * 5.2 + cost * 0.55, 2)) if max_skill else 5.0

        heroes[hero_id] = Hero(
            id=hero_id,
            name=name,
            cost=cost,
            role=role,
            synergies=synergies,
            base_atk=atk,
            base_hp=hp,
            atk_speed=atk_speed,
            attack_range=atk_range,
            mana_initial=mana_initial,
            mana_max=mana_max,
            carry_score=carry_score,
            skill_power=skill_power,
            skill_name=skill.get("name", ""),
            description=skill.get("description", ""),
            base_stats=stats,
        )

    return heroes


HEROES: Dict[str, Hero] = _build_heroes()


def get_hero_id_by_name(name: str) -> str | None:
    """Cari id hero berdasarkan nama tampilan."""
    normalized = name.strip().lower()
    for hero_id, hero in HEROES.items():
        if hero.name.lower() == normalized:
            return hero_id
    return None


def get_heroes_by_synergy(synergy_name: str) -> List[Hero]:
    """Ambil daftar hero yang memiliki synergy tertentu."""
    return [hero for hero in HEROES.values() if synergy_name in hero.synergies]
