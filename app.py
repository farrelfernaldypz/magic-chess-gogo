from __future__ import annotations

import random
from typing import List

import pandas as pd
import streamlit as st

from algorithms.game_simulator import PROFILES, simulate_all_profiles
from data.heroes import HEROES
from data.synergies import SYNERGIES

st.set_page_config(page_title="Magic Chess Go Go Simulator", page_icon="♟️", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at 10% 5%, rgba(56,189,248,.12), transparent 18%),
            radial-gradient(circle at 85% 10%, rgba(168,85,247,.10), transparent 18%),
            linear-gradient(180deg, #09111f 0%, #0d1726 45%, #0b1320 100%);
    }
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1280px;}
    .mc-header {
        background: linear-gradient(135deg, rgba(15,23,42,.95), rgba(17,24,39,.86));
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 22px;
        padding: 22px 24px;
        box-shadow: 0 20px 60px rgba(0,0,0,.28);
        margin-bottom: 14px;
    }
    .mc-title {font-size: 2rem; font-weight: 800; color: #f8fafc; margin: 0 0 4px 0;}
    .mc-sub {color: #cbd5e1; font-size: .94rem; margin: 0;}
    .metric-card {
        background: rgba(15,23,42,.82);
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 16px;
        padding: 14px 16px;
        height: 100%;
    }
    .metric-label {color: #94a3b8; font-size: .76rem; text-transform: uppercase; letter-spacing: .08em;}
    .metric-value {color: #f8fafc; font-size: 1.25rem; font-weight: 800; margin-top: 4px;}
    .phase-wrap {
        background: rgba(15,23,42,.78);
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 18px;
        padding: 18px;
        margin-top: 10px;
    }
    .phase-title {font-size: 1.1rem; font-weight: 800; color: #f8fafc; margin-bottom: 4px;}
    .phase-sub {font-size: .88rem; color: #cbd5e1; margin-bottom: 10px;}
    .hero-chip {
        display:inline-block; padding: 6px 10px; margin: 4px 6px 0 0; border-radius: 999px;
        background: rgba(30,41,59,.96); border:1px solid rgba(255,255,255,.08); color:#e2e8f0; font-size:.82rem;
    }
    .small-note {color:#94a3b8; font-size:.82rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def hero_dataframe() -> pd.DataFrame:
    rows = []
    for hero in HEROES.values():
        rows.append(
            {
                "Hero": hero.name,
                "Cost": hero.cost,
                "Role": hero.role,
                "Synergy": ", ".join(hero.synergies),
                "HP": hero.base_hp,
                "ATK": hero.base_atk,
                "ATK Speed": hero.atk_speed,
                "Range": hero.attack_range,
                "Carry Score": hero.carry_score,
                "Skill Power": hero.skill_power,
                "Power Index": round(hero.power_index, 2),
                "Skill": hero.skill_name,
            }
        )
    return pd.DataFrame(rows).sort_values("Power Index", ascending=False)


def synergy_dataframe() -> pd.DataFrame:
    rows = []
    for synergy in SYNERGIES.values():
        rows.append(
            {
                "Synergy": synergy.name,
                "Kategori": synergy.category,
                "Jumlah Hero": len(synergy.heroes),
                "Tier": " / ".join(str(t.required) for t in synergy.tiers),
                "Deskripsi": synergy.description,
                "Hero": ", ".join(synergy.heroes),
            }
        )
    return pd.DataFrame(rows).sort_values(["Kategori", "Synergy"])


def hero_names(ids: List[str]) -> str:
    return ", ".join(HEROES[i].name for i in ids if i in HEROES) or "-"


def render_chips(ids: List[str], mode: str = "board"):
    if not ids:
        st.caption("-")
        return
    html = []
    for hid in ids:
        hero = HEROES[hid]
        label = f"{hero.name} • {hero.cost}G" if mode == "shop" else f"{hero.name}"
        html.append(f"<span class='hero-chip'>{label}</span>")
    st.markdown("".join(html), unsafe_allow_html=True)


def render_metric_cards(run, profile_name: str):
    cols = st.columns(3)
    data = [
        ("Strategi", profile_name),
        ("Final Power", run.final_power),
        ("Core Synergy", ", ".join(run.final_synergies[:2]) if run.final_synergies else "-"),
    ]
    for col, (label, value) in zip(cols, data):
        col.markdown(
            f"<div class='metric-card'><div class='metric-label'>{label}</div><div class='metric-value' style='font-size:{'1rem' if label in ['Strategi','Core Synergy'] else '1.25rem'}'>{value}</div></div>",
            unsafe_allow_html=True,
        )


def recommendation_table(snapshot) -> pd.DataFrame:
    rows = []
    for rec in snapshot.recommendations[:3]:
        rows.append(
            {
                "Rank": rec.rank,
                "Hero": rec.hero_name,
                "Cost": rec.cost,
                "Hybrid": rec.hybrid,
                "Adjusted": rec.adjusted,
                "Alasan": rec.reason,
            }
        )
    return pd.DataFrame(rows)


def render_phase(snapshot):
    chosen_name = HEROES[snapshot.chosen_hero_id].name if snapshot.chosen_hero_id in HEROES else "-"
    st.markdown(
        f"<div class='phase-wrap'><div class='phase-title'>{snapshot.phase_label}</div><div class='phase-sub'>{snapshot.subtitle}</div></div>",
        unsafe_allow_html=True,
    )
    top = st.columns(3)
    top[0].metric("Round", snapshot.round_number)
    top[1].metric("Gold Sisa", snapshot.gold_after)
    top[2].metric("Adaptive Mode", snapshot.adaptive_mode.upper())

    left, right = st.columns([1, 1.2])
    with left:
        st.write("Shop yang muncul")
        render_chips(snapshot.shop_heroes, mode="shop")
        st.write("Hero yang dipilih")
        st.success(f"{chosen_name}")
        st.caption(snapshot.chosen_reason)
        st.write("Board setelah beli")
        render_chips(snapshot.board_after, mode="board")
        if snapshot.active_synergies_after:
            short_syn = ", ".join(f"{item['name']} ({item['count']})" for item in snapshot.active_synergies_after[:4])
            st.info(f"Synergy aktif: {short_syn}")

    with right:
        st.write("Top 3 rekomendasi")
        rec_df = recommendation_table(snapshot)
        st.dataframe(rec_df, use_container_width=True, hide_index=True)
        weight_df = pd.DataFrame(
            {
                "Komponen": ["Greedy", "Heuristic", "Carry"],
                "Bobot": [
                    snapshot.adaptive_weights["greedy"],
                    snapshot.adaptive_weights["heuristic"],
                    snapshot.adaptive_weights["carry"],
                ],
            }
        )
        st.caption("Bobot adaptive")
        st.bar_chart(weight_df.set_index("Komponen"))


if "game_seed" not in st.session_state:
    st.session_state.game_seed = random.randint(10000, 999999)
if "runs" not in st.session_state:
    st.session_state.runs = simulate_all_profiles(st.session_state.game_seed)

st.sidebar.title("Kontrol")
st.sidebar.caption("Biar gak ribet, yang penting aja ditampilin.")
if st.sidebar.button("🎲 Next Game", use_container_width=True):
    st.session_state.game_seed = random.randint(10000, 999999)
    st.session_state.runs = simulate_all_profiles(st.session_state.game_seed)

selected_profile = st.sidebar.selectbox(
    "Strategi",
    options=list(PROFILES.keys()),
    format_func=lambda x: PROFILES[x].name,
)
show_dataset = st.sidebar.toggle("Tampilkan dataset", value=False)

heroes_df = hero_dataframe()
synergies_df = synergy_dataframe()
runs = st.session_state.runs
selected_run = runs[selected_profile]
selected_profile_obj = PROFILES[selected_profile]

st.markdown(
    """
    <div class='mc-header'>
      <div class='mc-title'>Magic Chess Go Go Simulator</div>
      <p class='mc-sub'>Satu game baru dimulai dari awal saat tombol <b>Next Game</b> ditekan. Yang ditampilkan cuma inti: strategi, pilihan hero, board, dan rekomendasi.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

render_metric_cards(selected_run, selected_profile_obj.name)

main_tab, dataset_tab, visual_tab = st.tabs(["Game", "Dataset", "Visualisasi"])

with main_tab:
    st.subheader("Ringkasan singkat")
    st.write(f"Strategi aktif: **{selected_profile_obj.name}**")
    st.write(f"Build akhir: **{hero_names(selected_run.final_board.heroes_on_board if selected_run.final_board else [])}**")

    phase_tabs = st.tabs([snap.phase_label for snap in selected_run.snapshots])
    for tab, snapshot in zip(phase_tabs, selected_run.snapshots):
        with tab:
            render_phase(snapshot)

with dataset_tab:
    if not show_dataset:
        st.info("Kalau gak perlu lihat tabel data, biarin toggle dataset di sidebar tetap mati. Lebih bersih, kan.")
    else:
        subtab1, subtab2 = st.tabs(["Hero", "Synergy"])
        with subtab1:
            keyword = st.text_input("Cari hero / role / synergy", "")
            filtered = heroes_df.copy()
            if keyword:
                mask = filtered.apply(lambda row: keyword.lower() in " ".join(map(str, row.values)).lower(), axis=1)
                filtered = filtered[mask]
            st.dataframe(filtered, use_container_width=True, hide_index=True)
        with subtab2:
            st.dataframe(synergies_df, use_container_width=True, hide_index=True)

with visual_tab:
    st.subheader("Visual singkat")
    c1, c2 = st.columns(2)
    with c1:
        st.caption("Distribusi Cost Hero")
        st.bar_chart(heroes_df.groupby("Cost").size().rename("Jumlah Hero"))
        st.caption("Jumlah Hero per Role")
        st.bar_chart(heroes_df.groupby("Role").size().rename("Jumlah Hero"))
    with c2:
        st.caption("Top 10 Hero berdasarkan Power Index")
        st.bar_chart(heroes_df.head(10).set_index("Hero")[["Power Index"]])
        st.caption("Jumlah Hero per Synergy")
        st.bar_chart(synergies_df.set_index("Synergy")[["Jumlah Hero"]].head(12))
