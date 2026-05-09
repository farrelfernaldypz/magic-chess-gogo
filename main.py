from __future__ import annotations

import json
import random
import webbrowser
from pathlib import Path

from algorithms.game_simulator import simulate_all_profiles
from data.heroes import HEROES

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "index.html"
OUTPUT_DATA_FILE = OUTPUT_DIR / "data.js"
DATASET_FILE = OUTPUT_DIR / "dataset.html"
DATASET_DATA_FILE = OUTPUT_DIR / "dataset-data.js"
HERO_DATA_FILE = BASE_DIR / "data" / "raw" / "heroes_id.json"
SYNERGY_DATA_FILE = BASE_DIR / "data" / "raw" / "synergies_id.json"


def _run_to_dict(run):
    return {
        "seed": run.seed,
        "profile": {
            "name": run.profile.name,
            "accent": run.profile.accent,
        },
        "final_power": run.final_power,
        "final_board": [HEROES[h].name for h in run.final_board.heroes_on_board],
        "final_synergies": run.final_synergies,
        "snapshots": [
            {
                "phase_label": snap.phase_label,
                "checkpoint_label": snap.checkpoint_label,
                "player_level": snap.player_level,
                "subtitle": snap.subtitle,
                "round_number": snap.round_number,
                "gold_after": snap.gold_after,
                "board_after": [HEROES[h].name for h in snap.board_after],
                "shop": [HEROES[h].name for h in snap.shop_heroes],
                "chosen": HEROES[snap.chosen_hero_id].name if snap.chosen_hero_id in HEROES else "-",
                "chosen_reason": snap.chosen_reason,
                "carry": HEROES[snap.carry_hero_id].name if snap.carry_hero_id in HEROES else "-",
                "carry_reason": snap.carry_reason,
                "decision_algorithm": snap.decision_algorithm,
                "adaptive_mode": snap.adaptive_mode,
                "recommendations": [
                    {
                        "rank": rec.rank,
                        "hero": rec.hero_name,
                        "cost": rec.cost,
                        "adjusted": rec.adjusted,
                        "reason": rec.reason,
                    }
                    for rec in snap.recommendations[:3]
                ],
            }
            for snap in run.snapshots
        ],
    }


def build_games(sample_count: int = 20):
    games = []
    for _ in range(sample_count):
        seed = random.randint(10000, 999999)
        runs = simulate_all_profiles(seed)
        games.append({"seed": seed, "runs": {key: _run_to_dict(run) for key, run in runs.items()}})
    return games


def render_html() -> str:
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MCGG Hybrid Optimizer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@600;700;800;900&family=Inter:wght@400;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="sky-glow" aria-hidden="true"></div>
  <header class="topbar">
    <a class="brand" href="index.html" aria-label="MCGG Hybrid Optimizer">
      <img class="brand-logo" src="assets/logo/download.jpg" alt="">
      <span>MCGG Hybrid Optimizer</span>
    </a>
    <nav class="nav-pills" aria-label="Main navigation">
      <a href="#top">Home</a>
      <a href="#shop">Rekomendasi</a>
      <a href="#build">Lineup</a>
      <a href="#dataset">Dataset</a>
    </nav>
  </header>

  <main id="top" class="page-shell">
    <section class="hero-section">
      <div class="hero-copy">
        <span class="season-chip">Greedy - Heuristic - Adaptive</span>
        <h1>MCGG Hybrid Optimizer</h1>
        <div class="hero-actions">
          <button id="next-game" class="btn btn-gold" type="button">Next Game</button>
          <label class="strategy-picker">
            <span>Strategi</span>
            <select id="strategy-select" aria-label="Pilih strategi">
              <option value="farming">Farming / Scavenger</option>
              <option value="neobeast">Stacking / Neobeasts</option>
              <option value="normal">Normal</option>
            </select>
          </label>
        </div>
      </div>
    </section>

    <section id="simulator" class="summary-grid" aria-label="Ringkasan simulasi">
      <article class="summary-card">
        <span>Strategi</span>
        <strong id="summary-profile">-</strong>
      </article>
      <article class="summary-card">
        <span>Final Power</span>
        <strong id="summary-power">-</strong>
      </article>
      <article class="summary-card">
        <span>Core Synergy</span>
        <strong id="summary-synergy">-</strong>
      </article>
      <article class="summary-card">
        <span>Seed</span>
        <strong id="summary-seed">-</strong>
      </article>
    </section>

    <section class="algorithm-guide" aria-label="Penjelasan algoritma per fase">
      <article class="guide-card">
        <span>Early Game</span>
        <h3>Greedy</h3>
        <p>Dipakai pada checkpoint 2-1 dan 2-5 karena keputusan awal harus cepat, murah, dan langsung memberi value dari shop yang tersedia.</p>
      </article>
      <article class="guide-card">
        <span>Mid Game</span>
        <h3>Heuristic</h3>
        <p>Dipakai pada checkpoint 3-2 dan 4-1 karena board sudah punya arah, sehingga pilihan hero perlu melihat potensi synergy, carry transisi, dan jalur late game.</p>
      </article>
      <article class="guide-card">
        <span>Late Game</span>
        <h3>Adaptive</h3>
        <p>Dipakai pada checkpoint 5-1 dan 6-1 karena keputusan akhir harus menyesuaikan gold, level shop, carry yang sudah terbentuk, dan peluang upgrade ke hero cost tinggi.</p>
      </article>
    </section>

    <section id="shop" class="timeline" aria-label="Simulasi tiap fase">
      <div class="panel-title">
        <span>Refresh Timeline</span>
        <h2>Shop, Pick, dan Rekomendasi</h2>
      </div>
      <div id="phase-list"></div>
    </section>

    <section id="build" class="feature-panel build-panel">
      <div class="panel-title">
        <span>Final Lineup</span>
        <h2>Lineup Akhir</h2>
      </div>
      <div id="final-build"></div>
    </section>

    <section id="dataset" class="dataset-page">
      <section class="hero-section dataset-hero">
        <div class="hero-copy">
          <span class="season-chip">Season 5 Dataset</span>
          <h1>Hero & Synergy Data</h1>
        </div>
      </section>

      <section class="dataset-toolbar">
        <div class="dataset-tabs" role="tablist" aria-label="Dataset tab">
          <button id="hero-tab" class="btn btn-primary" type="button">Hero</button>
          <button id="synergy-tab" class="btn btn-soft" type="button">Sinergi</button>
        </div>
        <label class="dataset-search">
          <span>Search</span>
          <input id="dataset-search" type="search" placeholder="Cari hero atau sinergi...">
        </label>
      </section>

      <section class="summary-grid dataset-summary" aria-label="Dataset summary">
        <article class="summary-card">
          <span>Total Hero</span>
          <strong id="hero-count">-</strong>
        </article>
        <article class="summary-card">
          <span>Total Sinergi</span>
          <strong id="synergy-count">-</strong>
        </article>
        <article class="summary-card">
          <span>Mode</span>
          <strong id="dataset-mode">Hero</strong>
        </article>
        <article class="summary-card">
          <span>Patch</span>
          <strong>Season 5</strong>
        </article>
      </section>

      <section class="feature-panel">
        <div class="panel-title">
          <span id="dataset-kicker">Hero Dataset</span>
          <h2 id="dataset-title">Daftar Hero</h2>
        </div>
        <div id="dataset-content"></div>
      </section>
    </section>
  </main>

  <div class="bgm-control" aria-label="Background music controls">
    <button id="bgm-toggle" class="btn btn-audio is-playing" type="button" aria-pressed="true">Mute</button>
    <label class="volume-control">
      <span>Vol</span>
      <input id="bgm-volume" type="range" min="0" max="100" value="35">
    </label>
  </div>

  <script src="data.js"></script>
  <script src="dataset-data.js"></script>
  <script src="script.js"></script>
  <script src="dataset.js"></script>
  <script src="bgm.js"></script>
</body>
</html>"""


def render_data(payload: list[dict]) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    return f"window.MCGG_GAMES = {data};\n"


def render_dataset_html() -> str:
    return """<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=index.html#dataset">
  <title>Dataset - MCGG Hybrid Optimizer</title>
</head>
<body>
  <script>window.location.replace("index.html#dataset");</script>
</body>
</html>"""


def render_dataset_data() -> str:
    heroes = json.loads(HERO_DATA_FILE.read_text(encoding="utf-8"))
    synergies = json.loads(SYNERGY_DATA_FILE.read_text(encoding="utf-8"))
    data = json.dumps({"heroes": heroes, "synergies": synergies}, ensure_ascii=False)
    return f"window.MCGG_DATASET = {data};\n"


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_games(20)
    OUTPUT_FILE.write_text(render_html(), encoding="utf-8")
    OUTPUT_DATA_FILE.write_text(render_data(payload), encoding="utf-8")
    DATASET_FILE.write_text(render_dataset_html(), encoding="utf-8")
    DATASET_DATA_FILE.write_text(render_dataset_data(), encoding="utf-8")
    print(f"Dashboard berhasil dibuat: {OUTPUT_FILE}")
    try:
        webbrowser.open(OUTPUT_FILE.as_uri())
    except Exception:
        pass


if __name__ == "__main__":
    main()
