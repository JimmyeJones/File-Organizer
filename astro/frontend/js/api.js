const base = "";

async function get(path, params = {}) {
  const url = new URL(base + path, window.location.origin);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
  }
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${path}`);
  return r.json();
}

async function post(path, body) {
  const r = await fetch(base + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${path}`);
  return r.json();
}

async function del(path) {
  const r = await fetch(base + path, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}: ${path}`);
  return r.json();
}

export const api = {
  sunMoon: (lat, lon, date) => get("/api/astro/sun-moon", { lat, lon, date }),
  planets: (lat, lon) => get("/api/astro/planets", { lat, lon }),
  meteorShowers: () => get("/api/astro/meteor-showers"),
  weather: (lat, lon) => get("/api/weather", { lat, lon }),
  targets: (lat, lon, opts = {}) => get("/api/targets", { lat, lon, ...opts }),
  altitudeCurve: (id, lat, lon, date) =>
    get(`/api/targets/${id}/altitude-curve`, { lat, lon, date }),
  goesSectors: () => get("/api/goes/sectors"),
  goesLatest: (sector, band) => get("/api/goes/latest", { sector, band }),
  goesAnimation: (sector, band, limit = 12) =>
    get("/api/goes/animation", { sector, band, limit }),
  satellitePasses: (lat, lon, group, hours, minAlt) =>
    get("/api/satellites/passes", { lat, lon, group, hours, min_altitude: minAlt }),
  sites: () => get("/api/sites"),
  createSite: (payload) => post("/api/sites", payload),
  deleteSite: (id) => del(`/api/sites/${id}`),
};
