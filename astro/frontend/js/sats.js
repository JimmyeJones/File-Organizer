import { api } from "./api.js";
import { state } from "./state.js";
import { fmtDateTime } from "./util.js";

export async function renderSats() {
  document.getElementById("btn-sat-refresh").onclick = loadPasses;
  await loadPasses();
}

async function loadPasses() {
  const { site } = state;
  const group = document.getElementById("sat-group").value;
  const hours = document.getElementById("sat-hours").value;
  const minAlt = document.getElementById("sat-min-alt").value;

  const tbody = document.querySelector("#sat-table tbody");
  tbody.innerHTML = `<tr><td colspan="6" class="muted">Loading…</td></tr>`;

  try {
    const data = await api.satellitePasses(site.lat, site.lon, group, hours, minAlt);
    tbody.innerHTML = "";
    if (data.passes.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted">No passes in the window.</td></tr>`;
      return;
    }
    for (const p of data.passes) {
      const tr = document.createElement("tr");
      if (p.visible) tr.classList.add("visible-pass");
      tr.innerHTML = `
        <td>${p.satellite}</td>
        <td>${fmtDateTime(p.rise)}</td>
        <td>${fmtDateTime(p.culmination)}</td>
        <td>${fmtDateTime(p.set)}</td>
        <td>${p.peak_altitude_deg}°</td>
        <td>${p.visible ? "<span class='tag good'>visible</span>" : "<span class='tag'>daylight</span>"}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="muted">Error: ${e.message}</td></tr>`;
  }
}
