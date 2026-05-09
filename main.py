from __future__ import annotations

import json
import random
import webbrowser
from pathlib import Path

from algorithms.game_simulator import PROFILES, simulate_all_profiles
from data.heroes import HEROES

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_FILE = OUTPUT_DIR / "magic_chess_dashboard.html"


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
                "subtitle": snap.subtitle,
                "round_number": snap.round_number,
                "gold_after": snap.gold_after,
                "board_after": [HEROES[h].name for h in snap.board_after],
                "shop": [HEROES[h].name for h in snap.shop_heroes],
                "chosen": HEROES[snap.chosen_hero_id].name if snap.chosen_hero_id in HEROES else "-",
                "chosen_reason": snap.chosen_reason,
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


def render_html(payload: dict) -> str:
    data = json.dumps(payload, ensure_ascii=False)
    html = """<!doctype html>
<html lang='id'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Magic Chess Game Simulator</title>
<style>
body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#08111d,#0b1524);color:#f8fafc;}
.wrap{max-width:1200px;margin:0 auto;padding:24px 18px 42px;}
.hero{background:linear-gradient(135deg,rgba(15,23,42,.95),rgba(17,24,39,.86));border:1px solid rgba(255,255,255,.08);padding:22px;border-radius:22px;}
.metrics,.grid3,.grid2{display:grid;gap:12px;}
.metrics{grid-template-columns:repeat(4,1fr);margin-top:14px;}
.grid3{grid-template-columns:repeat(3,1fr);} .grid2{grid-template-columns:1fr 1.2fr;}
.card{background:rgba(15,23,42,.86);border:1px solid rgba(255,255,255,.08);padding:14px;border-radius:16px;}
.phase{background:rgba(15,23,42,.76);border:1px solid rgba(255,255,255,.08);padding:18px;border-radius:18px;margin-top:16px;}
.chip{display:inline-block;padding:6px 10px;background:#1e293b;border-radius:999px;margin:4px 6px 0 0;font-size:.85rem;}
.small{color:#cbd5e1;font-size:.9rem;}.muted{color:#94a3b8;font-size:.82rem;}.h1{font-size:2rem;font-weight:800;margin-bottom:6px;}
button{background:#0ea5e9;border:none;color:white;padding:10px 14px;border-radius:10px;font-weight:700;cursor:pointer;margin-right:8px}
button.secondary{background:#1e293b}
.table{width:100%;border-collapse:collapse;margin-top:8px}.table th,.table td{padding:8px;border-bottom:1px solid rgba(255,255,255,.08);text-align:left;font-size:.9rem}.table th{color:#94a3b8}
@media(max-width:980px){.metrics,.grid3,.grid2{grid-template-columns:1fr;}}
</style>
</head>
<body>
<div class='wrap'>
  <div class='hero'>
    <div class='h1'>Magic Chess Go Go Simulator</div>
    <div class='small'>Tampilan disederhanakan biar lebih enak dibaca. Tinggal pilih strategi dan lihat inti rekomendasinya saja.</div>
    <div style='margin-top:14px'>
      <button onclick='prevProfile()' class='secondary'>◀ Strategi</button>
      <button onclick='nextProfile()'>Strategi Berikutnya ▶</button>
      <button onclick='nextGame()' style='background:#22c55e'>🎲 Next Game</button>
    </div>
  </div>
  <div id='app'></div>
</div>
<script>
const games = __DATA__;
let gameIndex = 0;
let profileIndex = 0;
const profileKeys = ['farming','neobeast','aggressive'];
function chipList(items){return (items||[]).map(x=>`<span class="chip">${x}</span>`).join('') || '-';}
function nextGame(){gameIndex = (gameIndex + 1) % games.length; render();}
function nextProfile(){profileIndex = (profileIndex + 1) % profileKeys.length; render();}
function prevProfile(){profileIndex = (profileIndex - 1 + profileKeys.length) % profileKeys.length; render();}
function recTable(items){return `<table class="table"><thead><tr><th>#</th><th>Hero</th><th>Cost</th><th>Score</th><th>Alasan</th></tr></thead><tbody>${(items||[]).map(r=>`<tr><td>${r.rank}</td><td>${r.hero}</td><td>${r.cost}</td><td>${r.adjusted}</td><td>${r.reason}</td></tr>`).join('')}</tbody></table>`}
function render(){
  const root = document.getElementById('app');
  const game = games[gameIndex];
  const key = profileKeys[profileIndex];
  const run = game.runs[key];
  root.innerHTML = `
    <div class="metrics" style="grid-template-columns:repeat(3,1fr)">
      <div class="card"><div class="muted">Strategi</div><div><b>${run.profile.name}</b></div></div>
      <div class="card"><div class="muted">Final Power</div><div><b>${run.final_power}</b></div></div>
      <div class="card"><div class="muted">Core Synergy</div><div><b>${run.final_synergies.slice(0,2).join(', ') || '-'}</b></div></div>
    </div>
    <div class="phase">
      <div style="font-size:1rem;font-weight:800">Build Akhir</div>
      <div class="small">Core synergy: ${run.final_synergies.join(', ') || '-'}</div>
      <div style="margin-top:8px">${chipList(run.final_board)}</div>
    </div>
    ${run.snapshots.map(s=>`
      <div class="phase">
        <div style="font-size:1.05rem;font-weight:800">${s.phase_label}</div>
        <div class="small">${s.subtitle}</div>
        <div class="metrics" style="grid-template-columns:repeat(3,1fr)">
          <div class="card"><div class="muted">Round</div><div><b>${s.round_number}</b></div></div>
          <div class="card"><div class="muted">Gold</div><div><b>${s.gold_after}</b></div></div>
          <div class="card"><div class="muted">Mode</div><div><b>${s.adaptive_mode}</b></div></div>
        </div>
        <div class="grid2" style="margin-top:12px">
          <div>
            <div class="small"><b>Shop</b></div>
            <div>${chipList(s.shop)}</div>
            <div class="small" style="margin-top:12px"><b>Dipilih</b></div>
            <div class="card" style="margin-top:8px"><b>${s.chosen}</b><div class="small">${s.chosen_reason}</div></div>
            <div class="small" style="margin-top:12px"><b>Board setelah beli</b></div>
            <div>${chipList(s.board_after)}</div>
          </div>
          <div>
            <div class="small"><b>Top 3 rekomendasi</b></div>
            ${recTable(s.recommendations)}
          </div>
        </div>
      </div>
    `).join('')}
  `;
}
render();
</script>
</body></html>"""
    return html.replace("__DATA__", data)


def build_games(sample_count: int = 20):
    games = []
    for _ in range(sample_count):
        seed = random.randint(10000, 999999)
        runs = simulate_all_profiles(seed)
        games.append({"seed": seed, "runs": {key: _run_to_dict(run) for key, run in runs.items()}})
    return games


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_games(20)
    OUTPUT_FILE.write_text(render_html(payload), encoding="utf-8")
    print(f"Dashboard berhasil dibuat: {OUTPUT_FILE}")
    try:
        webbrowser.open(OUTPUT_FILE.as_uri())
    except Exception:
        pass


if __name__ == "__main__":
    main()
