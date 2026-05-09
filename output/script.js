const games = window.MCGG_GAMES || [];
const profileKeys = ["farming", "neobeast", "normal"];
const synergyIcons = {
    "Beyond the Clouds": "Beyond The Clouds Synergy Icon in 8K Quality.jpg",
    Bruiser: "Bruiser Logo Synergy 3D version _ Magic Chess_ Go Go.jpg",
    Dauntless: "Dauntless Synergy Logo 3D version _ Magic Chess_ Go Go.jpg",
    Defender: "Defender Synergy Logo 3D version _ Magic Chess_ Go Go.jpg",
    Exorcist: "Exorcist Synergy Icons _ 8K Quality _ 3D Art.jpg",
    "Glory League": "Glory League Synergy Icon in 8K Quality.jpg",
    Heartbond: "Heartbond Synergy Icon _ 8K Quality _ 3D Art.jpg",
    KOF: "KOF Synergy Icon in 8K Quality.jpg",
    Luminexus: "Luminexus Synergy 3D version _ Magic Chess_ Go Go Season 3.jpg",
    Mage: "Mage Synergy Logo 3D version _ Magic Chess_ Go Go.jpg",
    Marksman: "Marksman Synergy Logo 3D version, Magic Chess_ Go Go.jpg",
    "Mortal Rival": "Mortal Rival Synergy Icon in 8K Quality.jpg",
    "Mystic Meow": "Mystic Meow Synergy Icon _ 8K Quality _ 3D Art.jpg",
    Neobeasts: "Neobeast Synergy Icons _ 8K Quality _ 3D Art.jpg",
    Phasewarper: "Phasewarper Synergy Icon in 8K Quality.jpg",
    Scavenger: "Scavenger Synergy 3D version _ Magic Chess_ Go Go Season 3.png",
    "Soul Vessels": "Soul Vessels Synergy Icon in 8K Quality.jpg",
    Stargazer: "Stargazer Synergy Logo 3D version _ Magic Chess_ Go Go.jpg",
    Swiftblade: "Swiftblade Synergy Icon in 8K Quality.jpg",
    "Toy Mischief": "Toy Mischief Synergy Icon in 8K Quality.jpg",
    "Weapon Master": "Weapon Master Synergy Icon in 8K Quality.jpg"
};

let gameIndex = 0;
let profileIndex = 0;
let navScrollLock = false;

const algorithmDescriptions = {
    Greedy: "Greedy dipakai karena early game butuh keputusan cepat dari shop yang muncul. Skor menekankan value langsung: cost hero, power saat ini, dan synergy yang bisa segera aktif.",
    Heuristic: "Heuristic dipakai karena mid game sudah punya arah board. Skor menilai potensi ke depan: completion synergy, kualitas carry transisi, keseimbangan role, dan jalur menuju hero premium.",
    Adaptive: "Adaptive dipakai karena late game bergantung pada kondisi aktual. Skor menyesuaikan gold, level shop, carry yang sudah terbentuk, board yang hampir penuh, dan peluang upgrade ke cost tinggi."
};

const summaryProfile = document.getElementById("summary-profile");
const summaryPower = document.getElementById("summary-power");
const summarySynergy = document.getElementById("summary-synergy");
const summarySeed = document.getElementById("summary-seed");
const finalBuild = document.getElementById("final-build");
const phaseList = document.getElementById("phase-list");
const strategySelect = document.getElementById("strategy-select");

function formatChips(items, type = "") {
    const values = items || [];
    if (!values.length) {
        return '<span class="chip">-</span>';
    }

    return values.map((item) => {
        const icon = type === "synergy" && synergyIcons[item]
            ? `<img class="chip-icon" src="${encodeURI(`assets/synergy/${synergyIcons[item]}`)}" alt="">`
            : "";
        return `<span class="chip ${type}">${icon}${item}</span>`;
    }).join("");
}

function recommendationRows(items) {
    return `
        <table class="rec-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Hero</th>
                    <th>Cost</th>
                    <th>Score</th>
                    <th>Alasan</th>
                </tr>
            </thead>
            <tbody>
                ${(items || []).map((rec) => `
                    <tr>
                        <td>${rec.rank}</td>
                        <td><strong>${rec.hero}</strong></td>
                        <td>${rec.cost}</td>
                        <td>${rec.adjusted}</td>
                        <td>${rec.reason}</td>
                    </tr>
                `).join("")}
            </tbody>
        </table>
    `;
}

function currentRun() {
    const game = games[gameIndex];
    const key = profileKeys[profileIndex];
    return { game, key, run: game.runs[key] };
}

function checkpointLineupReason(snapshot) {
    const boardSize = (snapshot.board_after || []).length;
    return `Pada checkpoint ${snapshot.checkpoint_label} level ${snapshot.player_level}, lineup berisi ${boardSize} hero. ${snapshot.chosen} dipilih karena ${snapshot.chosen_reason}. Carry utama saat ini adalah ${snapshot.carry}; ${snapshot.carry_reason}.`;
}

function render() {
    if (!games.length) {
        phaseList.innerHTML = '<article class="phase-card"><div class="phase-top"><h3>Data belum tersedia</h3></div></article>';
        return;
    }

    const { game, run } = currentRun();
    const accent = run.profile.accent || "#278dff";

    document.documentElement.style.setProperty("--accent", accent);
    strategySelect.value = profileKeys[profileIndex];
    summaryProfile.textContent = run.profile.name;
    summaryPower.textContent = run.final_power;
    summarySynergy.textContent = run.final_synergies.slice(0, 2).join(", ") || "-";
    summarySeed.textContent = game.seed;

    document.querySelectorAll(".summary-card").forEach((card, index) => {
        const colors = [accent, "rgba(53, 213, 152, 0.5)", "rgba(110, 220, 255, 0.5)", "rgba(255, 200, 79, 0.55)"];
        card.style.setProperty("--accent", colors[index]);
    });

    finalBuild.innerHTML = `
        <div class="chip-row">${formatChips(run.final_board, "board")}</div>
        <div class="chip-row" style="margin-top:12px">${formatChips(run.final_synergies, "synergy")}</div>
    `;

    phaseList.className = "phase-list";
    phaseList.innerHTML = run.snapshots.map((snapshot) => `
        <article class="phase-card" style="--phase-glow:${accent}33">
            <div class="phase-top">
                <div>
                    <span class="section-label">${snapshot.phase_label}</span>
                    <h3>${snapshot.checkpoint_label}</h3>
                    <div class="small">${snapshot.subtitle}</div>
                </div>
                <span class="mode-pill">${snapshot.adaptive_mode}</span>
            </div>

            <div class="phase-metrics">
                <div class="metric">
                    <span class="metric-label">Checkpoint</span>
                    <strong>${snapshot.checkpoint_label}</strong>
                </div>
                <div class="metric">
                    <span class="metric-label">Level</span>
                    <strong>${snapshot.player_level}</strong>
                </div>
                <div class="metric">
                    <span class="metric-label">Gold</span>
                    <strong>${snapshot.gold_after}</strong>
                </div>
                <div class="metric">
                    <span class="metric-label">Mode</span>
                    <strong>${snapshot.decision_algorithm}</strong>
                </div>
                <div class="metric">
                    <span class="metric-label">Carry</span>
                    <strong>${snapshot.carry}</strong>
                </div>
            </div>

            <div class="decision-notes">
                <div class="decision-note">
                    <span class="section-label">Kenapa ${snapshot.decision_algorithm}</span>
                    <p>${algorithmDescriptions[snapshot.decision_algorithm] || "-"}</p>
                </div>
                <div class="decision-note">
                    <span class="section-label">Kenapa lineup ini</span>
                    <p>${checkpointLineupReason(snapshot)}</p>
                </div>
            </div>

            <div class="phase-body">
                <div>
                    <div class="info-box">
                        <span class="section-label">Shop yang muncul</span>
                        <div class="chip-row">${formatChips(snapshot.shop, "shop")}</div>
                    </div>
                    <div class="info-box">
                        <span class="section-label">Hero yang dipilih</span>
                        <strong class="pick-name">${snapshot.chosen}</strong>
                        <div class="small">${snapshot.chosen_reason}</div>
                        <div class="small">${snapshot.carry_reason}</div>
                    </div>
                    <div class="info-box">
                        <span class="section-label">Board setelah beli</span>
                        <div class="chip-row">${formatChips(snapshot.board_after, "board")}</div>
                    </div>
                </div>
                <div class="rec-box">
                    <span class="section-label">Top 3 rekomendasi</span>
                    ${recommendationRows(snapshot.recommendations)}
                </div>
            </div>
        </article>
    `).join("");
}

function nextGame() {
    gameIndex = (gameIndex + 1) % games.length;
    render();
}

function localNavLinks() {
    return Array.from(document.querySelectorAll(".nav-pills a[href^='#']"));
}

function setActiveNav(hash) {
    const targetHash = hash || "#top";

    document.querySelectorAll(".nav-pills a").forEach((link) => {
        const linkHash = link.getAttribute("href");
        link.classList.toggle("active", linkHash === targetHash);
    });
}

function isLocalNavHash(hash) {
    return localNavLinks().some((link) => link.getAttribute("href") === hash);
}

function updateActiveNavFromScroll() {
    if (navScrollLock) {
        return;
    }

    const checkpoints = [
        { hash: "#top", element: document.getElementById("top") },
        { hash: "#shop", element: document.getElementById("shop") },
        { hash: "#build", element: document.getElementById("build") },
        { hash: "#dataset", element: document.getElementById("dataset") }
    ]
        .filter((item) => item.element)
        .sort((left, right) => left.element.offsetTop - right.element.offsetTop);

    const viewportMarker = window.scrollY + 160;
    let activeHash = "#top";

    checkpoints.forEach((item) => {
        if (item.element.offsetTop <= viewportMarker) {
            activeHash = item.hash;
        }
    });

    setActiveNav(activeHash);
}

localNavLinks().forEach((link) => {
    link.addEventListener("click", (event) => {
        const targetHash = link.getAttribute("href");
        const target = document.querySelector(targetHash);

        if (!target) {
            return;
        }

        event.preventDefault();
        navScrollLock = true;
        setActiveNav(targetHash);
        history.pushState(null, "", targetHash);
        target.scrollIntoView({ behavior: "smooth", block: "start" });

        window.setTimeout(() => {
            navScrollLock = false;
            setActiveNav(targetHash);
        }, 650);
    });
});

document.getElementById("next-game").addEventListener("click", nextGame);
strategySelect.addEventListener("change", (event) => {
    const selectedIndex = profileKeys.indexOf(event.target.value);
    profileIndex = selectedIndex >= 0 ? selectedIndex : 0;
    render();
});
window.addEventListener("hashchange", () => {
    const targetHash = isLocalNavHash(window.location.hash) ? window.location.hash : "#top";
    setActiveNav(targetHash);
});
window.addEventListener("scroll", updateActiveNavFromScroll, { passive: true });

render();

const initialHash = isLocalNavHash(window.location.hash) ? window.location.hash : "#top";
setActiveNav(initialHash);

if (initialHash !== "#top") {
    navScrollLock = true;
    window.requestAnimationFrame(() => {
        document.querySelector(initialHash)?.scrollIntoView({ behavior: "auto", block: "start" });
        window.setTimeout(() => {
            navScrollLock = false;
            setActiveNav(initialHash);
        }, 350);
    });
} else {
    updateActiveNavFromScroll();
}
