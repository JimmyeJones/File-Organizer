/**
 * Interactive all-sky renderer.
 *
 * Projection: zenithal equidistant (azimuthal equidistant from zenith).
 *   r = (90 - alt_deg) / 90 * RADIUS   (horizon at edge, zenith at center)
 *   x = r * sin(az_rad), y = -r * cos(az_rad)   (North = up)
 *
 * Coordinate systems:
 *   Equatorial (RA/Dec, J2000) → local sidereal time → Hour Angle → Alt/Az
 */

import { NAMED_STARS, CONSTELLATION_LINES, GALACTIC_EQUATOR, GALACTIC_CENTER } from "./starcatalog.js";
import { api } from "./api.js";
import { state } from "./state.js";
import { fmtTime } from "./util.js";

// ─── Math helpers ────────────────────────────────────────────────────────────
const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

function lst(lon_deg, datetime_utc) {
  // Julian date
  const JD = datetime_utc / 86400000 + 2440587.5;
  const T = (JD - 2451545.0) / 36525;
  let gmst = 280.46061837 + 360.98564736629 * (JD - 2451545) +
             0.000387933 * T * T - T * T * T / 38710000;
  gmst = ((gmst % 360) + 360) % 360;
  return ((gmst + lon_deg) % 360 + 360) % 360;  // degrees
}

function altAz(ra_deg, dec_deg, lat_deg, lon_deg, date) {
  const lha = ((lst(lon_deg, date) - ra_deg) % 360 + 360) % 360;  // local hour angle
  const h = lha * D2R;
  const d = dec_deg * D2R;
  const l = lat_deg * D2R;
  const sinAlt = Math.sin(d) * Math.sin(l) + Math.cos(d) * Math.cos(l) * Math.cos(h);
  const alt = Math.asin(Math.max(-1, Math.min(1, sinAlt))) * R2D;
  const cosAz = (Math.sin(d) - Math.sin(alt * D2R) * Math.sin(l)) /
                (Math.cos(alt * D2R) * Math.cos(l));
  let az = Math.acos(Math.max(-1, Math.min(1, cosAz))) * R2D;
  if (Math.sin(h) > 0) az = 360 - az;
  return { alt, az };
}

function project(alt_deg, az_deg, R) {
  if (alt_deg < -1) return null;   // below horizon
  const r = ((90 - alt_deg) / 90) * R;
  const rad = az_deg * D2R;
  return { x: r * Math.sin(rad), y: -r * Math.cos(rad) };
}

function magToRadius(mag) {
  // Visual radius in canvas pixels. Bright stars are larger.
  return Math.max(0.5, 4.5 - mag * 0.7);
}

function bvToColor(bv) {
  // Map BV color index to RGB string
  if (bv === undefined || bv === null) return "#ffe4b5";
  if (bv < -0.3) return "#cce0ff";
  if (bv < 0.0)  return "#ddeeff";
  if (bv < 0.3)  return "#ffffff";
  if (bv < 0.6)  return "#fff5e0";
  if (bv < 1.0)  return "#ffdd99";
  if (bv < 1.5)  return "#ffaa66";
  return "#ff7744";
}

function pseudoRand(seed) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

// ─── Sky view state ───────────────────────────────────────────────────────────
let canvas, ctx;
let R = 0;           // sky circle radius
let CX, CY;          // canvas center
let times = [];      // array of Date objects for slider
let sliderIdx = 0;
let playTimer = null;
let planetTracks = {};
let dsoTracks = [];
let bgStars = [];    // procedurally generated faint stars
let hoveredObj = null;
let clickedObj = null;
let opts = {
  showStars: true,
  showMilkyWay: true,
  showConstellations: true,
  showDso: true,
  showPlanets: true,
  showLabels: true,
};

// ─── Procedural background star field ────────────────────────────────────────
function generateBgStars(count = 3500) {
  const rand = pseudoRand(42);
  const stars = [];
  // Named stars cover mag < ~4.5. Background: mag 4.5 to 8.5
  for (let i = 0; i < count; i++) {
    const ra = rand() * 360;
    // Weight toward galactic plane: sample dec with galactic bias
    // Galactic plane max density near dec ≈ -10° to -60° in RA 270° region
    let dec = (rand() * 2 - 1);  // -1..1
    dec = Math.asin(dec) * R2D;  // -90..90, equidistant on sphere

    // Add extra clustering near galactic plane (rough: center RA=266, dec=-29)
    // Perturb some stars toward galactic band
    if (rand() < 0.45) {
      // Pull toward galactic center direction with spread
      const gRa = 266 + (rand() - 0.5) * 180;
      const gDec = -29 + (rand() - 0.5) * 60;
      dec = dec * 0.3 + gDec * 0.7 + (rand() - 0.5) * 40;
      stars.push({
        ra: ra * 0.3 + gRa * 0.7 + (rand() - 0.5) * 60,
        dec: Math.max(-90, Math.min(90, dec)),
        mag: 5.5 + rand() * 3.0,
        bv: (rand() - 0.2) * 1.5,
      });
    } else {
      stars.push({
        ra,
        dec: Math.max(-90, Math.min(90, dec)),
        mag: 5.0 + rand() * 3.5,
        bv: (rand() - 0.1) * 1.2,
      });
    }
  }
  return stars;
}

// ─── Drawing functions ────────────────────────────────────────────────────────
function drawBackground() {
  const grad = ctx.createRadialGradient(CX, CY, 0, CX, CY, R * 1.05);
  grad.addColorStop(0, "#0a0a1e");
  grad.addColorStop(0.5, "#06060f");
  grad.addColorStop(1, "#000005");
  ctx.fillStyle = grad;
  ctx.beginPath();
  ctx.arc(CX, CY, R, 0, 2 * Math.PI);
  ctx.fill();
}

function drawHorizon() {
  // Horizon ring
  ctx.beginPath();
  ctx.arc(CX, CY, R, 0, 2 * Math.PI);
  ctx.strokeStyle = "rgba(100,100,150,0.6)";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Cardinal directions
  const dirs = [["N", 0], ["E", 90], ["S", 180], ["W", 270]];
  ctx.font = `bold ${Math.round(R * 0.045)}px monospace`;
  ctx.fillStyle = "rgba(150,150,200,0.7)";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (const [label, az] of dirs) {
    const pt = project(0, az, R);
    if (pt) {
      ctx.fillText(label, CX + pt.x * 1.06, CY + pt.y * 1.06);
    }
  }

  // Altitude circles at 30° and 60°
  for (const alt of [30, 60]) {
    const r = ((90 - alt) / 90) * R;
    ctx.beginPath();
    ctx.arc(CX, CY, r, 0, 2 * Math.PI);
    ctx.strokeStyle = "rgba(80,80,120,0.2)";
    ctx.lineWidth = 0.8;
    ctx.stroke();
  }
  // Zenith dot
  ctx.beginPath();
  ctx.arc(CX, CY, 2, 0, 2 * Math.PI);
  ctx.fillStyle = "rgba(150,150,200,0.4)";
  ctx.fill();
}

function drawMilkyWay(date) {
  if (!opts.showMilkyWay) return;
  const { lat, lon } = state.site;
  const width = 18;   // galactic band width in degrees
  const offsets = [-width, -width / 2, 0, width / 2, width];

  // Bright core zone: l=300..60 (central bulge)
  ctx.save();
  ctx.globalAlpha = 0.18;
  for (const bOffset of offsets) {
    const pts = [];
    for (const [ra, dec] of GALACTIC_EQUATOR) {
      // Offset in declination (crude but visually effective)
      const d = dec + bOffset * 0.8;
      const { alt, az } = altAz(ra, d, lat, lon, date);
      const p = project(alt, az, R);
      if (p) pts.push(p);
    }
    if (pts.length < 3) continue;
    ctx.beginPath();
    ctx.moveTo(CX + pts[0].x, CY + pts[0].y);
    for (let i = 1; i < pts.length; i++) {
      // Detect discontinuities (wrap-around) and break path
      const dx = pts[i].x - pts[i - 1].x;
      const dy = pts[i].y - pts[i - 1].y;
      if (Math.hypot(dx, dy) > R * 0.25) {
        ctx.moveTo(CX + pts[i].x, CY + pts[i].y);
      } else {
        ctx.lineTo(CX + pts[i].x, CY + pts[i].y);
      }
    }
    ctx.strokeStyle = "#b0c8ff";
    ctx.lineWidth = R * 0.06;
    ctx.lineCap = "round";
    ctx.stroke();
  }

  // Galactic core glow
  const gcPos = altAz(GALACTIC_CENTER[0], GALACTIC_CENTER[1], lat, lon, date);
  const gcPt = project(gcPos.alt, gcPos.az, R);
  if (gcPt) {
    const gcx = CX + gcPt.x;
    const gcy = CY + gcPt.y;
    const glow = ctx.createRadialGradient(gcx, gcy, 0, gcx, gcy, R * 0.28);
    glow.addColorStop(0, "rgba(255,210,120,0.35)");
    glow.addColorStop(0.4, "rgba(200,160,100,0.15)");
    glow.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(gcx, gcy, R * 0.28, 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.restore();
}

function drawConstellations(date) {
  if (!opts.showConstellations) return;
  const { lat, lon } = state.site;
  ctx.save();
  ctx.strokeStyle = "rgba(100,130,200,0.28)";
  ctx.lineWidth = 0.8;
  ctx.setLineDash([3, 5]);
  for (const [[ra1, dec1], [ra2, dec2]] of CONSTELLATION_LINES) {
    const r1 = altAz(ra1, dec1, lat, lon, date);
    const r2 = altAz(ra2, dec2, lat, lon, date);
    const p1 = project(r1.alt, r1.az, R);
    const p2 = project(r2.alt, r2.az, R);
    if (!p1 || !p2) continue;
    const dx = p1.x - p2.x, dy = p1.y - p2.y;
    if (Math.hypot(dx, dy) > R * 0.6) continue; // skip wrap-around lines
    ctx.beginPath();
    ctx.moveTo(CX + p1.x, CY + p1.y);
    ctx.lineTo(CX + p2.x, CY + p2.y);
    ctx.stroke();
  }
  ctx.setLineDash([]);
  ctx.restore();
}

function drawStar(x, y, mag, bv, alpha = 1) {
  const r = magToRadius(mag);
  const color = bvToColor(bv);

  // Halo for bright stars
  if (mag < 2) {
    const haloR = r * (2.5 - mag * 0.4);
    const grad = ctx.createRadialGradient(x, y, 0, x, y, haloR);
    grad.addColorStop(0, color + "cc");
    grad.addColorStop(0.3, color + "44");
    grad.addColorStop(1, "transparent");
    ctx.globalAlpha = alpha * 0.5;
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(x, y, haloR, 0, 2 * Math.PI);
    ctx.fill();
  }
  // Diffraction spikes for very bright stars
  if (mag < 0.5) {
    ctx.save();
    ctx.globalAlpha = alpha * 0.3;
    ctx.strokeStyle = color;
    ctx.lineWidth = 0.5;
    const spikeLen = r * 5;
    for (const ang of [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2]) {
      ctx.beginPath();
      ctx.moveTo(x + Math.cos(ang) * r, y + Math.sin(ang) * r);
      ctx.lineTo(x + Math.cos(ang) * spikeLen, y + Math.sin(ang) * spikeLen);
      ctx.stroke();
    }
    ctx.restore();
  }

  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.arc(x, y, Math.max(0.5, r), 0, 2 * Math.PI);
  ctx.fill();
  ctx.globalAlpha = 1;
}

function drawBgStars(date) {
  if (!opts.showStars) return;
  const { lat, lon } = state.site;
  for (const s of bgStars) {
    const { alt, az } = altAz(s.ra, s.dec, lat, lon, date);
    const p = project(alt, az, R);
    if (!p) continue;
    const alpha = alt < 5 ? Math.max(0, alt / 5) : 1;
    drawStar(CX + p.x, CY + p.y, s.mag, s.bv, alpha * 0.6);
  }
}

function drawNamedStars(date) {
  if (!opts.showStars) return;
  const { lat, lon } = state.site;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const labelFont = `${Math.round(R * 0.03)}px sans-serif`;

  for (const [name, ra, dec, mag, bv] of NAMED_STARS) {
    const { alt, az } = altAz(ra, dec, lat, lon, date);
    const p = project(alt, az, R);
    if (!p) continue;
    const alpha = alt < 5 ? Math.max(0, alt / 5) : 1;
    const sx = CX + p.x, sy = CY + p.y;
    drawStar(sx, sy, mag, bv, alpha);
    if (opts.showLabels && mag < 1.5 && alpha > 0.5) {
      ctx.font = labelFont;
      ctx.fillStyle = `rgba(200,200,230,${alpha * 0.75})`;
      ctx.fillText(name, sx + magToRadius(mag) + 3, sy);
    }
  }
}

function drawDSOs(date) {
  if (!opts.showDso || !dsoTracks.length) return;
  const { lat, lon } = state.site;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const labelFont = `${Math.round(R * 0.028)}px sans-serif`;
  const labelFontSmall = `${Math.round(R * 0.024)}px sans-serif`;

  for (const dso of dsoTracks) {
    let alt, az;
    if (dso.curve && dso.curve[sliderIdx]) {
      ({ alt, az } = dso.curve[sliderIdx]);
    } else {
      const pos = altAz(dso.ra * 15, dso.dec, lat, lon, date);
      alt = pos.alt; az = pos.az;
    }
    const p = project(alt, az, R);
    if (!p) continue;
    const alpha = alt < 5 ? Math.max(0, alt / 5) : 1;
    const x = CX + p.x, y = CY + p.y;
    ctx.globalAlpha = alpha;
    drawDSOSymbol(x, y, dso.type, dso.mag, dso.size);
    if (opts.showLabels && dso.mag < 7 && alpha > 0.5) {
      ctx.font = dso.mag < 6 ? labelFont : labelFontSmall;
      ctx.fillStyle = `rgba(160,220,160,${alpha * 0.8})`;
      ctx.fillText(dso.id, x + 7, y);
    }
    ctx.globalAlpha = 1;
  }
}

function drawDSOSymbol(x, y, type, mag, size) {
  const baseR = Math.max(3, Math.min(10, 8 - mag * 0.5));
  ctx.lineWidth = 1;
  if (type === "Galaxy") {
    ctx.strokeStyle = "#dd88ff";
    ctx.fillStyle = "rgba(180,80,255,0.12)";
    ctx.beginPath();
    ctx.ellipse(x, y, baseR, baseR * 0.45, Math.PI * 0.3, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
  } else if (type === "Globular Cluster") {
    ctx.strokeStyle = "#88ddff";
    ctx.fillStyle = "rgba(80,180,255,0.1)";
    ctx.beginPath();
    ctx.arc(x, y, baseR, 0, 2 * Math.PI);
    ctx.fill();
    ctx.stroke();
    // cross hairs
    ctx.beginPath();
    ctx.moveTo(x - baseR, y); ctx.lineTo(x + baseR, y);
    ctx.moveTo(x, y - baseR); ctx.lineTo(x, y + baseR);
    ctx.stroke();
  } else if (type === "Open Cluster") {
    ctx.strokeStyle = "#ffdd88";
    ctx.beginPath();
    ctx.arc(x, y, baseR, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.setLineDash([2, 2]);
    ctx.stroke();
    ctx.setLineDash([]);
  } else if (type.includes("Nebula") || type === "Supernova Remnant" || type === "Star Cloud") {
    ctx.strokeStyle = "#88ffaa";
    ctx.fillStyle = "rgba(80,255,120,0.08)";
    ctx.beginPath();
    ctx.rect(x - baseR, y - baseR * 0.6, baseR * 2, baseR * 1.2);
    ctx.fill();
    ctx.stroke();
  } else {
    ctx.fillStyle = "rgba(200,200,200,0.3)";
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, 2 * Math.PI);
    ctx.fill();
  }
}

function drawPlanets(date) {
  if (!opts.showPlanets || !Object.keys(planetTracks).length) return;
  const { lat, lon } = state.site;
  const PLANET_COLORS = {
    Mercury: "#aaaaaa", Venus: "#ffffa0", Mars: "#ff6644",
    Jupiter: "#ffddaa", Saturn: "#eeddaa", Uranus: "#aaffff", Neptune: "#7799ff",
  };
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  const labelFont = `bold ${Math.round(R * 0.034)}px sans-serif`;

  for (const [name, track] of Object.entries(planetTracks)) {
    const entry = track[Math.min(sliderIdx, track.length - 1)];
    if (!entry) continue;
    const p = project(entry.alt, entry.az, R);
    if (!p) continue;
    const alpha = entry.alt < 5 ? Math.max(0, entry.alt / 5) : 1;
    const x = CX + p.x, y = CY + p.y;
    const color = PLANET_COLORS[name] || "#ffffff";

    ctx.save();
    ctx.globalAlpha = alpha;

    // Planet disc
    const pR = name === "Jupiter" ? 7 : name === "Venus" ? 6 : name === "Saturn" ? 6 : 5;
    const glow = ctx.createRadialGradient(x, y, 0, x, y, pR * 2.5);
    glow.addColorStop(0, color);
    glow.addColorStop(0.4, color + "88");
    glow.addColorStop(1, "transparent");
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(x, y, pR * 2.5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, pR, 0, 2 * Math.PI);
    ctx.fill();

    // Saturn rings
    if (name === "Saturn") {
      ctx.strokeStyle = "rgba(200,180,120,0.7)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.ellipse(x, y, pR * 2, pR * 0.6, Math.PI * 0.2, 0, 2 * Math.PI);
      ctx.stroke();
    }

    if (opts.showLabels && alpha > 0.5) {
      ctx.font = labelFont;
      ctx.fillStyle = color;
      ctx.fillText(name, x + pR + 4, y);
    }
    ctx.restore();
  }
}

function drawObjectHover() {
  if (!hoveredObj) return;
  const { x, y, label, type } = hoveredObj;
  const pad = 8, lineH = 18;
  const lines = label.split("\n");
  const w = lines.reduce((m, l) => Math.max(m, l.length * 7.2), 0) + pad * 2;
  const h = lines.length * lineH + pad * 2;

  let bx = x + 14, by = y - 10;
  if (bx + w > CX * 2 - 10) bx = x - w - 14;
  if (by + h > CY * 2 - 10) by = CY * 2 - h - 10;

  ctx.save();
  ctx.fillStyle = "rgba(10,10,25,0.92)";
  ctx.strokeStyle = "rgba(150,150,255,0.5)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  const r4 = 4;
  ctx.moveTo(bx + r4, by);
  ctx.lineTo(bx + w - r4, by); ctx.arcTo(bx + w, by, bx + w, by + r4, r4);
  ctx.lineTo(bx + w, by + h - r4); ctx.arcTo(bx + w, by + h, bx + w - r4, by + h, r4);
  ctx.lineTo(bx + r4, by + h); ctx.arcTo(bx, by + h, bx, by + h - r4, r4);
  ctx.lineTo(bx, by + r4); ctx.arcTo(bx, by, bx + r4, by, r4);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.font = "12px monospace";
  ctx.fillStyle = "#d8d8e8";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  lines.forEach((ln, i) => ctx.fillText(ln, bx + pad, by + pad + i * lineH));
  ctx.restore();
}

function render(date) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawBackground();
  drawMilkyWay(date);
  drawConstellations(date);
  drawBgStars(date);
  drawNamedStars(date);
  drawDSOs(date);
  drawPlanets(date);
  drawHorizon();
  drawObjectHover();
}

// ─── Hit testing ─────────────────────────────────────────────────────────────
function findObjectAt(mx, my, date) {
  const { lat, lon } = state.site;
  // Planets
  for (const [name, track] of Object.entries(planetTracks)) {
    const entry = track[Math.min(sliderIdx, track.length - 1)];
    if (!entry) continue;
    const p = project(entry.alt, entry.az, R);
    if (!p) continue;
    if (Math.hypot(mx - (CX + p.x), my - (CY + p.y)) < 14) {
      return {
        x: CX + p.x, y: CY + p.y,
        label: `${name}\nAlt: ${entry.alt.toFixed(1)}°  Az: ${entry.az.toFixed(1)}°`,
        type: "planet",
      };
    }
  }
  // DSOs
  for (const dso of dsoTracks) {
    let alt, az;
    if (dso.curve && dso.curve[sliderIdx]) {
      ({ alt, az } = dso.curve[sliderIdx]);
    } else {
      const pos = altAz(dso.ra * 15, dso.dec, lat, lon, date);
      alt = pos.alt; az = pos.az;
    }
    const p = project(alt, az, R);
    if (!p) continue;
    if (Math.hypot(mx - (CX + p.x), my - (CY + p.y)) < 10) {
      return {
        x: CX + p.x, y: CY + p.y,
        label: `${dso.id} – ${dso.name}\n${dso.type}  mag ${dso.mag}  ${dso.size}'\nAlt: ${alt.toFixed(1)}°  Az: ${az.toFixed(1)}°`,
        type: "dso",
      };
    }
  }
  // Named stars
  for (const [name, ra, dec, mag, bv] of NAMED_STARS) {
    if (mag > 3) continue; // only check bright named stars
    const { alt, az } = altAz(ra, dec, lat, lon, date);
    const p = project(alt, az, R);
    if (!p) continue;
    if (Math.hypot(mx - (CX + p.x), my - (CY + p.y)) < 10) {
      return {
        x: CX + p.x, y: CY + p.y,
        label: `${name}\nmag ${mag}  B-V ${bv}\nAlt: ${alt.toFixed(1)}°  Az: ${az.toFixed(1)}°`,
        type: "star",
      };
    }
  }
  return null;
}

// ─── Resize ───────────────────────────────────────────────────────────────────
function resize() {
  const wrap = canvas.parentElement;
  const size = Math.min(wrap.offsetWidth, window.innerHeight * 0.75);
  canvas.width = size;
  canvas.height = size;
  R = size * 0.46;
  CX = size / 2;
  CY = size / 2;
}

// ─── Public init ──────────────────────────────────────────────────────────────
export async function renderSkyMap() {
  if (!canvas) initCanvas();
  if (!bgStars.length) bgStars = generateBgStars();

  const { site, date } = state;
  document.getElementById("skymap-time-label").textContent = "Loading…";

  // Fetch tracks from backend (planet positions + DSO alt/az curves)
  try {
    const [ptRes, dsoRes] = await Promise.all([
      api.planetTrack(site.lat, site.lon, date),
      api.dsoTrack(site.lat, site.lon, date),
    ]);

    // Build time axis from planet track (consistent steps)
    times = ptRes.times.map(t => new Date(t));
    planetTracks = {};
    for (const [name, track] of Object.entries(ptRes.planet_tracks)) {
      planetTracks[name] = track;
    }
    dsoTracks = dsoRes.dso_tracks || [];

    // Set up slider
    const slider = document.getElementById("skymap-slider");
    slider.max = Math.max(0, times.length - 1);
    slider.value = 0;
    sliderIdx = 0;

    // Label start/end
    document.getElementById("slider-start").textContent =
      times.length ? fmtTime(times[0].toISOString()) : "—";
    document.getElementById("slider-end").textContent =
      times.length ? fmtTime(times[times.length - 1].toISOString()) : "—";
  } catch (e) {
    console.error("Sky map data error", e);
    // Fall back: build times from sunset→sunrise using local math
    const now = new Date();
    times = [];
    for (let i = 0; i <= 48; i++) {
      times.push(new Date(now.getTime() + i * 20 * 60000));
    }
    sliderIdx = 0;
  }

  renderFrame();
}

function initCanvas() {
  canvas = document.getElementById("skymap-canvas");
  ctx = canvas.getContext("2d");
  resize();
  window.addEventListener("resize", () => { resize(); renderFrame(); });

  // Slider
  document.getElementById("skymap-slider").addEventListener("input", (e) => {
    sliderIdx = parseInt(e.target.value);
    renderFrame();
  });

  // Play/pause
  document.getElementById("sky-btn-play").addEventListener("click", () => {
    if (playTimer) {
      clearInterval(playTimer);
      playTimer = null;
      document.getElementById("sky-btn-play").textContent = "▶ Play";
    } else {
      document.getElementById("sky-btn-play").textContent = "⏸ Pause";
      playTimer = setInterval(() => {
        sliderIdx = (sliderIdx + 1) % Math.max(1, times.length);
        document.getElementById("skymap-slider").value = sliderIdx;
        renderFrame();
      }, 80);
    }
  });

  // Reset
  document.getElementById("sky-btn-reset").addEventListener("click", () => {
    sliderIdx = 0;
    document.getElementById("skymap-slider").value = 0;
    renderFrame();
  });

  // Toggle checkboxes
  for (const [id, key] of [
    ["sky-show-stars", "showStars"],
    ["sky-show-milkyway", "showMilkyWay"],
    ["sky-show-constellations", "showConstellations"],
    ["sky-show-dso", "showDso"],
    ["sky-show-planets", "showPlanets"],
    ["sky-show-labels", "showLabels"],
  ]) {
    document.getElementById(id).addEventListener("change", (e) => {
      opts[key] = e.target.checked;
      renderFrame();
    });
  }

  // Hover
  canvas.addEventListener("mousemove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const mx = (e.clientX - rect.left) * (canvas.width / rect.width);
    const my = (e.clientY - rect.top) * (canvas.height / rect.height);
    const date = times[sliderIdx] || new Date();
    const obj = findObjectAt(mx, my, date);
    if (obj !== hoveredObj) {
      hoveredObj = obj;
      canvas.style.cursor = obj ? "pointer" : "default";
      renderFrame();
    }
    document.getElementById("skymap-hover-info").textContent =
      obj ? obj.label.split("\n")[0] : "";
  });

  canvas.addEventListener("mouseleave", () => {
    hoveredObj = null;
    document.getElementById("skymap-hover-info").textContent = "";
    renderFrame();
  });
}

function renderFrame() {
  const date = times[sliderIdx] || new Date();
  document.getElementById("skymap-time-label").textContent = fmtTime(date.toISOString());
  render(date);
}
