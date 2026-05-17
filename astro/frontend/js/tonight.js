import { api } from "./api.js";
import { state } from "./state.js";
import { fmtTime, durationHours, el } from "./util.js";

let cloudChart, seeingChart;

export async function renderTonight() {
  const { site, date } = state;
  if (!site) return;

  const [sunMoon, weather, targets] = await Promise.all([
    api.sunMoon(site.lat, site.lon, date),
    api.weather(site.lat, site.lon),
    api.targets(site.lat, site.lon, { date, limit: 8 }),
  ]);

  renderSummary(sunMoon, weather);
  renderMoon(sunMoon.moon);
  renderTimeline(sunMoon.twilight);
  renderCloudChart(weather);
  renderSeeingChart(weather);
  renderTopTargets(targets);
}

function renderSummary(sunMoon, weather) {
  const tw = sunMoon.twilight;
  const darkHours = durationHours(tw.astronomical_dusk, tw.astronomical_dawn);
  const moon = sunMoon.moon;

  // Pull cloud cover during dark window from consensus
  const consensus = weather.consensus || [];
  const darkStart = tw.astronomical_dusk ? new Date(tw.astronomical_dusk) : null;
  const darkEnd = tw.astronomical_dawn ? new Date(tw.astronomical_dawn) : null;
  let cloudsDark = null;
  if (darkStart && darkEnd) {
    const inWindow = consensus.filter(c => {
      const t = new Date(c.time);
      return t >= darkStart && t <= darkEnd && c.cloud_cover_pct != null;
    });
    if (inWindow.length) {
      cloudsDark = inWindow.reduce((s, c) => s + c.cloud_cover_pct, 0) / inWindow.length;
    }
  }

  const container = document.getElementById("tonight-summary");
  container.innerHTML = "";
  const stats = [
    ["Site", state.site.name],
    ["Dark window", darkHours ? `${darkHours.toFixed(1)} h` : "—"],
    ["Astro dusk", fmtTime(tw.astronomical_dusk)],
    ["Astro dawn", fmtTime(tw.astronomical_dawn)],
    ["Avg clouds (dark)", cloudsDark != null ? `${Math.round(cloudsDark)}%` : "—"],
    ["Moon", `${Math.round(moon.illumination_fraction * 100)}% · ${moon.phase_name}`],
  ];
  for (const [label, value] of stats) {
    container.appendChild(el("div", { class: "stat" },
      el("div", { class: "label" }, label),
      el("div", { class: "value" }, value),
    ));
  }
}

function renderMoon(moon) {
  const card = document.getElementById("moon-card");
  card.innerHTML = "";

  const viz = el("div", { class: "moon-viz" });
  const lit = el("div", { class: "lit" });
  const shadow = el("div", { class: "shadow" });
  viz.appendChild(lit);
  viz.appendChild(shadow);
  // Phase angle 0=new, 180=full. Crude clip-path for visual feel.
  const phase = moon.phase_angle_deg;
  const illum = moon.illumination_fraction;
  const waxing = moon.phase_name.toLowerCase().includes("waxing") ||
                 moon.phase_name === "First Quarter" || moon.phase_name === "Full Moon";
  if (waxing) {
    shadow.style.clipPath = `inset(0 ${illum * 100}% 0 0)`;
  } else {
    shadow.style.clipPath = `inset(0 0 0 ${illum * 100}%)`;
  }

  const info = el("div", { class: "moon-info" },
    el("div", {}, el("strong", {}, moon.phase_name)),
    el("div", { class: "muted small" }, `${Math.round(illum * 100)}% illuminated`),
    el("div", { class: "muted small" }, `Rise: ${fmtTime(moon.rise)} · Set: ${fmtTime(moon.set)}`),
    el("div", { class: "muted small" }, `Now: alt ${moon.altitude_deg.toFixed(0)}°, az ${moon.azimuth_deg.toFixed(0)}°`),
  );
  card.appendChild(viz);
  card.appendChild(info);
}

function renderTimeline(tw) {
  const container = document.getElementById("twilight-timeline");
  container.innerHTML = "";

  const events = [
    ["Sunset", tw.sunset],
    ["Civil dusk", tw.civil_dusk],
    ["Naut. dusk", tw.nautical_dusk],
    ["Astro dusk", tw.astronomical_dusk],
    ["Astro dawn", tw.astronomical_dawn],
    ["Naut. dawn", tw.nautical_dawn],
    ["Civil dawn", tw.civil_dawn],
    ["Sunrise", tw.sunrise],
  ].filter(([, t]) => t);

  if (events.length === 0) return;

  const times = events.map(([, t]) => new Date(t));
  const start = times[0];
  const end = times[times.length - 1];
  const span = end - start;

  for (const [name, iso] of events) {
    const t = new Date(iso);
    const pct = ((t - start) / span) * 100;
    const tick = el("div", { class: "tick" });
    tick.style.left = `${pct}%`;
    tick.appendChild(el("span", { class: "name" }, name));
    tick.appendChild(el("span", { class: "lbl" }, fmtTime(iso)));
    container.appendChild(tick);
  }
}

function renderCloudChart(weather) {
  const ctx = document.getElementById("cloud-chart").getContext("2d");
  const sources = (weather.sources || []).filter(s => s.ok);

  // Build datasets per source (only those with cloud_cover_pct)
  const datasets = [];
  const colors = ["#ff6666", "#66ccff", "#88ee88", "#ffaa66"];
  sources.forEach((src, i) => {
    const data = (src.hourly || [])
      .filter(h => h.cloud_cover_pct != null && h.time)
      .slice(0, 72)
      .map(h => ({ x: h.time, y: h.cloud_cover_pct }));
    if (data.length === 0) return;
    datasets.push({
      label: src.label || src.source,
      data,
      borderColor: colors[i % colors.length],
      backgroundColor: colors[i % colors.length] + "33",
      tension: 0.3,
      pointRadius: 0,
    });
  });

  if (cloudChart) cloudChart.destroy();
  cloudChart = new Chart(ctx, {
    type: "line",
    data: { datasets },
    options: chartOpts({ yMax: 100, yLabel: "Cloud %" }),
  });
}

function renderSeeingChart(weather) {
  const ctx = document.getElementById("seeing-chart").getContext("2d");
  const sevenTimer = (weather.sources || []).find(s => s.source === "7timer");
  if (!sevenTimer || !sevenTimer.ok) {
    if (seeingChart) seeingChart.destroy();
    seeingChart = null;
    ctx.canvas.parentElement.querySelector(".no-seeing")?.remove();
    const msg = el("p", { class: "muted small no-seeing" }, "7Timer seeing data unavailable.");
    ctx.canvas.parentElement.appendChild(msg);
    return;
  }

  const seeing = sevenTimer.hourly.filter(h => h.seeing_index != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.seeing_index }));
  const trans = sevenTimer.hourly.filter(h => h.transparency_index != null).slice(0, 72)
    .map(h => ({ x: h.time, y: h.transparency_index }));

  if (seeingChart) seeingChart.destroy();
  seeingChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [
        {
          label: "Seeing (lower=better)",
          data: seeing,
          borderColor: "#ff8866",
          backgroundColor: "#ff886633",
          tension: 0.3,
          pointRadius: 0,
        },
        {
          label: "Transparency (lower=better)",
          data: trans,
          borderColor: "#66ccff",
          backgroundColor: "#66ccff33",
          tension: 0.3,
          pointRadius: 0,
        },
      ],
    },
    options: chartOpts({ yMax: 8, yMin: 1, yLabel: "Index 1-8" }),
  });
}

function renderTopTargets(targets) {
  const container = document.getElementById("top-targets");
  container.innerHTML = "";
  if (!targets.targets || targets.targets.length === 0) {
    container.appendChild(el("p", { class: "muted" }, "No targets above the minimum altitude tonight."));
    return;
  }
  for (const t of targets.targets.slice(0, 8)) {
    container.appendChild(el("div", { class: "target-row compact" },
      el("span", { class: "id" }, t.id),
      el("div", { class: "name" },
        document.createTextNode(t.name),
        el("div", { class: "meta" }, `${t.type} · ${t.constellation} · mag ${t.mag}`),
      ),
      el("span", { class: "alt" }, `${t.peak_altitude_deg}°`),
      el("span", { class: "score" }, t.score.toFixed(0)),
    ));
  }
}

function chartOpts({ yMin = 0, yMax = 100, yLabel = "" } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { color: "#d8d8e8", font: { size: 11 } } },
      tooltip: { titleColor: "#fff", bodyColor: "#fff" },
    },
    scales: {
      x: {
        type: "time",
        time: { unit: "hour", displayFormats: { hour: "MMM d HH:mm" } },
        ticks: { color: "#8888a0", font: { size: 10 }, maxRotation: 0 },
        grid: { color: "#2a2a3d" },
      },
      y: {
        min: yMin, max: yMax,
        ticks: { color: "#8888a0", font: { size: 10 } },
        grid: { color: "#2a2a3d" },
        title: { display: !!yLabel, text: yLabel, color: "#8888a0" },
      },
    },
  };
}
