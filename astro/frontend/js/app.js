import { state, init as initState, onChange, setSite, setDate, refreshSites } from "./state.js";
import { api } from "./api.js";
import { toast } from "./util.js";
import { renderTonight } from "./tonight.js";
import { renderWeather } from "./weather.js";
import { renderTargets } from "./targets.js";
import { renderSky } from "./sky.js";
import { renderSkyMap } from "./skyview.js";
import { renderSats } from "./sats.js";
import { renderEvents } from "./events.js";
import { renderSites } from "./sites.js";

const renderers = {
  tonight: renderTonight,
  weather: renderWeather,
  targets: renderTargets,
  skymap: renderSkyMap,
  sky: renderSky,
  satellites: renderSats,
  events: renderEvents,
  sites: renderSites,
};

let activeTab = "tonight";

window.addEventListener("DOMContentLoaded", async () => {
  // Wait for Chart.js / Leaflet to be ready (loaded with defer)
  await waitForGlobals(["Chart", "L"]);

  await initState();

  // Date picker
  const dateInput = document.getElementById("date-input");
  dateInput.value = state.date;
  dateInput.addEventListener("change", () => setDate(dateInput.value));

  // Site picker
  populateSiteSelect();
  document.getElementById("site-select").addEventListener("change", (e) => {
    const id = e.target.value;
    if (id === "__current_location__") return;
    const site = state.sites.find(s => s.id === id);
    if (site) setSite(site);
  });

  document.getElementById("btn-add-site").addEventListener("click", () => {
    activateTab("sites");
  });

  document.getElementById("btn-use-location").addEventListener("click", useGeolocation);

  // Tabs
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  // Target filter refresh
  document.getElementById("btn-refresh-targets").addEventListener("click", renderTargets);

  // Re-render when state changes
  onChange(() => {
    populateSiteSelect();
    runCurrent();
  });

  await runCurrent();
});

async function waitForGlobals(names, timeoutMs = 5000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (names.every(n => typeof window[n] !== "undefined")) return;
    await new Promise(r => setTimeout(r, 50));
  }
}

function populateSiteSelect() {
  const sel = document.getElementById("site-select");
  const current = state.site;
  sel.innerHTML = "";
  if (current && !current.id) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = current.name;
    opt.selected = true;
    sel.appendChild(opt);
  }
  for (const s of state.sites) {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    if (current && current.id === s.id) opt.selected = true;
    sel.appendChild(opt);
  }
  if (state.sites.length === 0 && !current) {
    const opt = document.createElement("option");
    opt.textContent = "No sites — add one";
    sel.appendChild(opt);
  }
}

async function activateTab(name) {
  activeTab = name;
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".panel").forEach(p => p.classList.toggle("active", p.id === `panel-${name}`));
  await runCurrent();
}

async function runCurrent() {
  const fn = renderers[activeTab];
  if (!fn) return;
  try {
    await fn();
  } catch (e) {
    console.error(e);
    toast(`Error: ${e.message}`);
  }
}

function useGeolocation() {
  if (!navigator.geolocation) {
    toast("Geolocation unavailable in this browser");
    return;
  }
  toast("Requesting location…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      setSite({
        name: `My location (${pos.coords.latitude.toFixed(3)}, ${pos.coords.longitude.toFixed(3)})`,
        lat: pos.coords.latitude,
        lon: pos.coords.longitude,
      });
      toast("Using current location");
    },
    (err) => toast(`Location error: ${err.message}`),
    { timeout: 10000 },
  );
}
