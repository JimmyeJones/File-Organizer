// Application state — current site selection, date, cached responses.
import { api } from "./api.js";

const STORAGE_KEY = "astro-planner-state";

export const state = {
  site: null,           // { id?, name, lat, lon, ... }
  date: null,           // ISO date string
  sites: [],            // saved sites
  listeners: new Set(),
};

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    site: state.site,
    date: state.date,
  }));
}

export function onChange(fn) {
  state.listeners.add(fn);
  return () => state.listeners.delete(fn);
}

function notify() {
  for (const fn of state.listeners) {
    try { fn(state); } catch (e) { console.error(e); }
  }
}

export function setSite(site) {
  state.site = site;
  save();
  notify();
}

export function setDate(date) {
  state.date = date;
  save();
  notify();
}

export async function init() {
  const saved = load();
  state.date = saved.date || new Date().toISOString().slice(0, 10);

  try {
    const { sites } = await api.sites();
    state.sites = sites;
  } catch (e) {
    console.error("failed to load sites", e);
    state.sites = [];
  }

  if (saved.site) {
    state.site = saved.site;
  } else if (state.sites.length > 0) {
    state.site = state.sites[0];
  } else {
    // Default to Greenwich until user provides a site
    state.site = { name: "Default (Greenwich)", lat: 51.4769, lon: 0.0005 };
  }
  notify();
}

export async function refreshSites() {
  const { sites } = await api.sites();
  state.sites = sites;
  notify();
}
