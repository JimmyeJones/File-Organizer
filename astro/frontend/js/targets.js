import { api } from "./api.js";
import { state } from "./state.js";
import { el, fmtTime } from "./util.js";

let altChart;

export async function renderTargets() {
  const { site, date } = state;
  const opts = {
    date,
    min_altitude: document.getElementById("filter-min-alt").value,
    type_filter: document.getElementById("filter-type").value,
    limit: document.getElementById("filter-limit").value,
  };
  const data = await api.targets(site.lat, site.lon, opts);
  renderList(data);
}

function renderList(data) {
  const container = document.getElementById("full-targets");
  container.innerHTML = "";
  document.getElementById("targets-heading").textContent =
    `Ranked targets — ${data.count} total · showing ${data.targets.length}`;

  if (data.targets.length === 0) {
    container.appendChild(el("p", { class: "muted" }, "No targets match the current filters."));
    return;
  }

  for (const t of data.targets) {
    const row = el("div", { class: "target-row",
      onclick: () => showDetail(t),
    },
      el("span", { class: "id" }, t.id),
      el("div", { class: "name" },
        document.createTextNode(t.name),
        el("div", { class: "meta" },
          `${t.type} · ${t.constellation} · mag ${t.mag} · size ${t.size}′ · moon Δ ${t.moon_separation_deg}°`,
        ),
      ),
      el("span", { class: "alt", title: "Peak altitude" }, `${t.peak_altitude_deg}°`),
      el("span", { class: "alt", title: "Hours above min altitude" }, `${t.hours_above_min}h`),
      el("span", { class: "alt", title: "Peak time" }, fmtTime(t.peak_time)),
      el("span", { class: "score" }, t.score.toFixed(0)),
    );
    container.appendChild(row);
  }
}

async function showDetail(target) {
  const card = document.getElementById("target-detail-card");
  card.classList.remove("hidden");
  document.getElementById("target-detail-name").textContent =
    `${target.id} — ${target.name}`;

  const meta = document.getElementById("target-detail-meta");
  meta.innerHTML = "";
  for (const [k, v] of Object.entries({
    "Type": target.type,
    "Constellation": target.constellation,
    "Magnitude": target.mag,
    "Apparent size": `${target.size}′`,
    "RA": `${target.ra.toFixed(3)}h`,
    "Dec": `${target.dec.toFixed(3)}°`,
    "Peak altitude": `${target.peak_altitude_deg}° at ${fmtTime(target.peak_time)}`,
    "Hours visible": `${target.hours_above_min}h above min alt`,
    "Moon separation": `${target.moon_separation_deg}°`,
    "Score": target.score.toFixed(1),
  })) {
    meta.appendChild(el("div", {}, el("strong", {}, `${k}: `), document.createTextNode(v)));
  }
  if (target.notes && target.notes.length) {
    const list = el("ul", {});
    for (const n of target.notes) list.appendChild(el("li", {}, n));
    meta.appendChild(list);
  }

  const { site, date } = state;
  const data = await api.altitudeCurve(target.id, site.lat, site.lon, date);
  const ctx = document.getElementById("alt-chart").getContext("2d");
  const tw = data.twilight;

  const points = data.curve.map(p => ({ x: p.t, y: p.alt }));

  // Build twilight bands as annotation areas via background datasets
  if (altChart) altChart.destroy();
  altChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Altitude °",
          data: points,
          borderColor: "#ff8866",
          backgroundColor: "#ff886622",
          fill: true,
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#d8d8e8" } },
        tooltip: {
          callbacks: {
            label: (c) => `Alt: ${c.parsed.y.toFixed(1)}°`,
          },
        },
      },
      scales: {
        x: {
          type: "time",
          time: { unit: "hour", displayFormats: { hour: "HH:mm" } },
          ticks: { color: "#8888a0", maxRotation: 0 },
          grid: { color: "#2a2a3d" },
        },
        y: {
          min: -10, max: 90,
          ticks: { color: "#8888a0", callback: (v) => `${v}°` },
          grid: { color: "#2a2a3d" },
        },
      },
    },
  });

  card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
