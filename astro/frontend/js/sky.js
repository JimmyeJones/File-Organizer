import { api } from "./api.js";
import { fmtDateTime } from "./util.js";

let sectorsLoaded = false;
let playTimer = null;
let frames = [];
let frameIdx = 0;

export async function renderSky() {
  if (!sectorsLoaded) {
    await loadSectors();
    sectorsLoaded = true;
  }
  await loadLatest();
}

async function loadSectors() {
  const { sectors, bands } = await api.goesSectors();
  const secSel = document.getElementById("goes-sector");
  const bandSel = document.getElementById("goes-band");
  secSel.innerHTML = "";
  for (const s of sectors) {
    const o = document.createElement("option");
    o.value = s.id;
    o.textContent = `${s.label} (${s.satellite})`;
    secSel.appendChild(o);
  }
  bandSel.innerHTML = "";
  for (const b of bands) {
    const o = document.createElement("option");
    o.value = b.id;
    o.textContent = `${b.id} — ${b.label}`;
    bandSel.appendChild(o);
  }
  document.getElementById("btn-goes-refresh").onclick = loadLatest;
  document.getElementById("btn-goes-play").onclick = togglePlay;
  secSel.onchange = loadLatest;
  bandSel.onchange = loadLatest;
}

async function loadLatest() {
  stopPlay();
  const sector = document.getElementById("goes-sector").value;
  const band = document.getElementById("goes-band").value;
  const img = document.getElementById("goes-image");
  const ts = document.getElementById("goes-timestamp");

  // Load animation frames so play is ready
  try {
    const data = await api.goesAnimation(sector, band, 12);
    frames = data.frames;
    frameIdx = 0;
    if (frames.length) {
      img.src = frames[0].url;
      ts.textContent = frames[0].timestamp ? fmtDateTime(frames[0].timestamp) + " UTC" : "Latest";
    } else {
      const { url } = await api.goesLatest(sector, band);
      img.src = url;
      ts.textContent = "Latest";
    }
  } catch (e) {
    const { url } = await api.goesLatest(sector, band);
    img.src = url;
    ts.textContent = "Latest";
  }
}

function togglePlay() {
  if (playTimer) {
    stopPlay();
  } else {
    startPlay();
  }
}

function startPlay() {
  if (!frames.length) return;
  // Play oldest → newest
  const ordered = [...frames].reverse();
  frameIdx = 0;
  const img = document.getElementById("goes-image");
  const ts = document.getElementById("goes-timestamp");
  document.getElementById("btn-goes-play").textContent = "■ Stop";
  playTimer = setInterval(() => {
    const f = ordered[frameIdx];
    img.src = f.url;
    ts.textContent = (f.timestamp ? fmtDateTime(f.timestamp) + " UTC" : "Frame") + ` (${frameIdx + 1}/${ordered.length})`;
    frameIdx = (frameIdx + 1) % ordered.length;
  }, 500);
}

function stopPlay() {
  if (playTimer) {
    clearInterval(playTimer);
    playTimer = null;
  }
  document.getElementById("btn-goes-play").textContent = "▶ Play loop";
}
