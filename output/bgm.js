const BGM_SOURCE = encodeURI("assets/bgm/Magic Chess Go Go Soundtrack - Season 5 Lobby - LilSoftieGacha Productions.mp3");
const BGM_KEYS = {
    muted: "mcgg-bgm-muted",
    volume: "mcgg-bgm-volume",
    time: "mcgg-bgm-time",
    wanted: "mcgg-bgm-wanted"
};

const bgmToggle = document.getElementById("bgm-toggle");
const bgmVolume = document.getElementById("bgm-volume");
const bgm = new Audio(BGM_SOURCE);

bgm.loop = true;
bgm.volume = Number(localStorage.getItem(BGM_KEYS.volume) || bgmVolume?.value || 35) / 100;
bgm.muted = localStorage.getItem(BGM_KEYS.muted) === "true";

if (bgmVolume) {
    bgmVolume.value = Math.round(bgm.volume * 100);
}

function saveBgmState() {
    localStorage.setItem(BGM_KEYS.muted, String(bgm.muted));
    localStorage.setItem(BGM_KEYS.volume, String(Math.round(bgm.volume * 100)));
    localStorage.setItem(BGM_KEYS.time, String(bgm.currentTime || 0));
    localStorage.setItem(BGM_KEYS.wanted, "true");
}

function syncMuteButton() {
    if (!bgmToggle) {
        return;
    }

    bgmToggle.classList.toggle("is-playing", !bgm.muted);
    bgmToggle.setAttribute("aria-pressed", String(!bgm.muted));
    bgmToggle.textContent = bgm.muted ? "Unmute" : "Mute";
}

function restoreTime() {
    const savedTime = Number(localStorage.getItem(BGM_KEYS.time) || 0);
    if (Number.isFinite(savedTime) && savedTime > 0) {
        try {
            bgm.currentTime = savedTime;
        } catch {
            bgm.addEventListener("loadedmetadata", () => {
                bgm.currentTime = Math.min(savedTime, Math.max(bgm.duration - 0.5, 0));
            }, { once: true });
        }
    }
}

async function startBgm() {
    if (!bgm.paused) {
        return;
    }

    restoreTime();

    try {
        await bgm.play();
        saveBgmState();
    } catch {
        // Most browsers block audible autoplay before the first user gesture.
        syncMuteButton();
    }
}

function toggleBgm() {
    bgm.muted = !bgm.muted;
    saveBgmState();

    if (!bgm.muted) {
        startBgm();
    }

    syncMuteButton();
}

function updateVolume() {
    if (!bgmVolume) {
        return;
    }

    bgm.volume = Number(bgmVolume.value) / 100;
    saveBgmState();
}

["pointerdown", "keydown"].forEach((eventName) => {
    window.addEventListener(eventName, startBgm, { once: true });
});

window.addEventListener("DOMContentLoaded", startBgm);
window.addEventListener("beforeunload", saveBgmState);
window.setInterval(saveBgmState, 1000);

bgmToggle?.addEventListener("click", toggleBgm);
bgmVolume?.addEventListener("input", updateVolume);

syncMuteButton();
