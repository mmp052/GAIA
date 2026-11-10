const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const state = {
  booted: false,
  screen: 'home',
  resumo: null,
  emailIndex: 0,
  buscaExecutando: false,
  historicoIniciado: false,
  monitorTimer: null,
  buscaTimer: null,
  historicoTimer: null,
  pendingToastShown: false,
};

function api() {
  if (!window.pywebview?.api) throw new Error('A ponte com o Python ainda não está pronta.');
  return window.pywebview.api;
}

function escapeText(value) { return String(value ?? ''); }
function formatNumber(value, suffix = '') { return `${Number(value || 0).toFixed(1)}${suffix}`; }
function screenEl(name) { return $(`[data-screen="${name}"]`); }

function showScreen(name) {
  state.screen = name;
  $$('.screen').forEach((screen) => screen.classList.toggle('is-active', screen.dataset.screen === name));
  if (name === 'historico' && !state.historicoIniciado) loadHistorico();
  if (name === 'resumidor') refreshBuscaState();
}

function toast(message, title = 'GAIA') {
  const item = document.createElement('div');
  item.className = 'toast';
  const heading = document.createElement('strong');
  heading.textContent = title;
  const body = document.createElement('div');
  body.textContent = message;
  item.append(heading, body);
  $('#toast-region').append(item);
  window.setTimeout(() => item.remove(), 5200);
}

function updateClock() {
  $('#clock').textContent = new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function thresholdClass(threshold) {
  return threshold === 'red' ? 'crit' : threshold === 'yellow' ? 'warn' : 'ok';
}

function drawLineChart(canvas, values, color) {
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(80, Math.floor(rect.width * ratio));
  const height = Math.max(40, Math.floor(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  const data = Array.isArray(values) ? values.map(Number).filter(Number.isFinite) : [];
  if (!data.length) return;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = Math.max(max - min, 1);
  const padX = Math.max(8, width * .02);
  const padY = Math.max(7, height * .18);
  const plotWidth = width - padX * 2;
  const plotHeight = height - padY * 2;
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2.2, ratio * 1.7);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  data.forEach((value, index) => {
    const x = data.length === 1 ? width / 2 : padX + (index / (data.length - 1)) * plotWidth;
    const normalized = (value - min) / span;
    const y = padY + (1 - normalized) * plotHeight;
    if (index === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function chartTimeLabel(label) {
  const text = String(label || '—');
  const match = text.match(/\d{2}:\d{2}/);
  return match ? match[0] : text;
}

function drawHistoricoChart(canvas, values, labels, color, hoverIndex = null) {
  if (!canvas) return;
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(260, Math.floor(rect.width * ratio));
  const height = Math.max(140, Math.floor(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);
  const rawValues = Array.isArray(values) ? values.map(Number).filter(Number.isFinite) : [];
  const data = rawValues.length ? rawValues : [0, 0];
  const tickLabels = Array.isArray(labels) && labels.length === data.length ? labels.map(chartTimeLabel) : data.map((_, index) => String(index));
  const rawMax = Math.max(...data);
  const maximum = Math.min(100, Math.max(10, Math.ceil(rawMax / 10) * 10));
  const plotLeft = Math.round(38 * ratio);
  const plotRight = width - Math.round(10 * ratio);
  const plotTop = Math.round(12 * ratio);
  const plotBottom = height - Math.round(28 * ratio);

  ctx.font = `${Math.round(11 * ratio)}px ui-monospace, SFMono-Regular, Menlo, monospace`;
  ctx.textBaseline = 'middle';
  ctx.lineWidth = Math.max(1.4, ratio);

  // Grade pontilhada horizontal para orientação do eixo Y.
  ctx.save();
  ctx.strokeStyle = 'rgba(148, 163, 184, .28)';
  ctx.setLineDash([Math.max(3, 3 * ratio), Math.max(3, 3 * ratio)]);
  [0, .5, 1].forEach((fraction) => {
    const y = plotBottom - fraction * (plotBottom - plotTop);
    ctx.beginPath();
    ctx.moveTo(plotLeft, y);
    ctx.lineTo(plotRight, y);
    ctx.stroke();
  });
  ctx.restore();

  // Eixos X e Y.
  ctx.strokeStyle = 'rgba(215, 230, 255, .48)';
  ctx.beginPath();
  ctx.moveTo(plotLeft, plotTop);
  ctx.lineTo(plotLeft, plotBottom);
  ctx.lineTo(plotRight, plotBottom);
  ctx.stroke();

  // Ticks do eixo Y.
  ctx.fillStyle = '#8b9dc3';
  [0, .5, 1].forEach((fraction) => {
    const y = plotBottom - fraction * (plotBottom - plotTop);
    const label = `${Math.round(maximum * fraction)}%`;
    ctx.textAlign = 'right';
    ctx.fillText(label, plotLeft - Math.round(7 * ratio), y);
  });

  const points = data.map((value, index) => {
    const x = data.length === 1 ? (plotLeft + plotRight) / 2 : plotLeft + (index / (data.length - 1)) * (plotRight - plotLeft);
    const y = plotBottom - (Math.max(0, Math.min(maximum, value)) / maximum) * (plotBottom - plotTop);
    return { x, y, value, label: tickLabels[index] };
  });

  // Ticks do eixo X: início, meio e fim.
  ctx.fillStyle = '#8b9dc3';
  const xIndexes = [...new Set([0, Math.floor((points.length - 1) / 2), points.length - 1])];
  xIndexes.forEach((index) => {
    const point = points[index];
    ctx.textAlign = index === 0 ? 'left' : index === points.length - 1 ? 'right' : 'center';
    ctx.fillText(point.label, point.x, plotBottom + Math.round(15 * ratio));
  });

  // Linha suave (Catmull-Rom convertida para Bézier).
  ctx.strokeStyle = color;
  ctx.lineWidth = Math.max(2.4, 1.8 * ratio);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[Math.max(0, index - 1)];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[Math.min(points.length - 1, index + 2)];
    const cp1x = p1.x + (p2.x - p0.x) / 6;
    const cp1y = p1.y + (p2.y - p0.y) / 6;
    const cp2x = p2.x - (p3.x - p1.x) / 6;
    const cp2y = p2.y - (p3.y - p1.y) / 6;
    ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2.x, p2.y);
  }
  ctx.stroke();

  if (hoverIndex !== null && points[hoverIndex]) {
    const point = points[hoverIndex];
    ctx.save();
    ctx.fillStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 12 * ratio;
    ctx.beginPath();
    ctx.arc(point.x, point.y, Math.max(4, 3.3 * ratio), 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  canvas._chartData = { points: points.map((point) => ({ ...point, xCss: point.x / ratio, yCss: point.y / ratio })) };
}

function attachChartHover(canvas, tooltip) {
  if (!canvas || !tooltip) return;
  canvas.addEventListener('mousemove', (event) => {
    const data = canvas._chartData;
    if (!data?.points?.length) {
      tooltip.hidden = true;
      return;
    }
    const mouseX = event.offsetX;
    const index = data.points.reduce((nearest, point, pointIndex) => (
      Math.abs(point.xCss - mouseX) < Math.abs(data.points[nearest].xCss - mouseX) ? pointIndex : nearest
    ), 0);
    const dataPoint = data.points[index];
    const color = canvas.id.includes('ram') ? '#f59e0b' : '#38bdf8';
    drawHistoricoChart(canvas, data.points.map((point) => point.value), data.points.map((point) => point.label), color, index);
    tooltip.textContent = `${dataPoint.label} · ${Number(dataPoint.value || 0).toFixed(1)}%`;
    tooltip.style.left = `${dataPoint.xCss}px`;
    tooltip.style.top = `${dataPoint.yCss}px`;
    tooltip.hidden = false;
  });
  canvas.addEventListener('mouseleave', () => {
    tooltip.hidden = true;
    const data = canvas._chartData;
    const color = canvas.id.includes('ram') ? '#f59e0b' : '#38bdf8';
    if (data?.points?.length) drawHistoricoChart(canvas, data.points.map((point) => point.value), data.points.map((point) => point.label), color, null);
  });
}

// ---------- Holograma GAIA (frames Arcade + envelope sonoro sempre ativo) ----------
let orbViewRect = null;
// Os frames 3D (esfera de energia roxa) são renderizados offline com a biblioteca
// Arcade pelo tools/gerar_esfera_gaia.py em assets/orb/. O envelope do MP3
// (window.GAIA_ENVELOPE, offline, sem tocar áudio) modula escala/brilho em runtime —
// sempre ligado, sem botão de play.
const ORB_FRAME_COUNT = 120;
const ORB_FRAMES_PER_SEC = 30;
const ORB_FRAME_IMAGES = Array.from({ length: ORB_FRAME_COUNT }, (_, index) => {
  const image = new Image();
  image.src = `assets/orb/frame_${String(index).padStart(3, '0')}.webp`;
  return image;
});

const ENVELOPE = (typeof window !== 'undefined' && window.GAIA_ENVELOPE && Array.isArray(window.GAIA_ENVELOPE.frames)) ? window.GAIA_ENVELOPE : null;

const orbRuntime = {
  rafId: null,
  smoothed: { rms: 0.32, graves: 0.3, medios: 0.32, agudos: 0.3 },
};

function envelopeSample(positionSeconds) {
  if (!ENVELOPE) return null;
  const fps = ENVELOPE.fps || 10;
  const frames = ENVELOPE.frames;
  const wrapped = ((positionSeconds % ENVELOPE.duracao_s) + ENVELOPE.duracao_s) % ENVELOPE.duracao_s;
  const raw = wrapped * fps;
  const index = Math.floor(raw) % frames.length;
  const next = (index + 1) % frames.length;
  const frac = raw - Math.floor(raw);
  const a = frames[index];
  const b = frames[next];
  return {
    rms: a[0] + (b[0] - a[0]) * frac,
    graves: a[1] + (b[1] - a[1]) * frac,
    medios: a[2] + (b[2] - a[2]) * frac,
    agudos: a[3] + (b[3] - a[3]) * frac,
  };
}

function orbAudioLevels(now) {
  // Sempre ligado: a faixa inteira toca como "tema" desde o boot e em loop.
  const sample = envelopeSample(now / 1000);
  if (!sample) {
    return {
      rms: 0.3 + 0.08 * Math.sin(now / 2600),
      graves: 0.26 + 0.1 * Math.sin(now / 3400 + 1.2),
      medios: 0.3 + 0.09 * Math.sin(now / 2100 + 2.4),
      agudos: 0.26 + 0.1 * Math.sin(now / 1700 + 4.0),
    };
  }
  const s = orbRuntime.smoothed;
  // Ataque rápido, liberação lenta.
  for (const key of Object.keys(s)) {
    const value = sample[key];
    s[key] = value > s[key] ? s[key] * 0.42 + value * 0.58 : s[key] * 0.87 + value * 0.13;
  }
  return { ...s };
}

function drawAmbientLight(ctx, centerX, centerY, sphereRadius, levels, energy) {
  // A esfera como sol: o ambiente inteiro é iluminado a partir dela,
  // e a "luz ambiente" infla e escurece junto com o envelope sonoro.
  const radius = sphereRadius * (2.15 + levels.graves * 1.05);
  const alpha = 0.18 + energy * 0.38;
  const gradient = ctx.createRadialGradient(centerX, centerY, sphereRadius * 0.35, centerX, centerY, radius);
  gradient.addColorStop(0, `rgba(139, 92, 246, ${alpha})`);
  gradient.addColorStop(0.55, `rgba(124, 58, 237, ${alpha * 0.45})`);
  gradient.addColorStop(1, 'rgba(124, 58, 237, 0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);
}

// ---------- Planetas das rotinas (orbitam o sol/esfera) ----------
// Cada rotina vira um planetinha glossy com ícone próprio, orbitando a esfera
// como um planeta orbita o sol. Parâmetros procedurais distintos (seed fixa →
// layout estável entre boots, nunca duas órbitas iguais) e volta propositalmente lenta.
const ORBIT_PLANETS = [
  { key: '1', label: 'RESUMIDOR DE EMAILS', icon: 'envelope', target: 'resumidor' },
  { key: '2', label: 'HISTÓRICO', icon: 'chart', target: 'historico' },
];

function mulberry32(seed) {
  return function () {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const ORBIT_SALT = 0x51AB3;
const orbitParams = ORBIT_PLANETS.map((_, index) => {
  const rand = mulberry32(ORBIT_SALT + index * 0x9E3779B1);
  return {
    aFactor: 1.38 + rand() * 0.85, // semi-eixo maior, múltiplo do raio da esfera (limitado pela tela)
    tilt: 0.30 + rand() * 0.16,    // razão eixo menor/maior (elipse)
    phase: rand() * Math.PI * 2,
    period: 92 + rand() * 46,      // segundos por volta — lento o bastante para clicar
  };
});
// Garante órbitas bem distintas (nada de dois planetas com trajetória parecida).
if (Math.abs(orbitParams[0].aFactor - orbitParams[1].aFactor) < 0.2) orbitParams[1].aFactor += 0.22;
if (Math.abs(orbitParams[0].tilt - orbitParams[1].tilt) < 0.05) orbitParams[1].tilt += 0.07;
if (Math.abs(orbitParams[0].phase - orbitParams[1].phase) < 1.1) orbitParams[1].phase += 2.2;

const orbitRuntime = { projected: [] };
let orbHoverIndex = -1;

function leftOrbitLimitCss() {
  const monitor = document.querySelector('.hud-monitor');
  return monitor && window.innerWidth > 760 ? monitor.getBoundingClientRect().right + 16 : 14;
}

function projectOrbitingPlanets(width, height, sphereRadius, now) {
  const cx = width / 2;
  const cy = height / 2;
  const ratio = orbViewRect ? width / orbViewRect.width : 1;
  const leftLimit = leftOrbitLimitCss() * ratio;
  const rightLimit = width - 14 * ratio;
  const aMax = Math.max(sphereRadius * 1.15, Math.min(cx - leftLimit, rightLimit - cx));
  return ORBIT_PLANETS.map((planet, index) => {
    const params = orbitParams[index];
    const a = Math.max(sphereRadius * 1.12, Math.min(sphereRadius * params.aFactor, aMax));
    const b = a * params.tilt;
    const angle = params.phase + (now / 1000 * Math.PI * 2) / params.period;
    const orbitDepth = Math.sin(angle); // >0 vem à frente (baixo), <0 passa atrás
    const scale = 0.66 + 0.34 * ((orbitDepth + 1) / 2);
    return {
      planet,
      orbitDepth,
      x: cx + Math.cos(angle) * a,
      y: cy + orbitDepth * b,
      r: Math.max(14, sphereRadius * 0.155 * scale),
    };
  });
}

function drawPlanetIcon(ctx, icon, x, y, size) {
  ctx.save();
  ctx.strokeStyle = 'rgba(237, 233, 254, .95)';
  ctx.lineWidth = Math.max(1.4, size * 0.16);
  ctx.lineJoin = 'round';
  ctx.lineCap = 'round';
  const s = size;
  if (icon === 'envelope') {
    const w = s * 1.15, h = s * 0.82, rx = s * 0.14;
    ctx.beginPath();
    if (typeof ctx.roundRect === 'function') ctx.roundRect(x - w / 2, y - h / 2, w, h, rx);
    else ctx.rect(x - w / 2, y - h / 2, w, h);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - w / 2 + rx * 0.6, y - h * 0.18);
    ctx.lineTo(x, y + h * 0.16);
    ctx.lineTo(x + w / 2 - rx * 0.6, y - h * 0.18);
    ctx.stroke();
  } else if (icon === 'chart') {
    ctx.beginPath();
    ctx.moveTo(x - s * 0.55, y - s * 0.55);
    ctx.lineTo(x - s * 0.55, y + s * 0.55);
    ctx.lineTo(x + s * 0.6, y + s * 0.55);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - s * 0.32, y + s * 0.3);
    ctx.lineTo(x - s * 0.1, y + s * 0.02);
    ctx.lineTo(x + s * 0.08, y + s * 0.16);
    ctx.lineTo(x + s * 0.22, y - s * 0.2);
    ctx.lineTo(x + s * 0.42, y - s * 0.36);
    ctx.stroke();
  }
  ctx.restore();
}

function drawOrbitingPlanet(ctx, item, hover) {
  const { planet, orbitDepth, x, y, r } = item;
  const behind = orbitDepth < 0;
  ctx.save();
  ctx.globalAlpha = behind ? 0.45 : 1;
  // O planeta é banhado pela luz do sol (a esfera): highlight do lado voltado ao centro.
  const cx = ctx.canvas.width / 2, cy = ctx.canvas.height / 2;
  let dx = cx - x, dy = cy - y;
  const len = Math.hypot(dx, dy) || 1;
  dx /= len; dy /= len;
  const grad = ctx.createRadialGradient(x + dx * r * 0.6, y + dy * r * 0.6, r * 0.12, x, y, r * 1.02);
  grad.addColorStop(0, '#ede9fe');
  grad.addColorStop(0.32, '#a78bfa');
  grad.addColorStop(0.72, '#5b21b6');
  grad.addColorStop(1, '#160b2e');
  ctx.fillStyle = grad;
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
  ctx.lineWidth = behind ? 1 : 1.4;
  ctx.strokeStyle = behind ? 'rgba(167, 139, 250, .45)' : 'rgba(196, 181, 253, .85)';
  ctx.stroke();
  // Ícone da rotina (envelope = Resumidor; gráfico = Histórico)
  drawPlanetIcon(ctx, planet.icon, x, y - r * 0.12, r * 0.52);
  // Badge com a tecla que abre a rotina
  const badge = Math.max(6.5, r * 0.34);
  const badgeX = x + r * 0.74, badgeY = y - r * 0.74;
  ctx.beginPath(); ctx.arc(badgeX, badgeY, badge, 0, Math.PI * 2);
  ctx.fillStyle = 'rgba(11, 16, 32, .92)'; ctx.fill();
  ctx.lineWidth = 1.2; ctx.strokeStyle = 'rgba(167, 139, 250, .8)'; ctx.stroke();
  ctx.fillStyle = '#d7e6ff';
  ctx.font = `700 ${Math.max(9, badge * 1.15)}px Inter, system-ui, sans-serif`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(planet.key, badgeX, badgeY + 0.5);
  // Nome sempre visível sob o planeta
  const labelSize = Math.max(8.5, r * 0.3);
  ctx.font = `800 ${labelSize}px Inter, system-ui, sans-serif`;
  ctx.fillStyle = behind ? 'rgba(215, 230, 255, .5)' : 'rgba(226, 219, 255, .92)';
  ctx.fillText(planet.label, x, y + r + labelSize * 0.9);
  if (hover) {
    ctx.beginPath(); ctx.arc(x, y, r + 5, 0, Math.PI * 2);
    ctx.lineWidth = 1.6;
    ctx.strokeStyle = 'rgba(216, 180, 254, .95)';
    ctx.shadowColor = 'rgba(192, 132, 252, .8)';
    ctx.shadowBlur = 14;
    ctx.stroke();
  }
  ctx.restore();
}

function drawOrbitingPlanets(ctx, front, projected, hoverIndex) {
  projected.forEach((item, index) => {
    const isFront = item.orbitDepth >= 0;
    if (isFront !== front) return;
    drawOrbitingPlanet(ctx, item, index === hoverIndex);
  });
}

function planetIndexAtPoint(cssX, cssY) {
  const canvas = $('#gaia-orb');
  if (!canvas || !orbViewRect) return -1;
  const ratio = canvas.width / orbViewRect.width;
  return orbitRuntime.projected.findIndex((item) => {
    const x = item.x / ratio, y = item.y / ratio, r = item.r / ratio;
    return Math.hypot(cssX - x, cssY - y) <= r + 8;
  });
}

function planetAtPoint(cssX, cssY) {
  const index = planetIndexAtPoint(cssX, cssY);
  return index >= 0 ? ORBIT_PLANETS[index] : null;
}

function drawGaiaOrb(now) {
  const canvas = $('#gaia-orb');
  if (!canvas) return;
  if (!orbViewRect || orbViewRect.width < 40) orbViewRect = canvas.getBoundingClientRect();
  if (orbViewRect.width < 40) return; // home oculta: nada a desenhar
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(240, Math.floor(orbViewRect.width * ratio));
  const height = Math.max(240, Math.floor(orbViewRect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) { canvas.width = width; canvas.height = height; }
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, width, height);

  const levels = orbAudioLevels(now);
  const energy = levels.rms;
  const t = now / 1000;
  const centerX = width / 2;
  const centerY = height / 2;
  const sphereRadius = Math.floor(Math.min(width, height) * 0.235);

  // --- Luz ambiente: a esfera ilumina a tela inteira como um sol ---
  drawAmbientLight(ctx, centerX, centerY, sphereRadius, levels, energy);

  // --- Planetas atrás da esfera (metade de trás da órbita) ---
  const projected = projectOrbitingPlanets(width, height, sphereRadius, now);
  orbitRuntime.projected = projected;
  drawOrbitingPlanets(ctx, false, projected, orbHoverIndex);

  // --- Esfera de energia (frames Arcade) ---
  const frameIndex = Math.floor(t * ORB_FRAMES_PER_SEC) % ORB_FRAME_COUNT;
  const image = ORB_FRAME_IMAGES[frameIndex];
  if (image && image.complete && image.naturalWidth) {
    ctx.save();
    const pulse = 1 + levels.graves * 0.22;
    const drawSize = sphereRadius * 4.26 * pulse; // o quadro Arcade traz a esfera a 0.235 do lado
    ctx.drawImage(image, (width - drawSize) / 2, (height - drawSize) / 2, drawSize, drawSize);
    // Bloom extra no auge dos graves.
    if (energy > 0.55) {
      ctx.globalAlpha = (energy - 0.55) * 0.6;
      const bloom = drawSize * 1.16;
      ctx.drawImage(image, (width - bloom) / 2, (height - bloom) / 2, bloom, bloom);
    }
    ctx.restore();
  } else {
    // Frames ainda carregando: núcleo provisório para nunca ficar vazio.
    const fallback = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, sphereRadius);
    fallback.addColorStop(0, 'rgba(237, 233, 254, .9)');
    fallback.addColorStop(0.4, 'rgba(167, 139, 250, .5)');
    fallback.addColorStop(1, 'rgba(139, 92, 246, 0)');
    ctx.fillStyle = fallback;
    ctx.beginPath();
    ctx.arc(centerX, centerY, sphereRadius, 0, Math.PI * 2);
    ctx.fill();
  }

  // --- Planetas na frente da esfera (metade da frente da órbita) ---
  drawOrbitingPlanets(ctx, true, projected, orbHoverIndex);
}

function orbFrame(now) {
  orbRuntime.rafId = window.requestAnimationFrame(orbFrame);
  if (state.screen !== 'home') return;
  drawGaiaOrb(now);
}

function resizeGaiaOrb() {
  orbViewRect = null; // tela mudou: recalcula tamanho/posição do canvas
  const canvas = $('#gaia-orb');
  if (canvas) canvas.width = 0; // força recomputar no próximo draw
  drawGaiaOrb(performance.now());
}

function startGaiaOrb() {
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reducedMotion) {
    drawGaiaOrb(0); // frame estático, sem loop
    return;
  }
  if (orbRuntime.rafId !== null) return;
  orbRuntime.rafId = window.requestAnimationFrame(orbFrame);
}

async function refreshMonitor() {
  try {
    const data = await api().monitor_estado();
    const cpu = data?.cpu || {};
    const ram = data?.ram || {};
    const gaia = data?.gaia || {};
    const cpuText = $('#monitor-cpu');
    const ramText = $('#monitor-ram');
    cpuText.textContent = `${formatNumber(cpu.valor)}%`;
    ramText.textContent = `${formatNumber(ram.valor)}%`;
    cpuText.className = thresholdClass(cpu.threshold);
    ramText.className = thresholdClass(ram.threshold);
    $('#monitor-gaia-detail').textContent = ` cpu ${formatNumber(gaia.cpu)}% · ram ${Number(gaia.ram_mb || 0).toFixed(0)}MB · ${escapeText(ram.usada || '--')}/${escapeText(ram.total || '--')}`;
    $('#monitor-status').textContent = escapeText(data?.status || 'aviso ≥80 · crítico ≥90');
    drawLineChart($('#chart-cpu'), cpu.historico, cpu.threshold === 'red' ? '#ef4444' : cpu.threshold === 'yellow' ? '#f59e0b' : '#22c55e');
    drawLineChart($('#chart-ram'), ram.historico, ram.threshold === 'red' ? '#ef4444' : ram.threshold === 'yellow' ? '#f59e0b' : '#22c55e');
    const pendente = await api().resumo_pendente();
    if (pendente && !state.pendingToastShown) {
      state.pendingToastShown = true;
      toast('Resumo automático pronto! Abra Resumidor → Ler último resumo.', 'Resumo automático');
    } else if (!pendente) {
      state.pendingToastShown = false;
    }
  } catch (error) {
    console.warn('monitor indisponível', error);
  }
}

function openModal() {
  $('#modal-confirmacao').hidden = false;
  $('#modal-nao').focus();
}

function closeModal() {
  $('#modal-confirmacao').hidden = true;
  $('#buscar-novos').focus();
}

async function iniciarBusca() {
  closeModal();
  const block = $('#busca-estado');
  block.hidden = false;
  $('#busca-status').textContent = 'Buscando não-lidos…';
  $('#busca-detalhe').textContent = 'Conectando ao Gmail';
  $('#resumidor-status').textContent = '';
  try {
    await api().iniciar_busca();
    state.buscaExecutando = true;
    window.clearInterval(state.buscaTimer);
    state.buscaTimer = window.setInterval(refreshBuscaState, 500);
    await refreshBuscaState();
  } catch (error) {
    block.hidden = true;
    $('#resumidor-status').textContent = `Não foi possível iniciar: ${error.message || error}`;
    toast(error.message || String(error), 'Resumidor — erro');
  }
}

async function refreshBuscaState() {
  try {
    const data = await api().busca_estado();
    if (!data) return;
    const block = $('#busca-estado');
    const buscarButton = $('#buscar-novos');
    buscarButton.disabled = Boolean(data.executando);
    $('#busca-status').textContent = escapeText(data.status || 'Buscando…');
    $('#busca-detalhe').textContent = escapeText(data.progresso || 'Processando emails');
    block.hidden = !data.executando;
    if (!data.executando && state.buscaExecutando) {
      state.buscaExecutando = false;
      window.clearInterval(state.buscaTimer);
      const resumidos = Number(data.resultado?.resumidos?.length || 0);
      const message = data.erro ? `Falha: ${data.erro}` : `Concluído — ${resumidos} email(s) resumido(s).`;
      $('#resumidor-status').textContent = message;
      toast(message, data.erro ? 'Resumidor — erro' : 'Resumidor');
      state.resumo = null;
      refreshMonitor();
    }
  } catch (error) {
    console.warn('estado da busca indisponível', error);
  }
}

function senderName(raw) {
  const value = escapeText(raw);
  return value.split('<')[0].trim() || '(sem remetente)';
}

function renderEmailList(resumo) {
  state.resumo = resumo;
  const emails = Array.isArray(resumo?.resumidos) ? resumo.resumidos : [];
  const ignorados = Array.isArray(resumo?.ignorados) ? resumo.ignorados.length : 0;
  const list = $('#email-list');
  list.replaceChildren();
  $('#lista-resumo').textContent = `Resumo ${escapeText(resumo?.dia || '?')} — ${emails.length} email(s) · ${ignorados} ignorado(s)`;
  $('#lista-vazia').hidden = emails.length !== 0;
  emails.forEach((email, index) => {
    const button = document.createElement('button');
    button.className = 'email-item';
    button.dataset.index = String(index);
    const number = document.createElement('span'); number.className = 'email-index'; number.textContent = String(index + 1).padStart(2, '0');
    const content = document.createElement('span');
    const sender = document.createElement('span'); sender.className = 'email-sender'; sender.textContent = senderName(email.de);
    const subject = document.createElement('span'); subject.className = 'email-subject'; subject.textContent = escapeText(email.assunto || '(sem assunto)');
    content.append(sender, subject);
    const arrow = document.createElement('span'); arrow.className = 'email-arrow'; arrow.textContent = '→';
    button.append(number, content, arrow);
    button.addEventListener('click', () => openEmail(index));
    list.append(button);
  });
}

async function abrirLeitura() {
  try {
    const resumo = await api().ler_ultimo_resumo();
    if (!resumo || !Array.isArray(resumo.resumidos) || resumo.resumidos.length === 0) {
      toast('Nenhum resumo salvo ainda. Use “Buscar novos agora”.', 'Resumidor');
      return;
    }
    renderEmailList(resumo);
    showScreen('leitura');
  } catch (error) {
    toast(error.message || String(error), 'Resumidor — erro');
  }
}

function openEmail(index) {
  const emails = state.resumo?.resumidos || [];
  if (!emails.length) return;
  state.emailIndex = Math.max(0, Math.min(Number(index) || 0, emails.length - 1));
  renderEmail();
  showScreen('email');
}

async function ouvirEmailAtual() {
  const email = state.resumo?.resumidos?.[state.emailIndex];
  if (!email) return;
  try { await api().parar_leitura(); await api().ouvir_email(email.de || '', email.assunto || '', email.resumo || ''); } catch (error) { toast(error.message || String(error), 'GAIA — voz'); }
}

async function pararLeitura() {
  try { await api().parar_leitura(); } catch (_) { /* ignora */ }
}

function renderEmail() {
  const emails = state.resumo?.resumidos || [];
  const email = emails[state.emailIndex];
  if (!email) return;
  $('#email-contador').textContent = `${state.emailIndex + 1} de ${emails.length}`;
  $('#email-de').textContent = escapeText(email.de || '(sem remetente)');
  $('#email-assunto').textContent = escapeText(email.assunto || '(sem assunto)');
  $('#email-data').textContent = escapeText(email.data || '');
  $('#email-idioma').textContent = email.idioma ? `(${escapeText(email.idioma)})` : '';
  $('#email-resumo').textContent = escapeText(email.resumo || '');
  $('#email-anterior').disabled = state.emailIndex === 0;
  $('#email-proximo').disabled = state.emailIndex === emails.length - 1;
}

async function loadHistorico() {
  state.historicoIniciado = true;
  $('#historico-ranking').textContent = 'Carregando…';
  $('#chart-tooltip-cpu').hidden = true;
  $('#chart-tooltip-ram').hidden = true;
  try {
    await api().iniciar_historico();
    window.clearInterval(state.historicoTimer);
    state.historicoTimer = window.setInterval(refreshHistoricoState, 400);
    await refreshHistoricoState();
  } catch (error) {
    $('#historico-ranking').textContent = `Não consegui carregar: ${error.message || error}`;
    toast(error.message || String(error), 'Histórico — erro');
  }
}

function renderRanking(items) {
  const target = $('#historico-ranking');
  target.replaceChildren();
  const ranking = Array.isArray(items) ? items.slice(0, 6) : [];
  if (!ranking.length) {
    const empty = document.createElement('p'); empty.className = 'subtle'; empty.textContent = 'Sem execuções de rotina registradas hoje/ontem.'; target.append(empty); return;
  }
  ranking.forEach((item) => {
    const row = document.createElement('div'); row.className = 'ranking-row';
    const name = document.createElement('span'); name.textContent = escapeText(item.rotina || 'rotina');
    const metrics = document.createElement('strong'); metrics.textContent = `${Number(item.execucoes || 0)}x · ${Number(item.duracao_total_s || 0).toFixed(1)}s`;
    row.append(name, metrics); target.append(row);
  });
}

async function refreshHistoricoState() {
  try {
    const data = await api().historico_estado();
    if (!data) return;
    if (data.executando) return;
    window.clearInterval(state.historicoTimer);
    if (data.erro) {
      $('#historico-ranking').textContent = `Falha: ${data.erro}`;
      toast(data.erro, 'Histórico — erro');
      return;
    }
    const historico = data.dados || {};
    const resumo = historico.resumo || {};
    const porHora = Array.isArray(historico.por_hora) ? historico.por_hora : [];
    $('#historico-amostras').textContent = String(resumo.total || 0);
    $('#historico-cpu').textContent = `${formatNumber(resumo.cpu_pico)}% / ${formatNumber(resumo.cpu_media)}%`;
    $('#historico-ram').textContent = `${formatNumber(resumo.ram_pico)}% / ${formatNumber(resumo.ram_media)}%`;
    const buckets = porHora.slice(-24);
    const labels = buckets.map((bucket) => bucket.hora || '—');
    const cpuValues = buckets.map((bucket) => bucket.cpu_pico || 0);
    const ramValues = buckets.map((bucket) => bucket.ram_pico || 0);
    const fallbackLabels = ['00:00', 'agora'];
    drawHistoricoChart($('#historico-chart-cpu'), cpuValues.length ? cpuValues : [0, 0], labels.length ? labels : fallbackLabels, '#38bdf8');
    drawHistoricoChart($('#historico-chart-ram'), ramValues.length ? ramValues : [0, 0], labels.length ? labels : fallbackLabels, '#f59e0b');
    renderRanking(historico.ranking);
  } catch (error) {
    console.warn('histórico indisponível', error);
  }
}


async function quitApp() {
  try { await api().sair(); } catch (_) { window.close(); }
}

function wireEvents() {
  const orbCanvas = $('#gaia-orb');
  if (orbCanvas) {
    orbCanvas.addEventListener('click', (event) => {
      const rect = orbCanvas.getBoundingClientRect();
      const planet = planetAtPoint(event.clientX - rect.left, event.clientY - rect.top);
      if (planet) showScreen(planet.target);
    });
    orbCanvas.addEventListener('mousemove', (event) => {
      const rect = orbCanvas.getBoundingClientRect();
      orbHoverIndex = planetIndexAtPoint(event.clientX - rect.left, event.clientY - rect.top);
      orbCanvas.style.cursor = orbHoverIndex >= 0 ? 'pointer' : 'default';
    });
    orbCanvas.addEventListener('mouseleave', () => { orbHoverIndex = -1; orbCanvas.style.cursor = 'default'; });
  }
  $('#voltar-resumidor').addEventListener('click', () => showScreen('home'));
  $('#voltar-leitura').addEventListener('click', () => showScreen('resumidor'));
  $('#voltar-email').addEventListener('click', () => showScreen('leitura'));
  $('#voltar-historico').addEventListener('click', () => showScreen('home'));
  $('#ler-ultimo').addEventListener('click', abrirLeitura);
  $('#buscar-novos').addEventListener('click', openModal);
  $('#modal-sim').addEventListener('click', iniciarBusca);
  $('#modal-nao').addEventListener('click', closeModal);
  $('#email-ouvir').addEventListener('click', ouvirEmailAtual);
  $('#email-anterior').addEventListener('click', () => { pararLeitura(); if (state.emailIndex > 0) { state.emailIndex -= 1; renderEmail(); } });
  $('#email-proximo').addEventListener('click', () => { pararLeitura(); const total = state.resumo?.resumidos?.length || 0; if (state.emailIndex < total - 1) { state.emailIndex += 1; renderEmail(); } });
  $('#email-gmail').addEventListener('click', async () => {
    const link = state.resumo?.resumidos?.[state.emailIndex]?.link_email;
    if (!link) { toast('Este email não tem link do Gmail.', 'Gmail'); return; }
    try { const result = await api().abrir_gmail(link); if (!result?.aberto) toast(result?.mensagem || 'O navegador não pôde ser aberto.', 'Gmail'); } catch (error) { toast(error.message || String(error), 'Gmail'); }
  });
  $('#reload-historico').addEventListener('click', () => { state.historicoIniciado = false; loadHistorico(); });
  attachChartHover($('#historico-chart-cpu'), $('#chart-tooltip-cpu'));
  attachChartHover($('#historico-chart-ram'), $('#chart-tooltip-ram'));
  window.addEventListener('keydown', (event) => {
    const key = event.key.toLowerCase();
    if (!$('#modal-confirmacao').hidden) {
      if (key === 'escape' || key === 'n') { event.preventDefault(); closeModal(); }
      if (key === 's' || key === 'y') { event.preventDefault(); iniciarBusca(); }
      return;
    }
    if (key === 'q') { event.preventDefault(); quitApp(); return; }
    if (key === 'escape') {
      event.preventDefault();
      if (state.screen === 'email') { pararLeitura(); showScreen('leitura'); }
      else if (state.screen === 'leitura') showScreen('resumidor');
      else if (state.screen !== 'home') showScreen('home');
      return;
    }
    if (state.screen === 'home' && ['1', '2', '0'].includes(key)) {
      event.preventDefault();
      if (key === '1') showScreen('resumidor');
      else if (key === '2') showScreen('historico');
      else quitApp();
    } else if (state.screen === 'resumidor') {
      if (key === 'l') abrirLeitura();
      if (key === 'b') openModal();
    } else if (state.screen === 'email') {
      if (key === 'n') $('#email-proximo').click();
      if (key === 'p') $('#email-anterior').click();
      if (key === 'o') ouvirEmailAtual();
    } else if (state.screen === 'historico' && key === 'r') $('#reload-historico').click();
  });
  window.addEventListener('resize', () => {
    refreshMonitor();
    resizeGaiaOrb();
    if (state.screen === 'historico') refreshHistoricoState();
  });
}

async function boot() {
  if (state.booted) return;
  state.booted = true;
  updateClock();
  window.setInterval(updateClock, 1000);
  wireEvents();
  startGaiaOrb();
  await refreshMonitor();
  let refreshMs = 1000;
  try { refreshMs = Math.max(250, Math.round((await api().intervalo_tela()) * 1000)); } catch (_) { /* usa o padrão */ }
  state.monitorTimer = window.setInterval(refreshMonitor, refreshMs);
}

window.addEventListener('pywebviewready', boot);
