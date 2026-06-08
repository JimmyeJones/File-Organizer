import { api } from "./api.js";
import { state } from "./state.js";
import { el, cloudCoverTag } from "./util.js";

let tempChart, windChart;

export async function renderWeather() {
  const { site } = state;
  const weather = await api.weather(site.lat, site.lon);
  renderSources(weather.sources || []);
  renderTempChart(weather);
  renderWindChart(weather);
}

function renderSources(sources) {
  const container = document.getElementById("weather-sources");
  container.innerHTML = "";
  for (const src of sources) {
    const card = el("div", { class: `source-card ${src.ok ? "ok" : "err"}` });
    card.appendChild(el("h3", {}, src.label || src.source || "unknown"));
    if (!src.ok) {
      card.appendChild(el("div", { class: "muted small" }, `Error: ${src.error || "unknown"}`));
    } else {
      const first = (src.hourly || []).find(h => h.cloud_cover_pct != null) || src.hourly[0] || {};
      card.appendChild(el("div", { class: "summary-row" },
        el("span", { class: "lbl" }, "Next-hour clouds"),
        el("span", { html: cloudCoverTag(first.cloud_cover_pct) }),
      ));
      if (first.temperature_c != null) {
        card.appendChild(el("div", { class: "summary-row" },
          el("span", { class: "lbl" }, "Temp"),
          el("span", {}, `${first.temperature_c}°C`),
        ));
      }
      if (first.humidity_pct != null) {
        card.appendChild(el("div", { class: "summary-row" },
          el("span", { class: "lbl" }, "Humidity"),
          el("span", {}, `${Math.round(first.humidity_pct)}%`),
        ));
      }
      if (first.wind_speed_kmh != null) {
        card.appendChild(el("div", { class: "summary-row" },
          el("span", { class: "lbl" }, "Wind"),
          el("span", {}, `${first.wind_speed_kmh} km/h`),
        ));
      }
      if (first.seeing_label) {
        card.appendChild(el("div", { class: "summary-row" },
          el("span", { class: "lbl" }, "Seeing"),
          el("span", {}, first.seeing_label),
        ));
      }
      if (first.transparency_label) {
        card.appendChild(el("div", { class: "summary-row" },
          el("span", { class: "lbl" }, "Transparency"),
          el("span", {}, first.transparency_label),
        ));
      }
    }
    container.appendChild(card);
  }
}

function renderTempChart(weather) {
  const ctx = document.getElementById("temp-chart").getContext("2d");
  const om = (weather.sources || []).find(s => s.source === "open-meteo");
  if (!om || !om.ok) return;

  const temps = om.hourly.filter(h => h.temperature_c != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.temperature_c }));
  const dew = om.hourly.filter(h => h.dew_point_c != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.dew_point_c }));

  if (tempChart) tempChart.destroy();
  tempChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        { label: "Temperature °C", data: temps, borderColor: "#ff8866", backgroundColor: "#ff886622", tension: 0.3, pointRadius: 0 },
        { label: "Dew point °C", data: dew, borderColor: "#66ccff", backgroundColor: "#66ccff22", tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#d8d8e8" } } },
      scales: {
        x: { type: "time", time: { unit: "hour" }, ticks: { color: "#8888a0", maxRotation: 0 }, grid: { color: "#2a2a3d" } },
        y: { ticks: { color: "#8888a0" }, grid: { color: "#2a2a3d" } },
      },
    },
  });
}

function renderWindChart(weather) {
  const ctx = document.getElementById("wind-chart").getContext("2d");
  const om = (weather.sources || []).find(s => s.source === "open-meteo");
  if (!om || !om.ok) return;

  const wind = om.hourly.filter(h => h.wind_speed_kmh != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.wind_speed_kmh }));
  const gusts = om.hourly.filter(h => h.wind_gusts_kmh != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.wind_gusts_kmh }));

  if (windChart) windChart.destroy();
  windChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        { label: "Wind km/h", data: wind, borderColor: "#88ee88", backgroundColor: "#88ee8822", tension: 0.3, pointRadius: 0 },
        { label: "Gusts km/h", data: gusts, borderColor: "#ff6666", backgroundColor: "#ff666622", tension: 0.3, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#d8d8e8" } } },
      scales: {
        x: { type: "time", time: { unit: "hour" }, ticks: { color: "#8888a0", maxRotation: 0 }, grid: { color: "#2a2a3d" } },
        y: { min: 0, ticks: { color: "#8888a0" }, grid: { color: "#2a2a3d" } },
      },
    },
  });
}
