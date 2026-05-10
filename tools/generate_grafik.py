from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime
from html import escape
from pathlib import Path
from statistics import mean
from typing import Iterable


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from algorithms.game_simulator import PROFILES, simulate_all_profiles  # noqa: E402
from data.heroes import HEROES  # noqa: E402
from data.synergies import SYNERGIES  # noqa: E402


DEFAULT_OUTPUT_DIR = BASE_DIR / "output" / "grafik"
DEFAULT_HTML_FILE = BASE_DIR / "output" / "grafik.html"
DEFAULT_SEED = 20260510

PALETTE = [
    "#278dff",
    "#35d598",
    "#ffc84f",
    "#ff70b8",
    "#8b5cf6",
    "#ff8f3d",
    "#06b6d4",
    "#14b8a6",
    "#ef4444",
    "#64748b",
]

PROFILE_LABELS = {key: profile.name for key, profile in PROFILES.items()}
PROFILE_COLORS = {
    key: profile.accent for key, profile in PROFILES.items()
}


def rupiah_number(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}".replace(",", ".")
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def safe_id(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in {" ", "-", "_"}:
            allowed.append("-")
    return "-".join("".join(allowed).split("-")).strip("-") or "chart"


def truncate_label(value: str, max_chars: int = 30) -> str:
    return value if len(value) <= max_chars else f"{value[: max_chars - 1]}..."


def svg_shell(title: str, subtitle: str, width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(subtitle or title)}</desc>
  <defs>
    <linearGradient id="paper" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#ffffff"/>
      <stop offset="100%" stop-color="#eef8ff"/>
    </linearGradient>
    <filter id="softShadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#1c468b" flood-opacity="0.13"/>
    </filter>
  </defs>
  <style>
    .bg {{ fill: url(#paper); }}
    .title {{ fill: #18396f; font: 800 32px 'Segoe UI', Arial, sans-serif; }}
    .subtitle {{ fill: #5e708e; font: 600 15px 'Segoe UI', Arial, sans-serif; }}
    .axis {{ stroke: rgba(43, 91, 167, 0.22); stroke-width: 1; }}
    .grid {{ stroke: rgba(43, 91, 167, 0.10); stroke-width: 1; }}
    .label {{ fill: #31527f; font: 700 13px 'Segoe UI', Arial, sans-serif; }}
    .small {{ fill: #5e708e; font: 600 12px 'Segoe UI', Arial, sans-serif; }}
    .value {{ fill: #18396f; font: 800 13px 'Segoe UI', Arial, sans-serif; }}
    .legend {{ fill: #31527f; font: 700 13px 'Segoe UI', Arial, sans-serif; }}
  </style>
  <rect class="bg" width="{width}" height="{height}" rx="22"/>
  <rect x="18" y="18" width="{width - 36}" height="{height - 36}" rx="18" fill="rgba(255,255,255,0.58)" filter="url(#softShadow)"/>
  <text class="title" x="44" y="62">{escape(title)}</text>
  <text class="subtitle" x="44" y="88">{escape(subtitle)}</text>
{body}
</svg>
"""


def horizontal_bar_chart(
    title: str,
    rows: list[tuple[str, float]],
    subtitle: str = "",
    *,
    width: int = 1120,
    max_items: int | None = None,
    value_formatter=rupiah_number,
) -> str:
    visible_rows = rows[:max_items] if max_items else rows
    bar_height = 24
    gap = 13
    top = 122
    left = 260
    right = 96
    bottom = 52
    height = max(360, top + bottom + len(visible_rows) * (bar_height + gap))
    chart_width = width - left - right
    max_value = max((value for _, value in visible_rows), default=1)
    max_value = max(max_value, 1)

    pieces = [
        f'  <line class="axis" x1="{left}" y1="{top - 14}" x2="{left}" y2="{height - bottom + 10}"/>',
        f'  <line class="axis" x1="{left}" y1="{height - bottom + 10}" x2="{width - right}" y2="{height - bottom + 10}"/>',
    ]

    for index in range(1, 5):
        x = left + chart_width * index / 4
        pieces.append(f'  <line class="grid" x1="{x:.1f}" y1="{top - 14}" x2="{x:.1f}" y2="{height - bottom + 10}"/>')

    for index, (label, value) in enumerate(visible_rows):
        y = top + index * (bar_height + gap)
        bar_width = max(4, chart_width * value / max_value)
        color = PALETTE[index % len(PALETTE)]
        pieces.extend(
            [
                f'  <text class="label" x="{left - 14}" y="{y + 17}" text-anchor="end">{escape(truncate_label(label, 34))}</text>',
                f'  <rect x="{left}" y="{y}" width="{bar_width:.1f}" height="{bar_height}" rx="8" fill="{color}"/>',
                f'  <text class="value" x="{left + bar_width + 10:.1f}" y="{y + 17}">{escape(value_formatter(value))}</text>',
            ]
        )

    return svg_shell(title, subtitle, width, height, "\n".join(pieces))


def vertical_bar_chart(
    title: str,
    rows: list[tuple[str, float]],
    subtitle: str = "",
    *,
    width: int = 1120,
    height: int = 520,
    value_formatter=rupiah_number,
) -> str:
    top = 124
    left = 86
    right = 54
    bottom = 88
    chart_width = width - left - right
    chart_height = height - top - bottom
    max_value = max((value for _, value in rows), default=1)
    max_value = max(max_value, 1)
    gap = 16
    bar_width = (chart_width - gap * max(len(rows) - 1, 0)) / max(len(rows), 1)

    pieces = [
        f'  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"/>',
        f'  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"/>',
    ]

    for index in range(1, 5):
        y = top + chart_height - chart_height * index / 4
        pieces.append(f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>')

    for index, (label, value) in enumerate(rows):
        x = left + index * (bar_width + gap)
        bar_height = chart_height * value / max_value
        y = top + chart_height - bar_height
        color = PALETTE[index % len(PALETTE)]
        pieces.extend(
            [
                f'  <rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{bar_height:.1f}" rx="8" fill="{color}"/>',
                f'  <text class="value" x="{x + bar_width / 2:.1f}" y="{y - 10:.1f}" text-anchor="middle">{escape(value_formatter(value))}</text>',
                f'  <text class="label" x="{x + bar_width / 2:.1f}" y="{height - bottom + 34}" text-anchor="middle">{escape(label)}</text>',
            ]
        )

    return svg_shell(title, subtitle, width, height, "\n".join(pieces))


def line_chart(
    title: str,
    categories: list[str],
    series: dict[str, list[float]],
    subtitle: str = "",
    *,
    width: int = 1120,
    height: int = 560,
    value_formatter=rupiah_number,
) -> str:
    top = 126
    left = 86
    right = 60
    bottom = 116
    chart_width = width - left - right
    chart_height = height - top - bottom
    values = [value for values in series.values() for value in values]
    min_value = min(values, default=0)
    max_value = max(values, default=1)
    if min_value == max_value:
        min_value = 0
    padding = (max_value - min_value) * 0.08
    min_value = max(0, min_value - padding)
    max_value = max_value + padding

    def x_for(index: int) -> float:
        if len(categories) == 1:
            return left + chart_width / 2
        return left + chart_width * index / (len(categories) - 1)

    def y_for(value: float) -> float:
        ratio = (value - min_value) / (max_value - min_value)
        return top + chart_height - chart_height * ratio

    pieces = [
        f'  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"/>',
        f'  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"/>',
    ]

    for index in range(5):
        y = top + chart_height * index / 4
        value = max_value - (max_value - min_value) * index / 4
        pieces.extend(
            [
                f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>',
                f'  <text class="small" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{escape(value_formatter(value))}</text>',
            ]
        )

    for index, label in enumerate(categories):
        x = x_for(index)
        pieces.append(f'  <text class="label" x="{x:.1f}" y="{height - bottom + 34}" text-anchor="middle">{escape(label)}</text>')

    legend_y = height - 44
    legend_x = left
    for index, (name, values_for_series) in enumerate(series.items()):
        color = PROFILE_COLORS.get(name, PALETTE[index % len(PALETTE)])
        points = " ".join(f"{x_for(i):.1f},{y_for(value):.1f}" for i, value in enumerate(values_for_series))
        pieces.append(f'  <polyline points="{points}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>')
        for i, value in enumerate(values_for_series):
            x = x_for(i)
            y = y_for(value)
            pieces.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="#ffffff" stroke-width="2"/>')
        pieces.extend(
            [
                f'  <rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" rx="4" fill="{color}"/>',
                f'  <text class="legend" x="{legend_x + 22}" y="{legend_y}">{escape(PROFILE_LABELS.get(name, name))}</text>',
            ]
        )
        legend_x += 190

    return svg_shell(title, subtitle, width, height, "\n".join(pieces))


def stacked_bar_chart(
    title: str,
    categories: list[str],
    segments: dict[str, list[float]],
    subtitle: str = "",
    *,
    width: int = 1120,
    height: int = 540,
) -> str:
    top = 128
    left = 96
    right = 58
    bottom = 112
    chart_width = width - left - right
    chart_height = height - top - bottom
    gap = 20
    bar_width = (chart_width - gap * max(len(categories) - 1, 0)) / max(len(categories), 1)
    segment_colors = {
        "greedy": "#278dff",
        "heuristic": "#35d598",
        "carry": "#ffc84f",
    }

    pieces = [
        f'  <line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}"/>',
        f'  <line class="axis" x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}"/>',
    ]

    for index in range(1, 5):
        y = top + chart_height - chart_height * index / 4
        pieces.extend(
            [
                f'  <line class="grid" x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}"/>',
                f'  <text class="small" x="{left - 12}" y="{y + 4:.1f}" text-anchor="end">{index * 25}%</text>',
            ]
        )

    for category_index, category in enumerate(categories):
        x = left + category_index * (bar_width + gap)
        y_cursor = top + chart_height
        total = sum(segments[name][category_index] for name in segments) or 1
        for name, values in segments.items():
            value = values[category_index] / total
            segment_height = chart_height * value
            y_cursor -= segment_height
            pieces.append(
                f'  <rect x="{x:.1f}" y="{y_cursor:.1f}" width="{bar_width:.1f}" height="{segment_height:.1f}" rx="6" fill="{segment_colors.get(name, "#64748b")}"/>'
            )
            if segment_height > 38:
                pieces.append(
                    f'  <text class="value" x="{x + bar_width / 2:.1f}" y="{y_cursor + segment_height / 2 + 4:.1f}" text-anchor="middle">{escape(pct(value))}</text>'
                )
        pieces.append(f'  <text class="label" x="{x + bar_width / 2:.1f}" y="{height - bottom + 34}" text-anchor="middle">{escape(category)}</text>')

    legend_y = height - 44
    legend_x = left
    for label, key in [("Greedy", "greedy"), ("Heuristic", "heuristic"), ("Carry", "carry")]:
        pieces.extend(
            [
                f'  <rect x="{legend_x}" y="{legend_y - 12}" width="14" height="14" rx="4" fill="{segment_colors[key]}"/>',
                f'  <text class="legend" x="{legend_x + 22}" y="{legend_y}">{label}</text>',
            ]
        )
        legend_x += 150

    return svg_shell(title, subtitle, width, height, "\n".join(pieces))


def average_map(values: dict[str, list[float]]) -> dict[str, float]:
    return {key: mean(items) if items else 0.0 for key, items in values.items()}


def collect_simulation(samples: int, seed: int) -> dict:
    rng = random.Random(seed)
    seeds = [rng.randint(10_000, 999_999) for _ in range(samples)]

    final_power: dict[str, list[float]] = defaultdict(list)
    final_hp: dict[str, list[float]] = defaultdict(list)
    active_synergy_count: dict[str, list[float]] = defaultdict(list)
    gold_by_checkpoint: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    weights_by_profile: dict[str, dict[str, dict[str, list[float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    checkpoint_order: list[str] = []

    for game_seed in seeds:
        runs = simulate_all_profiles(game_seed)
        for profile_key, run in runs.items():
            final_power[profile_key].append(run.final_power)
            final_hp[profile_key].append(run.final_commander_hp)
            active_synergy_count[profile_key].append(len(run.final_synergies))

            for snapshot in run.snapshots:
                label = snapshot.checkpoint_label
                if label not in checkpoint_order:
                    checkpoint_order.append(label)
                gold_by_checkpoint[profile_key][label].append(snapshot.gold_after)
                for name, value in snapshot.adaptive_weights.items():
                    weights_by_profile[profile_key][label][name].append(value)

    return {
        "seed": seed,
        "samples": samples,
        "seeds": seeds,
        "checkpoint_order": checkpoint_order,
        "final_power": final_power,
        "final_hp": final_hp,
        "active_synergy_count": active_synergy_count,
        "gold_by_checkpoint": gold_by_checkpoint,
        "weights_by_profile": weights_by_profile,
    }


def dataset_charts() -> list[dict]:
    cost_counter = Counter(hero.cost for hero in HEROES.values())
    role_counter = Counter(hero.role for hero in HEROES.values())
    synergy_counts = sorted(
        ((synergy.name, len(synergy.heroes)) for synergy in SYNERGIES.values()),
        key=lambda item: (-item[1], item[0]),
    )
    top_power = sorted(
        ((hero.name, hero.power_index) for hero in HEROES.values()),
        key=lambda item: item[1],
        reverse=True,
    )[:12]

    return [
        {
            "file": "hero-cost-distribution.svg",
            "title": "Distribusi Cost Hero",
            "subtitle": "Jumlah hero pada setiap cost.",
            "svg": vertical_bar_chart(
                "Distribusi Cost Hero",
                [(str(cost), cost_counter[cost]) for cost in sorted(cost_counter)],
                "Jumlah hero pada setiap cost.",
            ),
            "data": dict(sorted(cost_counter.items())),
        },
        {
            "file": "hero-role-distribution.svg",
            "title": "Distribusi Role Hero",
            "subtitle": "Role hasil inferensi dari dataset hero.",
            "svg": horizontal_bar_chart(
                "Distribusi Role Hero",
                sorted(role_counter.items(), key=lambda item: (-item[1], item[0])),
                "Role hasil inferensi dari dataset hero.",
            ),
            "data": dict(sorted(role_counter.items())),
        },
        {
            "file": "top-heroes-power-index.svg",
            "title": "Top Hero Power Index",
            "subtitle": "Ranking berdasarkan formula power_index di data/heroes.py.",
            "svg": horizontal_bar_chart(
                "Top Hero Power Index",
                top_power,
                "Ranking berdasarkan formula power_index di data/heroes.py.",
                value_formatter=lambda value: f"{value:,.1f}".replace(",", "."),
            ),
            "data": top_power,
        },
        {
            "file": "synergy-hero-count.svg",
            "title": "Jumlah Hero per Sinergi",
            "subtitle": "Sinergi dengan pool hero terbanyak lebih mudah dicapai.",
            "svg": horizontal_bar_chart(
                "Jumlah Hero per Sinergi",
                synergy_counts,
                "Sinergi dengan pool hero terbanyak lebih mudah dicapai.",
            ),
            "data": synergy_counts,
        },
    ]


def simulation_charts(sim: dict) -> list[dict]:
    checkpoint_order = sim["checkpoint_order"]
    final_power_avg = average_map(sim["final_power"])
    final_hp_avg = average_map(sim["final_hp"])
    active_synergy_avg = average_map(sim["active_synergy_count"])
    samples = sim["samples"]

    power_rows = sorted(
        ((PROFILE_LABELS[key], value) for key, value in final_power_avg.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    hp_rows = sorted(
        ((PROFILE_LABELS[key], value) for key, value in final_hp_avg.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    synergy_rows = sorted(
        ((PROFILE_LABELS[key], value) for key, value in active_synergy_avg.items()),
        key=lambda item: item[1],
        reverse=True,
    )

    gold_series = {
        profile_key: [
            mean(sim["gold_by_checkpoint"][profile_key][checkpoint])
            if sim["gold_by_checkpoint"][profile_key][checkpoint]
            else 0.0
            for checkpoint in checkpoint_order
        ]
        for profile_key in PROFILES
    }

    charts = [
        {
            "file": "profile-final-power.svg",
            "title": "Rata-rata Final Power",
            "subtitle": f"Perbandingan strategi dari {samples} simulasi.",
            "svg": horizontal_bar_chart(
                "Rata-rata Final Power",
                power_rows,
                f"Perbandingan strategi dari {samples} simulasi.",
            ),
            "data": final_power_avg,
        },
        {
            "file": "profile-commander-hp.svg",
            "title": "Rata-rata HP Commander",
            "subtitle": f"Sisa HP akhir dari {samples} simulasi.",
            "svg": horizontal_bar_chart(
                "Rata-rata HP Commander",
                hp_rows,
                f"Sisa HP akhir dari {samples} simulasi.",
                value_formatter=lambda value: f"{value:.1f}",
            ),
            "data": final_hp_avg,
        },
        {
            "file": "profile-active-synergies.svg",
            "title": "Rata-rata Sinergi Aktif",
            "subtitle": f"Jumlah sinergi aktif pada final board dari {samples} simulasi.",
            "svg": horizontal_bar_chart(
                "Rata-rata Sinergi Aktif",
                synergy_rows,
                f"Jumlah sinergi aktif pada final board dari {samples} simulasi.",
                value_formatter=lambda value: f"{value:.2f}",
            ),
            "data": active_synergy_avg,
        },
        {
            "file": "checkpoint-gold-timeline.svg",
            "title": "Timeline Gold per Checkpoint",
            "subtitle": f"Rata-rata gold setelah keputusan pembelian dari {samples} simulasi.",
            "svg": line_chart(
                "Timeline Gold per Checkpoint",
                checkpoint_order,
                gold_series,
                f"Rata-rata gold setelah keputusan pembelian dari {samples} simulasi.",
            ),
            "data": gold_series,
        },
    ]

    for profile_key, profile in PROFILES.items():
        segments = {
            component: [
                mean(sim["weights_by_profile"][profile_key][checkpoint][component])
                if sim["weights_by_profile"][profile_key][checkpoint][component]
                else 0.0
                for checkpoint in checkpoint_order
            ]
            for component in ["greedy", "heuristic", "carry"]
        }
        charts.append(
            {
                "file": f"adaptive-weight-{safe_id(profile_key)}.svg",
                "title": f"Bobot Adaptive - {profile.name}",
                "subtitle": "Perubahan komposisi Greedy, Heuristic, dan Carry per checkpoint.",
                "svg": stacked_bar_chart(
                    f"Bobot Adaptive - {profile.name}",
                    checkpoint_order,
                    segments,
                    "Perubahan komposisi Greedy, Heuristic, dan Carry per checkpoint.",
                ),
                "data": segments,
            }
        )

    return charts


def write_chart_files(charts: Iterable[dict], output_dir: Path) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for chart in charts:
        target = output_dir / chart["file"]
        target.write_text(chart["svg"], encoding="utf-8")
        manifest.append(
            {
                "file": target.name,
                "title": chart["title"],
                "subtitle": chart["subtitle"],
                "data": chart["data"],
            }
        )
    return manifest


def render_html(manifest: list[dict], *, samples: int, seed: int, output_dir_name: str) -> str:
    cards = []
    for item in manifest:
        src = f"{output_dir_name}/{item['file']}"
        cards.append(
            f"""
      <article class="chart-card">
        <img src="{escape(src)}" alt="{escape(item['title'])}">
      </article>"""
        )

    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Grafik Analisis MCGG</title>
  <style>
    :root {{
      --ink: #14233f;
      --muted: #5e708e;
      --line: rgba(43, 91, 167, 0.16);
      --blue: #278dff;
      --paper: rgba(255, 255, 255, 0.78);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      background:
        radial-gradient(circle at 16% 8%, rgba(255, 200, 79, 0.34), transparent 22%),
        radial-gradient(circle at 86% 12%, rgba(110, 220, 255, 0.48), transparent 28%),
        linear-gradient(180deg, #dff7ff 0%, #f7fbff 42%, #eff4ff 100%);
    }}
    main {{
      width: min(1180px, calc(100% - 28px));
      margin: 26px auto 56px;
    }}
    .topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
      padding: 14px 18px;
      border: 1px solid rgba(255,255,255,.72);
      border-radius: 22px;
      background: rgba(255,255,255,.72);
      box-shadow: 0 16px 45px rgba(39,141,255,.16);
      backdrop-filter: blur(18px);
    }}
    h1 {{
      margin: 0;
      color: #18396f;
      font-size: clamp(2rem, 4vw, 3.6rem);
      line-height: 1;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }}
    .pill {{
      padding: 8px 12px;
      color: #31527f;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.68);
      font-size: .86rem;
      font-weight: 800;
    }}
    .chart-grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
    }}
    .chart-card {{
      overflow: hidden;
      border: 1px solid rgba(255,255,255,.74);
      border-radius: 24px;
      background: var(--paper);
      box-shadow: 0 24px 70px rgba(28,70,139,.18);
      backdrop-filter: blur(18px);
    }}
    .chart-card img {{
      display: block;
      width: 100%;
      height: auto;
    }}
    @media (max-width: 720px) {{
      .topbar {{
        align-items: flex-start;
        flex-direction: column;
      }}
      .meta {{
        justify-content: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header class="topbar">
      <h1>Grafik Analisis MCGG</h1>
      <div class="meta">
        <span class="pill">Sample: {samples}</span>
        <span class="pill">Seed: {seed}</span>
        <span class="pill">Generated: {escape(datetime.now().strftime("%Y-%m-%d %H:%M"))}</span>
      </div>
    </header>
    <section class="chart-grid">
{"".join(cards)}
    </section>
  </main>
</body>
</html>
"""


def write_manifest(manifest: list[dict], output_dir: Path, *, samples: int, seed: int) -> None:
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "samples": samples,
        "charts": manifest,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate grafik SVG dan HTML dari dataset serta simulasi Magic Chess Go Go.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=30,
        help="Jumlah simulasi untuk grafik perbandingan strategi. Default: 30.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Seed dasar agar hasil simulasi reproducible. Default: {DEFAULT_SEED}.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Folder output SVG. Default: output/grafik.",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=DEFAULT_HTML_FILE,
        help="File HTML galeri grafik. Default: output/grafik.html.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.samples < 1:
        raise SystemExit("--samples minimal 1.")

    output_dir = args.out_dir.resolve()
    html_file = args.html.resolve()
    html_file.parent.mkdir(parents=True, exist_ok=True)

    sim = collect_simulation(samples=args.samples, seed=args.seed)
    charts = dataset_charts() + simulation_charts(sim)
    manifest = write_chart_files(charts, output_dir)
    write_manifest(manifest, output_dir, samples=args.samples, seed=args.seed)

    try:
        output_dir_name = output_dir.relative_to(html_file.parent).as_posix()
    except ValueError:
        output_dir_name = output_dir.as_posix()
    html_file.write_text(
        render_html(
            manifest,
            samples=args.samples,
            seed=args.seed,
            output_dir_name=output_dir_name,
        ),
        encoding="utf-8",
    )

    print(f"Grafik SVG dibuat di: {output_dir}")
    print(f"Galeri HTML dibuat di: {html_file}")


if __name__ == "__main__":
    main()
