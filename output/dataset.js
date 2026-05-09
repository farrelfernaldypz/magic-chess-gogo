const dataset = window.MCGG_DATASET || { heroes: [], synergies: [] };
const datasetSynergyIcons = {
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

let activeMode = "heroes";

const heroTab = document.getElementById("hero-tab");
const synergyTab = document.getElementById("synergy-tab");
const searchInput = document.getElementById("dataset-search");
const heroCount = document.getElementById("hero-count");
const synergyCount = document.getElementById("synergy-count");
const datasetMode = document.getElementById("dataset-mode");
const datasetKicker = document.getElementById("dataset-kicker");
const datasetTitle = document.getElementById("dataset-title");
const datasetContent = document.getElementById("dataset-content");

function asText(value) {
    if (Array.isArray(value)) {
        return value.join(", ");
    }

    return value || "-";
}

function heroPower(hero) {
    const hp = hero.base_stats?.hp?.[0] || "-";
    const physical = hero.base_stats?.physical_atk?.[0] || "-";
    const magic = hero.base_stats?.magic_atk?.[0] || "-";
    return { hp, physical, magic };
}

function matchesQuery(item, query) {
    if (!query) {
        return true;
    }

    return JSON.stringify(item).toLowerCase().includes(query.toLowerCase());
}

function synergyIcon(name) {
    if (!datasetSynergyIcons[name]) {
        return "";
    }

    return `<img class="synergy-art" src="${encodeURI(`assets/synergy/${datasetSynergyIcons[name]}`)}" alt="">`;
}

function setTab(mode) {
    activeMode = mode;
    heroTab.className = mode === "heroes" ? "btn btn-primary" : "btn btn-soft";
    synergyTab.className = mode === "synergies" ? "btn btn-primary" : "btn btn-soft";
    datasetMode.textContent = mode === "heroes" ? "Hero" : "Sinergi";
    datasetKicker.textContent = mode === "heroes" ? "Hero Dataset" : "Synergy Dataset";
    datasetTitle.textContent = mode === "heroes" ? "Daftar Hero" : "Daftar Sinergi";
    renderDataset();
}

function renderHeroes(items) {
    if (!items.length) {
        return '<div class="empty-state">Data hero tidak ditemukan.</div>';
    }

    return `
        <div class="dataset-table-wrap">
            <table class="dataset-table">
                <thead>
                    <tr>
                        <th>Hero</th>
                        <th>Cost</th>
                        <th>Synergy</th>
                        <th>HP</th>
                        <th>Physical</th>
                        <th>Magic</th>
                        <th>Skill</th>
                    </tr>
                </thead>
                <tbody>
                    ${items.map((hero) => {
                        const power = heroPower(hero);
                        return `
                            <tr>
                                <td>${hero.hero_name}</td>
                                <td>${hero.cost}</td>
                                <td>${asText(hero.synergies)}</td>
                                <td>${power.hp}</td>
                                <td>${power.physical}</td>
                                <td>${power.magic}</td>
                                <td>${hero.skill?.name || "-"}</td>
                            </tr>
                        `;
                    }).join("")}
                </tbody>
            </table>
        </div>
    `;
}

function renderSynergies(items) {
    if (!items.length) {
        return '<div class="empty-state">Data sinergi tidak ditemukan.</div>';
    }

    return `
        <div class="dataset-grid">
            ${items.map((synergy) => `
                <article class="dataset-card">
                    <div class="dataset-card-head">
                        ${synergyIcon(synergy.synergy_name)}
                        <h3>${synergy.synergy_name}</h3>
                    </div>
                    <div class="dataset-meta">
                        <span>${synergy.type}</span>
                        <span>${(synergy.heroes || []).length} Hero</span>
                        <span>${(synergy.levels || []).map((level) => level.count).join(" / ") || "-"}</span>
                    </div>
                    <p>${synergy.description}</p>
                    <div class="chip-row">${(synergy.heroes || []).slice(0, 8).map((hero) => `<span class="chip">${hero}</span>`).join("")}</div>
                </article>
            `).join("")}
        </div>
    `;
}

function renderDataset() {
    const query = searchInput.value.trim();
    const source = activeMode === "heroes" ? dataset.heroes : dataset.synergies;
    const filtered = source.filter((item) => matchesQuery(item, query));

    datasetContent.innerHTML = activeMode === "heroes" ? renderHeroes(filtered) : renderSynergies(filtered);
}

heroCount.textContent = dataset.heroes.length;
synergyCount.textContent = dataset.synergies.length;
heroTab.addEventListener("click", () => setTab("heroes"));
synergyTab.addEventListener("click", () => setTab("synergies"));
searchInput.addEventListener("input", renderDataset);

setTab("heroes");
