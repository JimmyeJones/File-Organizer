import { api } from "./api.js";
import { state } from "./state.js";
import { el } from "./util.js";

export async function renderEvents() {
  const { site } = state;
  const [planets, showers] = await Promise.all([
    api.planets(site.lat, site.lon),
    api.meteorShowers(),
  ]);

  const ptbody = document.querySelector("#planets-table tbody");
  ptbody.innerHTML = "";
  for (const p of planets.planets) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${p.name}</td>
      <td>${p.altitude_deg}°</td>
      <td>${p.azimuth_deg}°</td>
      <td>${p.distance_au} AU</td>
      <td>${p.above_horizon ? "<span class='tag good'>up</span>" : "<span class='tag'>below</span>"}</td>
    `;
    ptbody.appendChild(tr);
  }

  const meteorList = document.getElementById("meteor-list");
  meteorList.innerHTML = "";
  for (const s of showers.showers) {
    const card = el("div", { class: "meteor-card" },
      el("h3", {}, s.name),
      el("div", {}, el("span", { class: "zhr" }, `ZHR ~${s.zhr}`)),
      el("div", { class: "muted small" }, `Peak: ${s.peak_date}`),
      el("div", { class: "muted small" }, `Active: ${s.active_start} → ${s.active_end}`),
      el("div", { class: "muted small" }, `Radiant: RA ${s.radiant_ra}h, Dec ${s.radiant_dec}°`),
    );
    meteorList.appendChild(card);
  }
  if (showers.showers.length === 0) {
    meteorList.appendChild(el("p", { class: "muted" }, "No major showers in the next 90 days."));
  }
}
