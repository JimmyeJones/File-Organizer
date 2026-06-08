import { api } from "./api.js";
import { state, refreshSites, setSite } from "./state.js";
import { el, toast } from "./util.js";

let map = null;
let markers = [];

export async function renderSites() {
  await refreshSites();
  renderTable();
  renderMap();
  bindForm();
}

function renderTable() {
  const tbody = document.querySelector("#sites-table tbody");
  tbody.innerHTML = "";
  if (state.sites.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="muted">No sites yet. Add one below.</td></tr>`;
    return;
  }
  for (const s of state.sites) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${escapeHtml(s.name)}</strong></td>
      <td><code>${s.lat.toFixed(4)}, ${s.lon.toFixed(4)}</code></td>
      <td>${s.bortle ?? "—"}</td>
      <td>
        <button data-act="use" data-id="${s.id}">Use</button>
        <button data-act="del" data-id="${s.id}">Delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  }
  tbody.onclick = async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    if (btn.dataset.act === "use") {
      const site = state.sites.find(s => s.id === id);
      if (site) {
        setSite(site);
        toast(`Now using ${site.name}`);
      }
    } else if (btn.dataset.act === "del") {
      if (!confirm("Delete this site?")) return;
      await api.deleteSite(id);
      await refreshSites();
      renderTable();
      renderMap();
    }
  };
}

function renderMap() {
  if (!map) {
    map = L.map("sites-map").setView([20, 0], 2);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "© OpenStreetMap",
      maxZoom: 18,
    }).addTo(map);
    map.on("click", (e) => {
      const form = document.getElementById("site-form");
      form.lat.value = e.latlng.lat.toFixed(4);
      form.lon.value = e.latlng.lng.toFixed(4);
      toast("Picked location on map");
    });
  }
  for (const m of markers) m.remove();
  markers = [];
  const bounds = [];
  for (const s of state.sites) {
    const marker = L.marker([s.lat, s.lon]).addTo(map).bindPopup(`<strong>${s.name}</strong>`);
    markers.push(marker);
    bounds.push([s.lat, s.lon]);
  }
  if (bounds.length === 1) map.setView(bounds[0], 8);
  else if (bounds.length > 1) map.fitBounds(bounds, { padding: [30, 30] });
}

function bindForm() {
  const form = document.getElementById("site-form");
  form.onsubmit = async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (!data.elevation_m) delete data.elevation_m;
    if (!data.bortle) delete data.bortle;
    if (!data.sqm) delete data.sqm;
    try {
      await api.createSite(data);
      toast(`Saved ${data.name}`);
      form.reset();
      await refreshSites();
      renderTable();
      renderMap();
    } catch (err) {
      toast(`Error: ${err.message}`);
    }
  };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
