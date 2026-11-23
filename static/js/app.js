/**
 * SmartSite — AI Construction Safety Platform
 * Enterprise Dashboard Application Engine v2.0
 * Vanilla JS SPA — FastAPI Backend + WebSocket Real-Time Bus
 */

'use strict';

// ============================================================
// 1. APPLICATION STATE
// ============================================================
const App = {
  currentView: 'overview',
  wsConnection: null,
  wsReconnectTimer: null,
  pollTimers: {},
  audioEnabled: true,
  audioCtx: null,
  charts: {},
  chartsInitialized: false,
  uploadedFile: null,          // stores the File object for custom image upload
  uploadedFilePreviewUrl: null, // stores base64 data url preview of uploaded file
};

// ============================================================
// 2. BOOTSTRAP
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  initLucideIcons();
  startClock();
  connectWebSocket();
  initAudioToggle();
  refreshDashboard();          // Load overview immediately
  loadRegisteredWorkers();     // Preload registered personnel
  initDropzone();              // Wire drag-and-drop on custom upload dropzone
  startPollingLoop();
  lucide.createIcons();        // Re-render icons after DOM settles
});

function initLucideIcons() {
  if (typeof lucide !== 'undefined') lucide.createIcons();
}

// ============================================================
// 3. VIEW NAVIGATION
// ============================================================
function switchView(viewName) {
  // Hide all sections
  document.querySelectorAll('main > section').forEach(s => s.classList.add('hidden'));
  // Remove active from all nav tabs
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));

  // Show target section
  const target = document.getElementById(`view-${viewName}`);
  if (target) target.classList.remove('hidden');

  // Activate nav button
  const navBtn = document.getElementById(`nav-${viewName}`);
  if (navBtn) navBtn.classList.add('active');

  App.currentView = viewName;

  // Reset scroll to top
  const mainContent = document.getElementById('main-content');
  if (mainContent) mainContent.scrollTop = 0;

  // Per-view initialization on switch
  try {
    switch (viewName) {
      case 'overview':     refreshDashboard(); break;
      case 'camera':       pollStreamMetrics(); initDropzone(); break;
      case 'access':       loadActiveRoster(); loadRegisteredWorkers(); break;
      case 'iot':          loadIoTData(); break;
      case 'incidents':    loadIncidentsTable(); break;
      case 'regulations':  loadRegulations(); break;
    }
  } catch (err) {
    console.warn(`[SwitchView] Warning in ${viewName} initialization:`, err);
  }

  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
}

// ============================================================
// 4. LIVE CLOCK
// ============================================================
function startClock() {
  function tick() {
    const el = document.getElementById('live-clock');
    if (el) el.textContent = new Date().toLocaleTimeString('en-GB', { hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

// ============================================================
// 5. WEBSOCKET — REAL-TIME ALERT BUS
// ============================================================
function connectWebSocket() {
  if (App.wsConnection && App.wsConnection.readyState < 2) return;

  const wsUrl = `ws://${location.host}/ws`;
  App.wsConnection = new WebSocket(wsUrl);

  App.wsConnection.onopen = () => {
    updateWsStatus(true);
    if (App.wsReconnectTimer) { clearTimeout(App.wsReconnectTimer); App.wsReconnectTimer = null; }
  };

  App.wsConnection.onmessage = (evt) => {
    try {
      const msg = JSON.parse(evt.data);
      if (msg.type === 'incident_alert') {
        handleIncomingAlert(msg.payload);
      } else if (msg.type === 'keepalive') {
        // ignore
      }
    } catch (_) {}
  };

  App.wsConnection.onclose = () => {
    updateWsStatus(false);
    // Reconnect in 4s
    App.wsReconnectTimer = setTimeout(connectWebSocket, 4000);
  };

  App.wsConnection.onerror = () => App.wsConnection.close();
}

function updateWsStatus(connected) {
  const el = document.getElementById('ws-client-status');
  if (!el) return;
  el.textContent = connected ? 'Live (WebSocket)' : 'Reconnecting...';
  el.className = connected ? 'text-emerald-400 font-semibold' : 'text-amber-400 font-semibold';
}

function handleIncomingAlert(payload) {
  const priority = (payload.priority || '').toLowerCase();
  const color = priority === 'critical' ? 'rose' : priority === 'high' ? 'amber' : 'sky';
  showToast(
    `🚨 ${payload.priority}: ${payload.hazard_category || payload.event_type}`,
    payload.description || '',
    color,
    priority === 'critical' ? 7000 : 4500
  );
  if (App.audioEnabled) playAlertTone(priority);
  // Refresh KPIs silently
  fetchDashboardStats().then(updateKpiTiles);
  if (App.currentView === 'incidents') loadIncidentsTable();
}

// ============================================================
// 6. CONTINUOUS POLLING LOOP
// ============================================================
function startPollingLoop() {
  // Poll every 2.5 seconds
  setInterval(() => {
    if (App.currentView === 'overview') fetchDashboardStats().then(updateKpiTiles);
    if (App.currentView === 'camera')   pollStreamMetrics();
    if (App.currentView === 'iot')      loadIoTData();
  }, 2500);

  // Sensor chart refresh every 15s on overview
  setInterval(() => {
    if (App.currentView === 'overview') fetchChartData().then(updateCharts);
  }, 15000);
}

// ============================================================
// 7. DASHBOARD OVERVIEW
// ============================================================
async function refreshDashboard() {
  try {
    const [stats, charts] = await Promise.all([fetchDashboardStats(), fetchChartData()]);
    updateKpiTiles(stats);
    updateCharts(charts);
    loadRecentIncidents();
  } catch (e) {
    console.error('Dashboard refresh error:', e);
  }
}

async function fetchDashboardStats() {
  const r = await fetch('/api/v1/dashboard/stats');
  return r.json();
}

async function fetchChartData() {
  const r = await fetch('/api/v1/dashboard/charts');
  return r.json();
}

function updateKpiTiles(stats) {
  if (!stats) return;

  setText('kpi-workers',         stats.optical_workers_count ?? '--');
  setText('kpi-biometric-workers', stats.biometric_checked_in_count ?? '--');
  setText('kpi-compliance',      (stats.ppe_compliance_rate?.toFixed(1) ?? '--') + '%');
  setText('kpi-open-incidents',  stats.open_incidents_count ?? '--');
  setText('kpi-critical',        stats.critical_alerts_count ?? '--');
  setText('badge-open-incidents', stats.open_incidents_count ?? 0);

  const envEl = document.getElementById('kpi-env-status');
  if (envEl) {
    const env = stats.environmental_status || 'Normal';
    envEl.textContent = env.toUpperCase();
    envEl.className = `text-3xl font-black mono ${envStatusColor(env)}`;
  }

  // Zone breach banner on camera view
  const breachBanner = document.getElementById('live-breach-banner');
  if (breachBanner) {
    if (stats.is_zone_breach) {
      breachBanner.classList.remove('hidden');
    } else {
      breachBanner.classList.add('hidden');
    }
  }

  // Compliance color & progress bar
  const compEl = document.getElementById('kpi-compliance');
  if (compEl) {
    const rate = stats.ppe_compliance_rate ?? 100;
    compEl.className = `text-4xl font-black mono ${rate >= 90 ? 'text-emerald-400' : rate >= 75 ? 'text-amber-400' : 'text-rose-500'}`;
  }
  const compBar = document.getElementById('kpi-compliance-bar');
  if (compBar) {
    compBar.style.width = Math.min(100, Math.max(0, stats.ppe_compliance_rate ?? 100)) + '%';
  }

  // Calculate & Update Live AI Safety Risk Gauge (Circumference 2 * pi * 50 = 314)
  const ppeVio = Math.max(0, Math.min(100, Math.round(100 - (stats.ppe_compliance_rate ?? 100))));
  const zoneIntrusion = stats.is_zone_breach ? Math.min(100, (stats.active_zone_breaches || 1) * 35) : 0;
  const envRisk = (stats.environmental_status === 'Critical') ? 90 : (stats.environmental_status === 'Warning' ? 50 : 8);
  const totalRisk = Math.min(100, Math.round((ppeVio * 0.4) + (zoneIntrusion * 0.4) + (envRisk * 0.2)));

  const arc = document.getElementById('risk-gauge-arc');
  if (arc) {
    const offset = 314 - (314 * (totalRisk / 100));
    arc.style.strokeDashoffset = offset;
  }
  setText('risk-gauge-pct', totalRisk + '%');

  const riskLabel = document.getElementById('risk-gauge-label');
  if (riskLabel) {
    if (totalRisk >= 60) {
      riskLabel.textContent = '🚨 HIGH RISK ZONE';
      riskLabel.className = 'mt-2 badge-pill badge-critical text-[10px]';
    } else if (totalRisk >= 25) {
      riskLabel.textContent = '⚠️ ELEVATED HAZARD';
      riskLabel.className = 'mt-2 badge-pill badge-high text-[10px]';
    } else {
      riskLabel.textContent = '✅ SECURE PERIMETER';
      riskLabel.className = 'mt-2 badge-pill badge-resolved text-[10px]';
    }
  }

  // Risk breakdown bars
  setText('risk-ppe-pct', ppeVio + '%');
  const rPpeBar = document.getElementById('risk-ppe-bar');
  if (rPpeBar) rPpeBar.style.width = ppeVio + '%';

  setText('risk-zone-pct', zoneIntrusion + '%');
  const rZoneBar = document.getElementById('risk-zone-bar');
  if (rZoneBar) rZoneBar.style.width = zoneIntrusion + '%';

  setText('risk-env-pct', envRisk + '%');
  const rEnvBar = document.getElementById('risk-env-bar');
  if (rEnvBar) rEnvBar.style.width = envRisk + '%';
}

function envStatusColor(status) {
  if (!status) return 'text-emerald-400';
  const s = status.toLowerCase();
  if (s === 'normal') return 'text-emerald-400';
  if (s === 'warning') return 'text-amber-400';
  if (s === 'critical') return 'text-rose-500';
  return 'text-sky-400';
}

// ============================================================
// 8. CHARTS (Chart.js)
// ============================================================
function updateCharts(data) {
  if (!data) return;

  // --- Hazard Category Donut ---
  const catData = data.categories || {};
  const catLabels = catData.labels || [];
  const catValues = catData.values || [];
  const hazardColors = ['#ef4444','#f59e0b','#38bdf8','#10b981','#a855f7','#f97316','#ec4899'];

  if (!App.charts.hazard) {
    const ctx = document.getElementById('chart-hazard-categories');
    if (ctx) {
      App.charts.hazard = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: catLabels,
          datasets: [{ data: catValues, backgroundColor: hazardColors, borderWidth: 0, hoverOffset: 4 }]
        },
        options: {
          plugins: {
            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 10 } }
          },
          cutout: '65%',
          responsive: true,
          maintainAspectRatio: false,
        }
      });
    }
  } else {
    App.charts.hazard.data.labels = catLabels;
    App.charts.hazard.data.datasets[0].data = catValues;
    App.charts.hazard.update('none');
  }

  // --- Sensor History Line Chart ---
  const st = data.sensor_trends || {};
  const labels = st.labels || [];

  if (!App.charts.sensor) {
    const ctx2 = document.getElementById('chart-sensor-history');
    if (ctx2) {
      App.charts.sensor = new Chart(ctx2, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Temp (°C)',
              data: st.temperature || [],
              borderColor: '#f97316', backgroundColor: 'rgba(249,115,22,0.07)',
              tension: 0.4, borderWidth: 2, pointRadius: 0, fill: true
            },
            {
              label: 'Dust (µg/m³)',
              data: st.dust || [],
              borderColor: '#facc15', backgroundColor: 'rgba(250,204,21,0.07)',
              tension: 0.4, borderWidth: 2, pointRadius: 0, fill: true
            },
            {
              label: 'Gas (ppm)',
              data: st.gas || [],
              borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.07)',
              tension: 0.4, borderWidth: 2, pointRadius: 0, fill: true
            },
            {
              label: 'Noise (dBA)',
              data: st.noise || [],
              borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.07)',
              tension: 0.4, borderWidth: 2, pointRadius: 0, fill: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { position: 'top', labels: { color: '#94a3b8', font: { size: 10 }, boxWidth: 12 } }
          },
          scales: {
            x: { ticks: { color: '#475569', maxTicksLimit: 10, font: { size: 9 } }, grid: { color: '#1e293b' } },
            y: { ticks: { color: '#475569', font: { size: 9 } }, grid: { color: '#1e293b' } }
          }
        }
      });
    }
  } else {
    App.charts.sensor.data.labels = labels;
    App.charts.sensor.data.datasets[0].data = st.temperature || [];
    App.charts.sensor.data.datasets[1].data = st.dust || [];
    App.charts.sensor.data.datasets[2].data = st.gas || [];
    App.charts.sensor.data.datasets[3].data = st.noise || [];
    App.charts.sensor.update('none');
  }
}

// ============================================================
// 9. RECENT INCIDENTS (Overview)
// ============================================================
async function loadRecentIncidents() {
  try {
    const r = await fetch('/api/v1/incidents/?limit=5');
    const data = await r.json();
    const events = Array.isArray(data) ? data : (data.events || []);
    const tbody = document.getElementById('overview-incidents-body');
    if (!tbody) return;

    if (!events.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="py-6 text-center text-slate-500">No incidents recorded yet.</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(evt => `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-4 mono font-semibold text-sky-400">${evt.event_id}</td>
        <td class="py-2.5 px-4 text-slate-400">${formatTime(evt.timestamp)}</td>
        <td class="py-2.5 px-4 text-slate-200">${evt.hazard_category}</td>
        <td class="py-2.5 px-4">${priorityBadge(evt.priority)}</td>
        <td class="py-2.5 px-4 text-slate-400">${evt.site_zone}</td>
        <td class="py-2.5 px-4">${statusBadge(evt.status)}</td>
        <td class="py-2.5 px-4 text-slate-400">${evt.osha_ref || '—'}</td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Failed to load recent incidents:', e);
  }
}

// ============================================================
// 10. CAMERA MONITORING
// ============================================================
async function pollStreamMetrics() {
  try {
    const r = await fetch('/api/v1/stream/metrics');
    const data = await r.json();
    const metrics = data.metrics || {};

    // Update live workers panel
    const list = document.getElementById('live-workers-list');
    if (list) {
      const profiles = metrics.profiles || [];
      if (profiles.length === 0) {
        list.innerHTML = `<div class="text-center text-slate-500 py-4 text-xs">
          ${data.is_running ? 'Analyzing frame... No tracked workers detected.' : 'Stream inactive.'}
        </div>`;
      } else {
        list.innerHTML = profiles.map((p, i) => `
          <div class="p-3 rounded bg-slate-900 border border-slate-800 flex items-center justify-between">
            <div>
              <div class="font-bold text-slate-200">Worker #${i+1} (Track ID: ${p.worker_id})</div>
              <div class="text-[11px] ${workerStatusColor(p.violations)}">
                Helmet: ${ppe_badge(p.helmet)} • Vest: ${ppe_badge(p.vest)}
                ${p.violations.length ? ` — ⚠ ${p.violations.join(', ')}` : ''}
              </div>
            </div>
            ${p.violations.length ? '<span class="badge-pill badge-critical">VIOLATION</span>' : '<span class="badge-pill badge-resolved">SAFE</span>'}
          </div>
        `).join('');
      }
    }

    // Zone breach banner
    const breachBanner = document.getElementById('live-breach-banner');
    if (breachBanner) {
      metrics.is_breach ? breachBanner.classList.remove('hidden') : breachBanner.classList.add('hidden');
    }

  } catch (e) {}
}

function ppe_badge(status) {
  if (!status) return '?';
  if (status === 'compliant') return '✅';
  if (status === 'violation') return '❌';
  return '—';
}

function workerStatusColor(violations) {
  return (violations && violations.length > 0) ? 'text-rose-400' : 'text-emerald-400';
}

function toggleStreamPlayPause() {
  const btn = document.getElementById('btn-stream-play');
  const streamImg = document.getElementById('live-ppe-stream');
  if (!btn) return;

  const isPaused = btn.dataset.state === 'paused';
  const action = isPaused ? 'play' : 'pause';

  fetch('/api/v1/stream/controls', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action })
  }).then(() => {
    if (isPaused) {
      btn.dataset.state = 'playing';
      btn.innerHTML = '<i data-lucide="pause" class="w-3.5 h-3.5"></i> Pause Stream';
      if (streamImg) streamImg.src = '/api/v1/stream/ppe?' + Date.now();
    } else {
      btn.dataset.state = 'paused';
      btn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5"></i> Resume Stream';
    }
    lucide.createIcons();
  });
}

function changeCameraSource(sourceType) {
  fetch('/api/v1/stream/source', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source_type: sourceType })
  }).then(() => {
    const streamImg = document.getElementById('live-ppe-stream');
    if (streamImg) streamImg.src = '/api/v1/stream/ppe?' + Date.now();
    showToast('Camera Source Changed', `Switched to: ${sourceType}`, 'sky', 2500);
  }).catch(() => {
    showToast('Source Error', 'Failed to switch source. Webcam may not be available.', 'amber', 3000);
  });
}

async function uploadCustomVideo() {
  const input = document.getElementById('custom-video-input');
  if (!input || !input.files.length) {
    showToast('No File', 'Please select an MP4 or AVI video file first.', 'amber', 3000);
    return;
  }

  const formData = new FormData();
  formData.append('file', input.files[0]);

  showToast('Uploading...', `Processing ${input.files[0].name}`, 'sky', 3000);

  try {
    const r = await fetch('/api/v1/stream/upload_video', { method: 'POST', body: formData });
    const data = await r.json();
    if (r.ok) {
      const streamImg = document.getElementById('live-ppe-stream');
      if (streamImg) streamImg.src = '/api/v1/stream/ppe?' + Date.now();
      showToast('Video Loaded', `Now processing: ${data.filename}`, 'emerald', 3000);
    } else {
      showToast('Upload Failed', data.detail || 'Upload error', 'rose', 4000);
    }
  } catch (e) {
    showToast('Upload Error', e.message, 'rose', 4000);
  }
}

// ============================================================
// 11. ZONE CONFIGURATION
// ============================================================
function updateZoneSliders() {
  const vals = ['x1','y1','x2','y2'];
  vals.forEach(k => {
    const input = document.getElementById(`input-zone-${k}`);
    const display = document.getElementById(`val-zone-${k}`);
    if (input && display) display.textContent = input.value + '%';
  });
}

async function saveZoneSettings() {
  const x1 = parseFloat(document.getElementById('input-zone-x1')?.value || 55) / 100;
  const y1 = parseFloat(document.getElementById('input-zone-y1')?.value || 35) / 100;
  const x2 = parseFloat(document.getElementById('input-zone-x2')?.value || 95) / 100;
  const y2 = parseFloat(document.getElementById('input-zone-y2')?.value || 90) / 100;

  try {
    const r = await fetch('/api/v1/zones/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ x1, y1, x2, y2, zone_name: 'Custom Restricted Zone' })
    });
    if (r.ok) {
      showToast('Zone Saved', `Restricted zone updated: (${(x1*100).toFixed(0)}%, ${(y1*100).toFixed(0)}%) → (${(x2*100).toFixed(0)}%, ${(y2*100).toFixed(0)}%)`, 'emerald', 3000);
    } else {
      showToast('Zone Error', 'Failed to save zone config.', 'rose', 3000);
    }
  } catch (e) {
    showToast('Zone Error', e.message, 'rose', 3000);
  }
}

// ============================================================
// 11B. SINGLE-IMAGE AI VISION & DANGEROUS-ZONE ASSESSMENT
// ============================================================
App.uploadedFile = null;
App.uploadedFilePreviewUrl = null;
App.selectedDatasetImg = null;
App.dangerZoneEnabled = true;

function triggerFileInput() {
  const input = document.getElementById('direct-image-upload');
  if (input) input.click();
}

function onDirectFileSelected(files) {
  if (!files || !files.length) return;
  const file = files[0];
  App.uploadedFile = file;
  App.selectedDatasetImg = null;

  // Reset dataset dropdown
  const dsSelect = document.getElementById('select-dataset-sample');
  if (dsSelect) dsSelect.value = '';

  const badge = document.getElementById('uploaded-file-badge');
  const filenameText = document.getElementById('uploaded-filename-text');
  const thumb = document.getElementById('upload-thumb-preview');
  if (badge) { badge.classList.remove('hidden'); badge.classList.add('flex'); }
  if (filenameText) filenameText.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`;

  const reader = new FileReader();
  reader.onload = (e) => {
    App.uploadedFilePreviewUrl = e.target.result;
    if (thumb) thumb.src = e.target.result;
    const displayImg = document.getElementById('dataset-image-display');
    const placeholder = document.getElementById('dataset-img-placeholder');
    if (displayImg) { displayImg.src = e.target.result; displayImg.classList.remove('hidden'); }
    if (placeholder) placeholder.classList.add('hidden');
  };
  reader.readAsDataURL(file);

  showToast('Photo Loaded', `Ready to analyze ${file.name}`, 'sky', 2500);
}

function clearDirectImage(e) {
  if (e && e.stopPropagation) e.stopPropagation();
  App.uploadedFile = null;
  App.uploadedFilePreviewUrl = null;
  const input = document.getElementById('direct-image-upload');
  if (input) input.value = '';
  const badge = document.getElementById('uploaded-file-badge');
  if (badge) { badge.classList.add('hidden'); badge.classList.remove('flex'); }

  const displayImg = document.getElementById('dataset-image-display');
  const placeholder = document.getElementById('dataset-img-placeholder');
  if (displayImg) { displayImg.src = ''; displayImg.classList.add('hidden'); }
  if (placeholder) placeholder.classList.remove('hidden');
}

function onDatasetDropdownChange(val) {
  if (!val) {
    App.selectedDatasetImg = null;
    return;
  }
  // Clear any uploaded custom file
  clearDirectImage();
  App.selectedDatasetImg = val;

  const displayImg = document.getElementById('dataset-image-display');
  const placeholder = document.getElementById('dataset-img-placeholder');
  if (displayImg) {
    displayImg.src = `/dataset_images/${val}`;
    displayImg.classList.remove('hidden');
  }
  if (placeholder) placeholder.classList.add('hidden');
  showToast('Dataset Scene Selected', val, 'sky', 2000);
}

function onToggleDangerZone(enabled) {
  App.dangerZoneEnabled = !!enabled;
  const controls = document.getElementById('danger-zone-controls');
  const label = document.getElementById('label-danger-zone-enabled');
  if (controls) {
    if (enabled) {
      controls.classList.remove('hidden');
    } else {
      controls.classList.add('hidden');
    }
  }
  if (label) {
    label.textContent = enabled ? 'Enabled' : 'Disabled';
    label.className = enabled ? 'text-amber-400 font-bold text-[11px]' : 'text-slate-500 font-medium text-[11px]';
  }
  showToast('Danger Zone Geofence', enabled ? 'Virtual danger zone active' : 'Disabled (YOLO PPE only)', enabled ? 'amber' : 'slate', 2000);
}

function initDropzone() {
  const dz = document.getElementById('dropzone-area');
  if (!dz || dz._dzInited) return;
  dz._dzInited = true;

  ['dragenter', 'dragover'].forEach(name => {
    dz.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.add('dropzone-active');
    });
  });

  ['dragleave', 'dragend'].forEach(name => {
    dz.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dz.classList.remove('dropzone-active');
    });
  });

  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    e.stopPropagation();
    dz.classList.remove('dropzone-active');
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length) {
      onDirectFileSelected(e.dataTransfer.files);
    }
  });
}

function setZoneSliders(x1, y1, x2, y2, zoneName) {
  const inX1 = document.getElementById('input-zone-x1');
  const inY1 = document.getElementById('input-zone-y1');
  const inX2 = document.getElementById('input-zone-x2');
  const inY2 = document.getElementById('input-zone-y2');
  const nameLabel = document.getElementById('active-zone-label');

  if (inX1) inX1.value = Math.round(x1);
  if (inY1) inY1.value = Math.round(y1);
  if (inX2) inX2.value = Math.round(x2);
  if (inY2) inY2.value = Math.round(y2);
  if (nameLabel && zoneName) nameLabel.textContent = zoneName;

  updateZoneSliders();
}

function applyZonePreset(presetKey) {
  const presets = {
    pit: { x1: 55, y1: 35, x2: 95, y2: 90, name: 'Pit B Excavation Area' },
    crane: { x1: 25, y1: 20, x2: 75, y2: 75, name: 'Crane Swing Radius' },
    scaffold: { x1: 20, y1: 25, x2: 85, y2: 88, name: 'Scaffold Drop Zone' },
    staging: { x1: 45, y1: 30, x2: 90, y2: 90, name: 'Material Staging Exclusion' }
  };
  const p = presets[presetKey] || presets.pit;
  setZoneSliders(p.x1, p.y1, p.x2, p.y2, p.name);
  showToast('Zone Preset Applied', `${p.name}`, 'amber', 2000);
}

async function runVisionZoneInspection() {
  const btn = document.getElementById('btn-run-inspection');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin"></i> Running AI Safety Inspection...';
    lucide.createIcons();
  }

  const directFileInput = document.getElementById('direct-image-upload');
  const fileToUpload = App.uploadedFile || (directFileInput && directFileInput.files && directFileInput.files[0]);
  const datasetImg = App.selectedDatasetImg || document.getElementById('select-dataset-sample')?.value;

  if (!fileToUpload && !datasetImg) {
    showToast('No Image Selected', 'Please upload a site photo or choose a dataset image first.', 'amber', 3500);
    resetInspectionButton();
    return;
  }

  const conf = (parseFloat(document.getElementById('dataset-image-conf')?.value || 25)) / 100;
  const zoneToggle = document.getElementById('toggle-danger-zone');
  const isZoneEnabled = zoneToggle ? zoneToggle.checked : true;

  const x1 = parseFloat(document.getElementById('input-zone-x1')?.value || 55) / 100;
  const y1 = parseFloat(document.getElementById('input-zone-y1')?.value || 35) / 100;
  const x2 = parseFloat(document.getElementById('input-zone-x2')?.value || 95) / 100;
  const y2 = parseFloat(document.getElementById('input-zone-y2')?.value || 90) / 100;
  const zoneName = document.getElementById('active-zone-label')?.textContent || 'Restricted Danger Zone';

  const formData = new FormData();
  formData.append('conf_threshold', conf);
  formData.append('enable_zone', isZoneEnabled);
  formData.append('zone_x1', x1);
  formData.append('zone_y1', y1);
  formData.append('zone_x2', x2);
  formData.append('zone_y2', y2);
  formData.append('zone_name', zoneName);

  if (fileToUpload) {
    formData.append('file', fileToUpload, fileToUpload.name);
    showToast('Analyzing...', `Running YOLO11n on ${fileToUpload.name}...`, 'sky', 2500);
  } else {
    formData.append('dataset_image', datasetImg);
    showToast('Analyzing...', `Running YOLO11n on ${datasetImg}...`, 'sky', 2500);
  }

  try {
    const r = await fetch('/api/v1/stream/analyze_image', { method: 'POST', body: formData });
    const data = await r.json();

    if (!r.ok || data.status !== 'ok') {
      showToast('Analysis Error', data?.detail || 'Inference failed', 'rose', 4000);
      resetInspectionButton();
      return;
    }

    renderInspectionResults(data);
  } catch (e) {
    showToast('Inference Error', e.message, 'rose', 4000);
  } finally {
    resetInspectionButton();
  }
}

function resetInspectionButton() {
  const btn = document.getElementById('btn-run-inspection');
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="scan" class="w-4 h-4"></i> Run AI Safety & PPE Inspection';
    lucide.createIcons();
  }
}

function renderInspectionResults(data) {
  // 1. Render Annotated Image on Canvas
  const displayImg = document.getElementById('dataset-image-display');
  const placeholder = document.getElementById('dataset-img-placeholder');
  const canvasStatus = document.getElementById('canvas-badge-status');

  if (displayImg && data.annotated_image) {
    displayImg.src = data.annotated_image;
    displayImg.classList.remove('hidden');
  }
  if (placeholder) placeholder.classList.add('hidden');
  if (canvasStatus) {
    canvasStatus.textContent = `${data.worker_count} Workers • ${data.detections.length} Objects`;
    canvasStatus.className = 'badge-pill badge-low text-[10px]';
  }

  // 2. Zone Breach Flash Banner
  const banner = document.getElementById('zone-inspection-banner');
  const zoneStatus = data.zone_status || {};
  const isBreach = zoneStatus.breach_active || (zoneStatus.workers_in_zone > 0);
  const inZoneCount = zoneStatus.workers_in_zone || 0;

  if (banner) {
    banner.classList.remove('hidden');
    if (isBreach) {
      banner.className = 'rounded-xl p-4 border border-rose-500/40 bg-gradient-to-r from-rose-950/70 to-rose-900/40 text-rose-200 backdrop-blur-md animate-pulse flex items-center justify-between shadow-lg shadow-rose-950/30';
      banner.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-rose-600/30 border border-rose-500 flex items-center justify-center text-rose-400 shrink-0">
            <i data-lucide="alert-octagon" class="w-5 h-5"></i>
          </div>
          <div>
            <div class="font-extrabold text-sm text-rose-300 tracking-tight flex items-center gap-2">
              🚨 CRITICAL SAFETY ALERT: ${inZoneCount} Worker${inZoneCount > 1 ? 's' : ''} Inside Restricted Zone '${data.zone_name}'!
            </div>
            <div class="text-xs text-rose-300/80 mt-0.5">
              Geometric foot ground-contact intrusion detected • Immediate evacuation and supervisor intervention required.
            </div>
          </div>
        </div>
        <div class="text-right shrink-0 hidden sm:block">
          <span class="badge-pill badge-critical text-[11px]">29 CFR 1926 Subpart P</span>
        </div>
      `;
      if (App.audioEnabled) playAlertTone('critical');
    } else {
      banner.className = 'rounded-xl p-4 border border-emerald-500/30 bg-gradient-to-r from-emerald-950/60 to-emerald-900/30 text-emerald-200 backdrop-blur-md flex items-center justify-between shadow-lg shadow-emerald-950/20';
      banner.innerHTML = `
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg bg-emerald-600/30 border border-emerald-500 flex items-center justify-center text-emerald-400 shrink-0">
            <i data-lucide="shield-check" class="w-5 h-5"></i>
          </div>
          <div>
            <div class="font-extrabold text-sm text-emerald-300 tracking-tight flex items-center gap-2">
              ✅ DESIGNATED PERIMETER SECURE: Zone Clear
            </div>
            <div class="text-xs text-emerald-300/80 mt-0.5">
              0 workers observed inside restricted boundary '${data.zone_name}'. All active personnel are positioned safely outside.
            </div>
          </div>
        </div>
        <div class="text-right shrink-0 hidden sm:block">
          <span class="badge-pill badge-resolved text-[11px]">PERIMETER CLEAR</span>
        </div>
      `;
    }
  }

  // 3. Update Metric KPI Tiles
  setText('img-worker-count', data.worker_count);
  setText('img-compliance-rate', (data.compliance_rate || 0).toFixed(0) + '%');

  const breachEl = document.getElementById('img-zone-breach-count');
  if (breachEl) {
    breachEl.textContent = inZoneCount;
    breachEl.className = `text-2xl font-black mono mt-1 ${isBreach ? 'text-rose-400 animate-pulse' : 'text-emerald-400'}`;
  }

  // Calculate missing PPE count from worker telemetry
  const workers = data.workers || [];
  const violatingWorkers = workers.filter(w => w.violations && w.violations.length > 0);
  setText('img-violations-count', violatingWorkers.length);

  // 4. Detected PPE Objects Pill List
  const detectionsList = document.getElementById('img-detections-list');
  if (detectionsList) {
    const detections = data.detections || [];
    if (!detections.length) {
      detectionsList.innerHTML = '<span class="text-slate-500 text-xs">No objects detected.</span>';
    } else {
      detectionsList.innerHTML = detections.map(d => {
        const isVio = d.is_violation;
        const bg = isVio ? 'bg-rose-950/60 text-rose-300 border-rose-700/60' : 'bg-slate-800 text-slate-300 border-slate-700';
        return `<span class="px-2 py-0.5 rounded text-[10px] mono border ${bg}">
          ${d.class_name} (${(d.confidence * 100).toFixed(0)}%)
        </span>`;
      }).join('');
    }
  }

  // 5. Worker-by-Worker Telemetry Breakdown Table
  const tbody = document.getElementById('workers-telemetry-body');
  const countBadge = document.getElementById('telemetry-workers-count-badge');
  if (countBadge) countBadge.textContent = `${workers.length} Workers`;

  if (tbody) {
    if (!workers.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="py-6 text-center text-slate-500 text-xs">No worker persons detected in this image.</td></tr>';
    } else {
      tbody.innerHTML = workers.map(w => {
        const inZone = w.in_zone;
        const zoneBadge = inZone 
          ? '<span class="badge-pill badge-critical text-[10px]">🚨 ZONE INTRUSION</span>'
          : '<span class="badge-pill badge-resolved text-[10px]">✅ CLEAR (OUTSIDE)</span>';

        const helmetBadge = w.helmet_status === 'Compliant'
          ? '<span class="text-emerald-400 font-semibold flex items-center gap-1">⛑ Helmet OK</span>'
          : w.helmet_status === 'Missing'
          ? '<span class="text-rose-400 font-bold flex items-center gap-1">❌ NO HELMET</span>'
          : '<span class="text-slate-500">—</span>';

        const vestBadge = w.vest_status === 'Compliant'
          ? '<span class="text-emerald-400 font-semibold flex items-center gap-1">🦺 Vest OK</span>'
          : w.vest_status === 'Missing'
          ? '<span class="text-rose-400 font-bold flex items-center gap-1">❌ NO VEST</span>'
          : '<span class="text-slate-500">—</span>';

        const riskBadge = w.risk === 'CRITICAL'
          ? '<span class="badge-pill badge-critical text-[10px]">CRITICAL</span>'
          : w.risk === 'HIGH' || w.risk === 'WARNING'
          ? '<span class="badge-pill badge-high text-[10px]">' + w.risk + '</span>'
          : '<span class="badge-pill badge-resolved text-[10px]">SAFE</span>';

        const bc = w.bottom_center || [0, 0];
        const bcText = `X: ${bc[0]}px, Y: ${bc[1]}px`;

        return `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-2.5 px-3 mono font-bold text-sky-400 text-xs">Worker #${w.worker_id}</td>
            <td class="py-2.5 px-3 mono text-slate-400 text-[11px]">${bcText}</td>
            <td class="py-2.5 px-3">${zoneBadge}</td>
            <td class="py-2.5 px-3 text-xs">${helmetBadge}</td>
            <td class="py-2.5 px-3 text-xs">${vestBadge}</td>
            <td class="py-2.5 px-3">${riskBadge}</td>
          </tr>
        `;
      }).join('');
    }
  }

  lucide.createIcons();
  showToast(
    isBreach ? '🚨 Danger Zone Breach!' : '✅ Inspection Completed',
    `Found ${data.worker_count} workers (${inZoneCount} in restricted area), ${violationsCount(workers)} PPE violations.`,
    isBreach ? 'rose' : 'emerald',
    4500
  );
}

function violationsCount(workers) {
  return workers.reduce((acc, w) => acc + (w.violations ? w.violations.length : 0), 0);
}

function toggleVideoFeedModal() {
  const videoSec = document.getElementById('video-stream-collapsible');
  const btnText = document.getElementById('btn-video-mode-text');
  if (!videoSec) return;

  const isHidden = videoSec.classList.contains('hidden');
  if (isHidden) {
    videoSec.classList.remove('hidden');
    if (btnText) btnText.textContent = 'Hide Video Stream';
  } else {
    videoSec.classList.add('hidden');
    if (btnText) btnText.textContent = 'Live Video Feed (Demo)';
  }
}

function toggleCanvasFullscreen() {
  const container = document.getElementById('inspection-canvas-container');
  if (!container) return;

  if (!document.fullscreenElement) {
    container.requestFullscreen().catch(() => {});
  } else {
    document.exitFullscreen().catch(() => {});
  }
}

// ============================================================
// 12. BIOMETRIC ACCESS CONTROL
// ============================================================
async function loadActiveRoster() {
  try {
    const r = await fetch('/api/v1/workers/on_site');
    const data = await r.json();
    const workers = Array.isArray(data) ? data : (data.workers || []);
    const list = document.getElementById('active-roster-list');
    if (!list) return;

    if (!workers.length) {
      list.innerHTML = '<div class="text-center text-slate-500 py-4 text-xs">No workers currently checked in.</div>';
      return;
    }

    list.innerHTML = workers.map(w => `
      <div class="p-3 rounded-lg bg-slate-900 border border-slate-800 flex items-center gap-3">
        <div class="w-9 h-9 rounded-full border-2 border-emerald-500/50 bg-slate-800 flex items-center justify-center shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="font-bold text-xs text-slate-200 truncate">${w.worker_name}</div>
          <div class="text-[11px] text-slate-400 truncate">${w.role}</div>
          <div class="text-[10px] text-emerald-400 mt-0.5">${w.osha_cert}</div>
        </div>
        <div class="text-right shrink-0">
          <span class="badge-pill badge-resolved text-[10px]">ON SITE</span>
          <div class="text-[10px] text-slate-500 mt-1">${formatTime(w.timestamp)}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    console.error('Roster load error:', e);
  }
}

function photoUrl(path) {
  if (!path) return '';
  // Normalize Windows backslashes to forward slashes
  const normalized = path.replace(/\\/g, '/');
  // Extract just the filename from any absolute or relative path
  const facesIdx = normalized.indexOf('data/faces/');
  if (facesIdx !== -1) {
    return '/faces/' + normalized.substring(facesIdx + 'data/faces/'.length);
  }
  // If path starts with /faces/ already
  if (normalized.startsWith('faces/')) return '/' + normalized;
  if (normalized.startsWith('/faces/')) return normalized;
  // For any absolute Windows path like D:/..., extract the filename only
  const filename = normalized.split('/').pop();
  if (filename) return '/faces/' + filename;
  return '';
}

async function loadRegisteredWorkers() {
  try {
    const r = await fetch('/api/v1/workers');
    const workers = await r.json();
    const list = Array.isArray(workers) ? workers : [];

    // Update count badge
    const countBadge = document.getElementById('registered-workers-count');
    if (countBadge) {
      countBadge.textContent = `${list.length} Enrolled`;
    }

    // Populate dropdown in turnstile scanner
    const select = document.getElementById('select-registered-worker');
    if (select) {
      if (!list.length) {
        select.innerHTML = '<option value="">-- No registered workers yet --</option>';
      } else {
        select.innerHTML = list.map(w => `
          <option value="${w.worker_code}">${w.worker_code} — ${w.full_name} (${w.role})</option>
        `).join('');
      }
    }

    // Populate directory grid
    const grid = document.getElementById('registered-workers-grid');
    if (grid) {
      if (!list.length) {
        grid.innerHTML = '<div class="col-span-3 text-center text-slate-500 py-8 text-xs">No registered workers in SQLite database. Register a worker below to begin biometric turnstile matching.</div>';
        return;
      }

      grid.innerHTML = list.map(w => `
        <div class="p-4 rounded-xl bg-slate-900 border border-slate-800 flex flex-col justify-between space-y-3 hover:border-slate-700 transition">
          <div class="flex items-start gap-3">
            <div class="w-14 h-14 rounded-lg border border-slate-700 bg-slate-950 shrink-0 flex items-center justify-center">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-7 h-7 text-slate-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="flex items-center justify-between">
                <span class="mono font-bold text-xs text-sky-400">${w.worker_code}</span>
                <span class="text-[9px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-1.5 py-0.5 rounded">ArcFace 512-d</span>
              </div>
              <div class="font-bold text-sm text-slate-100 truncate mt-0.5">${w.full_name}</div>
              <div class="text-[11px] text-slate-400 truncate">${w.role}</div>
              <div class="text-[10px] text-amber-400 mt-1">${w.osha_cert || 'OSHA 10'}</div>
            </div>
          </div>

          <div class="text-[10px] text-slate-500 bg-slate-950/50 p-2 rounded border border-slate-800/80 truncate">
            <span class="text-slate-400 font-semibold">Zones:</span> ${w.authorized_zones || 'All Zones'}
          </div>

          <div class="flex items-center gap-2 pt-1 border-t border-slate-800/80">
            <button onclick="testWorkerAtGate('${w.worker_code}')" class="flex-1 bg-cyan-900/40 hover:bg-cyan-800/60 border border-cyan-700/50 text-cyan-300 font-semibold text-[11px] py-1.5 rounded transition flex items-center justify-center gap-1">
              <i data-lucide="scan-face" class="w-3.5 h-3.5"></i> Test Gate
            </button>
            <button onclick="deleteWorker('${w.worker_code}')" class="bg-rose-950/40 hover:bg-rose-900/60 border border-rose-800/50 text-rose-400 font-semibold text-[11px] px-2.5 py-1.5 rounded transition" title="Delete Worker">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `).join('');
      lucide.createIcons();
    }
  } catch (e) {
    console.error('Failed to load registered workers:', e);
  }
}

function testWorkerAtGate(workerCode) {
  const select = document.getElementById('select-registered-worker');
  if (select) select.value = workerCode;
  triggerGateVerification();
}

async function deleteWorker(workerCode) {
  if (!confirm(`Are you sure you want to remove worker ${workerCode} and delete their biometric embedding?`)) return;

  try {
    const r = await fetch(`/api/v1/workers/${encodeURIComponent(workerCode)}`, { method: 'DELETE' });
    if (r.ok) {
      showToast('Worker Deleted', `Removed ${workerCode} from biometric registry.`, 'amber', 3000);
      loadRegisteredWorkers();
      loadActiveRoster();
    } else {
      showToast('Delete Failed', 'Could not delete worker.', 'rose', 3000);
    }
  } catch (e) {
    showToast('Error', e.message, 'rose', 3000);
  }
}

async function triggerGateVerification() {
  const workerCode = document.getElementById('select-registered-worker')?.value;
  const gate = document.getElementById('gate-selector')?.value || 'Gate 1 - Main Turnstile';

  if (!workerCode) {
    showToast('No Worker', 'Please select or enroll a registered worker first.', 'amber', 3000);
    return;
  }

  showToast('Scanning Biometrics...', `Running ArcFace verification for ${workerCode}`, 'sky', 2000);

  const formData = new FormData();
  formData.append('worker_code', workerCode);
  formData.append('demo_worker_code', workerCode);
  formData.append('gate_name', gate);

  try {
    const r = await fetch('/api/v1/stream/gate_verify', { method: 'POST', body: formData });
    const data = await r.json();

    const img = document.getElementById('gate-result-img');
    const placeholder = document.getElementById('gate-empty-placeholder');
    const matchCard = document.getElementById('gate-match-card');
    const matchTitle = document.getElementById('gate-match-title');
    const matchDetails = document.getElementById('gate-match-details');

    if (r.ok && data.annotated_image) {
      if (img) {
        img.src = data.annotated_image;
        img.classList.remove('hidden');
      }
      if (placeholder) placeholder.classList.add('hidden');

      const matches = data.matches || [];
      if (matchCard) matchCard.classList.remove('hidden');

      if (matches.length > 0) {
        const m = matches[0];
        const granted = m.access_status === 'Granted';
        if (matchCard) {
          matchCard.className = `p-4 rounded-lg border text-xs space-y-1 ${
            granted ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-rose-500/30 bg-rose-500/10'
          }`;
        }
        if (matchTitle) {
          matchTitle.className = `font-bold text-sm flex items-center gap-2 ${granted ? 'text-emerald-400' : 'text-rose-400'}`;
          matchTitle.innerHTML = `<i data-lucide="${granted ? 'check-circle' : 'x-circle'}" class="w-4 h-4"></i>
            ${granted ? 'ACCESS GRANTED' : 'ACCESS DENIED'}: ${m.matched_worker_name || 'Unknown'} (${m.matched_worker_code || '—'})`;
        }
        if (matchDetails) {
          matchDetails.innerHTML = `Role: ${m.role || '—'} | OSHA: ${m.osha_cert || '—'} | Cosine Similarity: ${((m.confidence || 0) * 100).toFixed(1)}%`;
        }
        lucide.createIcons();
        showToast(
          granted ? '✅ Access Granted' : '🚫 Access Denied',
          `${m.matched_worker_name || 'Unknown'} — ${((m.confidence || 0) * 100).toFixed(1)}% match`,
          granted ? 'emerald' : 'rose',
          4000
        );
        loadActiveRoster();
      }
    } else {
      showToast('Gate Error', data?.detail || 'Verification error', 'rose', 4000);
    }
  } catch (e) {
    showToast('Verification Error', e.message, 'rose', 4000);
  }
}

async function verifyUploadedFace() {
  const input = document.getElementById('gate-upload-input');
  const gate = document.getElementById('gate-selector')?.value || 'Gate 1 - Main Turnstile';

  if (!input || !input.files.length) {
    showToast('No Image', 'Please select an image to verify.', 'amber', 3000);
    return;
  }

  const formData = new FormData();
  formData.append('file', input.files[0]);
  formData.append('gate_name', gate);

  showToast('Analyzing Face...', 'Running ArcFace biometric verification...', 'sky', 2500);

  try {
    const r = await fetch('/api/v1/stream/gate_verify', { method: 'POST', body: formData });
    const data = await r.json();

    const img = document.getElementById('gate-result-img');
    const placeholder = document.getElementById('gate-empty-placeholder');
    const matchCard = document.getElementById('gate-match-card');
    const matchTitle = document.getElementById('gate-match-title');
    const matchDetails = document.getElementById('gate-match-details');

    if (r.ok && data.annotated_image) {
      if (img) {
        img.src = data.annotated_image;
        img.classList.remove('hidden');
      }
      if (placeholder) placeholder.classList.add('hidden');
      if (matchCard) matchCard.classList.remove('hidden');

      const matches = data.matches || [];
      if (matches.length === 0) {
        if (matchCard) matchCard.className = 'p-4 rounded-lg border text-xs space-y-1 border-rose-500/30 bg-rose-500/10';
        if (matchTitle) {
          matchTitle.className = 'font-bold text-sm flex items-center gap-2 text-rose-400';
          matchTitle.innerHTML = '<i data-lucide="x-circle" class="w-4 h-4"></i> ACCESS DENIED: Unregistered Visitor';
        }
        if (matchDetails) {
          matchDetails.innerHTML = 'Face detected, but biometric embedding does not match any registered worker.';
        }
        lucide.createIcons();
        showToast('🚫 Access Denied', 'Visitor not recognized in registered worker database.', 'rose', 4000);
      } else {
        const m = matches[0];
        const granted = m.access_status === 'Granted';
        if (matchCard) {
          matchCard.className = `p-4 rounded-lg border text-xs space-y-1 ${
            granted ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-rose-500/30 bg-rose-500/10'
          }`;
        }
        if (matchTitle) {
          matchTitle.className = `font-bold text-sm flex items-center gap-2 ${granted ? 'text-emerald-400' : 'text-rose-400'}`;
          matchTitle.innerHTML = `<i data-lucide="${granted ? 'check-circle' : 'x-circle'}" class="w-4 h-4"></i>
            ${granted ? 'ACCESS GRANTED' : 'ACCESS DENIED'}: ${m.matched_worker_name} (${m.matched_worker_code || '—'})`;
        }
        if (matchDetails) {
          matchDetails.innerHTML = `Role: ${m.role || '—'} | OSHA: ${m.osha_cert || '—'} | Match Confidence: ${((m.confidence||0)*100).toFixed(1)}%`;
        }
        lucide.createIcons();
        showToast(
          granted ? '✅ Access Granted' : '🚫 Access Denied',
          `${m.matched_worker_name} — ${((m.confidence||0)*100).toFixed(1)}% match`,
          granted ? 'emerald' : 'rose',
          5000
        );
        loadActiveRoster();
      }
    }
  } catch (e) {
    showToast('Error', e.message, 'rose', 4000);
  }
}

async function submitWorkerEnrollment(event) {
  event.preventDefault();
  const code = document.getElementById('enroll-code')?.value;
  const name = document.getElementById('enroll-name')?.value;
  const role = document.getElementById('enroll-role')?.value;
  const cert = document.getElementById('enroll-cert')?.value;
  const zones = document.getElementById('enroll-zones')?.value;
  const photoInput = document.getElementById('enroll-photo');

  if (!code || !name || !role || !zones) return;

  const formData = new FormData();
  formData.append('worker_code', code);
  formData.append('full_name', name);
  formData.append('role', role);
  formData.append('osha_cert', cert);
  formData.append('authorized_zones', zones);
  if (photoInput && photoInput.files.length) {
    formData.append('photo', photoInput.files[0]);
  }

  showToast('Enrolling...', `Computing 512-d ArcFace embedding for ${name}...`, 'sky', 3000);

  try {
    const r = await fetch('/api/v1/workers/enroll', { method: 'POST', body: formData });
    const data = await r.json();
    if (r.ok) {
      showToast('✅ Enrolled', `${name} (${code}) successfully registered with biometric.`, 'emerald', 4000);
      document.getElementById('enroll-form').reset();
      loadRegisteredWorkers();
      loadActiveRoster();
    } else {
      showToast('Enrollment Error', data.detail || 'Enrollment failed.', 'rose', 4000);
    }
  } catch (e) {
    showToast('Error', e.message, 'rose', 4000);
  }
}

// ============================================================
// 13. IoT ENVIRONMENTAL SENSORS
// ============================================================
async function loadIoTData() {
  try {
    const r = await fetch('/api/v1/iot/current');
    const data = await r.json();
    const vals = data.values || {};

    const tempVal = vals.temperature?.toFixed(1) ?? '--';
    const humidVal = vals.humidity?.toFixed(1) ?? '--';
    const dustVal = vals.dust?.toFixed(1) ?? '--';
    const gasVal = vals.gas?.toFixed(1) ?? '--';
    const noiseVal = vals.noise?.toFixed(1) ?? '--';

    setText('iot-temp', tempVal + ' °C');
    setText('iot-humid', humidVal + ' %');
    setText('iot-dust', dustVal + ' µg/m³');
    setText('iot-gas', gasVal + ' ppm');
    setText('iot-noise', noiseVal + ' dBA');

    // Color-code dangerous values
    colorSensorEl('iot-temp', vals.temperature, 40, 'text-orange-400', 'text-rose-500');
    colorSensorEl('iot-dust', vals.dust, 150, 'text-yellow-400', 'text-rose-500');
    colorSensorEl('iot-gas', vals.gas, 50, 'text-rose-400', 'text-rose-500');
    colorSensorEl('iot-noise', vals.noise, 85, 'text-sky-400', 'text-rose-500');

    // Show alerts if any
    const alerts = data.recent_alerts || [];
    alerts.forEach(a => {
      showToast(`⚠ SIMULATED IoT Alert: ${a.sensor}`, a.message, 'amber', 5000);
    });
  } catch (e) {
    console.error('IoT fetch error:', e);
  }
}

function colorSensorEl(id, value, threshold, normalClass, alertClass) {
  const el = document.getElementById(id);
  if (!el || value === null || value === undefined) return;
  el.classList.remove('text-orange-400', 'text-sky-400', 'text-yellow-400', 'text-rose-400',
                       'text-emerald-400', 'text-rose-500');
  if (value >= threshold) {
    el.classList.add(alertClass);
  } else {
    el.classList.add(normalClass);
  }
}

async function applyIoTPreset(presetName) {
  try {
    const r = await fetch('/api/v1/iot/preset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preset: presetName })
    });
    if (r.ok) {
      showToast('Scenario Applied', presetName, 'sky', 2500);
      await loadIoTData();
    }
  } catch (e) {
    showToast('IoT Error', e.message, 'rose', 3000);
  }
}

// ============================================================
// 14. SAFETY INCIDENTS TABLE
// ============================================================
async function loadIncidentsTable() {
  const statusFilter = document.getElementById('filter-incident-status')?.value || '';
  const priorityFilter = document.getElementById('filter-incident-priority')?.value || '';
  const search = (document.getElementById('incident-search')?.value || '').toLowerCase();

  let url = `/api/v1/incidents/?limit=200`;
  if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
  if (priorityFilter) url += `&priority=${encodeURIComponent(priorityFilter)}`;

  try {
    const r = await fetch(url);
    const data = await r.json();
    let events = Array.isArray(data) ? data : (data.events || []);

    // Client-side text search
    if (search) {
      events = events.filter(e =>
        (e.event_id + e.hazard_category + e.description + e.site_zone + e.event_type)
          .toLowerCase().includes(search)
      );
    }

    const tbody = document.getElementById('incidents-table-body');
    if (!tbody) return;

    if (!events.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="py-8 text-center text-slate-500">No incidents match the current filters.</td></tr>';
      return;
    }

    tbody.innerHTML = events.map(evt => `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-2.5 px-4 mono font-semibold text-sky-400 text-[11px]">${evt.event_id}</td>
        <td class="py-2.5 px-4 text-slate-400 text-[11px]">${formatTime(evt.timestamp)}</td>
        <td class="py-2.5 px-4 text-slate-200 text-[11px]">
          <div class="font-semibold">${evt.hazard_category}</div>
          <div class="text-slate-500 text-[10px]">${evt.event_type}</div>
        </td>
        <td class="py-2.5 px-4">${priorityBadge(evt.priority)}</td>
        <td class="py-2.5 px-4 text-slate-400 text-[11px]">${evt.site_zone}</td>
        <td class="py-2.5 px-4">${statusBadge(evt.status)}</td>
        <td class="py-2.5 px-4 text-right">
          <div class="flex items-center justify-end gap-1.5 flex-wrap">
            ${evt.evidence_path ? `<a href="/evidence/${evidenceFilename(evt.evidence_path)}" target="_blank" class="btn-action btn-action-sky">View Evidence</a>` : ''}
            ${evt.status === 'Open' ? `<button onclick="updateEventStatus('${evt.event_id}', 'Acknowledged')" class="btn-action btn-action-amber">Acknowledge</button>` : ''}
            ${evt.status !== 'Resolved' ? `<button onclick="updateEventStatus('${evt.event_id}', 'Resolved')" class="btn-action btn-action-emerald">Resolve</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Incidents load error:', e);
  }
}

async function updateEventStatus(eventId, newStatus) {
  try {
    const r = await fetch(`/api/v1/incidents/${encodeURIComponent(eventId)}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (r.ok) {
      showToast('Status Updated', `${eventId} → ${newStatus}`, 'emerald', 2500);
      loadIncidentsTable();
      fetchDashboardStats().then(updateKpiTiles);
    } else {
      showToast('Update Failed', 'Could not update incident status.', 'rose', 3000);
    }
  } catch (e) {
    showToast('Error', e.message, 'rose', 3000);
  }
}

function evidenceFilename(path) {
  if (!path) return '';
  return path.replace(/\\/g, '/').split('/').pop();
}

// ============================================================
// 15. OSHA REGULATIONS
// ============================================================
async function loadRegulations() {
  const container = document.getElementById('regulations-container');
  if (!container) return;

  if (container.dataset.loaded) return; // Load only once

  try {
    const r = await fetch('/api/v1/regulations/');
    const data = await r.json();
    const rawList = Array.isArray(data) ? data : (data.standards || []);

    if (!rawList.length) {
      container.innerHTML = '<p class="text-slate-500 col-span-2">No regulations available.</p>';
      return;
    }

    const standards = rawList.map(s => ({
      hazard_category: s.hazard_category || '',
      standard_ref: s.code || s.standard_ref || '',
      title: s.title || s.hazard_category || '',
      explanation: s.summary || s.explanation || '',
      recommended_action: s.recommended_action || '',
      source_url: s.official_url || s.source_url || '#'
    }));

    const hazardIcons = {
      'Head Protection': '⛑',
      'Personal Protective Equipment': '🦺',
      'Fall Protection': '🪂',
      'Excavations': '⛏',
      'Cranes and Derricks': '🏗',
      'Respiratory Protection': '😷',
      'Eye and Face Protection': '🥽',
    };

    container.innerHTML = standards.map(s => `
      <div class="glass-panel p-5 space-y-3">
        <div class="flex items-start justify-between gap-2">
          <div>
            <div class="text-lg">${hazardIcons[s.hazard_category] || '📋'}</div>
            <div class="mono text-xs font-bold text-sky-400 mt-1">${s.standard_ref}</div>
            <div class="font-bold text-sm text-slate-200 mt-1">${s.title || s.hazard_category}</div>
          </div>
          <span class="badge-pill badge-low shrink-0 text-[10px]">${s.hazard_category}</span>
        </div>
        <p class="text-xs text-slate-400 leading-relaxed">${s.explanation}</p>
        <div class="bg-emerald-900/20 border border-emerald-700/30 rounded-lg p-3">
          <div class="text-[11px] font-bold text-emerald-400 mb-1">Recommended Action</div>
          <div class="text-xs text-slate-300">${s.recommended_action}</div>
        </div>
        <a href="${s.source_url}" target="_blank" rel="noopener"
           class="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 hover:underline">
          📎 Official OSHA Source <span class="text-slate-500">→</span>
        </a>
        <div class="text-[10px] text-slate-600 italic mt-1">This is an OSHA-aligned demonstration reference, not a certified compliance determination.</div>
      </div>
    `).join('');

    container.dataset.loaded = '1';
  } catch (e) {
    container.innerHTML = '<p class="text-slate-500 col-span-2">Failed to load regulations.</p>';
  }
}

// ============================================================
// 16. TOAST NOTIFICATIONS
// ============================================================
function showToast(title, body, color = 'sky', durationMs = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const colorMap = {
    sky:     { border: 'border-sky-500/50',     dot: 'bg-sky-400',     title: 'text-sky-300' },
    emerald: { border: 'border-emerald-500/50', dot: 'bg-emerald-400', title: 'text-emerald-300' },
    amber:   { border: 'border-amber-500/50',   dot: 'bg-amber-400',   title: 'text-amber-300' },
    rose:    { border: 'border-rose-500/50',     dot: 'bg-rose-400',    title: 'text-rose-300' },
    cyan:    { border: 'border-cyan-500/50',     dot: 'bg-cyan-400',    title: 'text-cyan-300' },
  };

  const c = colorMap[color] || colorMap.sky;
  const id = 'toast-' + Date.now();

  const toast = document.createElement('div');
  toast.id = id;
  toast.className = `pointer-events-auto bg-slate-900/95 backdrop-blur-md border ${c.border} 
    rounded-lg shadow-2xl p-3.5 flex gap-3 items-start transform translate-x-full opacity-0 
    transition-all duration-300 ease-out`;

  toast.innerHTML = `
    <div class="w-2 h-2 rounded-full ${c.dot} mt-1 shrink-0 animate-pulse"></div>
    <div class="flex-1 min-w-0">
      <div class="font-bold text-xs ${c.title} truncate">${title}</div>
      <div class="text-[11px] text-slate-400 mt-0.5 line-clamp-2">${body}</div>
    </div>
    <button onclick="document.getElementById('${id}').remove()" class="text-slate-600 hover:text-slate-400 text-xs shrink-0">✕</button>
  `;

  container.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      toast.classList.remove('translate-x-full', 'opacity-0');
      toast.classList.add('translate-x-0', 'opacity-100');
    });
  });

  // Auto remove
  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-x-full');
    setTimeout(() => toast.remove(), 300);
  }, durationMs);
}

// ============================================================
// 17. AUDIO ALERTS
// ============================================================
function initAudioToggle() {
  const btn = document.getElementById('btn-audio-toggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    App.audioEnabled = !App.audioEnabled;
    const textEl = document.getElementById('audio-status-text');
    if (textEl) textEl.textContent = App.audioEnabled ? 'Audio Alert: ON' : 'Audio Alert: OFF';
    btn.classList.toggle('opacity-50', !App.audioEnabled);
  });
}

function playAlertTone(severity = 'medium') {
  try {
    if (!App.audioCtx) App.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const ctx = App.audioCtx;

    const freqs = { critical: [880, 660, 880], high: [660, 440], medium: [440], low: [330] };
    const tones = freqs[severity] || freqs.medium;
    let startTime = ctx.currentTime;

    tones.forEach(freq => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = freq;
      osc.type = 'sine';
      gain.gain.setValueAtTime(0.15, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.25);
      osc.start(startTime);
      osc.stop(startTime + 0.26);
      startTime += 0.28;
    });
  } catch (_) {}
}

// ============================================================
// 18. UTILITY HELPERS
// ============================================================
function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function formatTime(isoStr) {
  if (!isoStr) return '—';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
  } catch (_) { return isoStr; }
}

function priorityBadge(priority) {
  const map = {
    'Critical': 'badge-critical',
    'High':     'badge-high',
    'Medium':   'badge-medium',
    'Low':      'badge-low',
  };
  return `<span class="badge-pill ${map[priority] || 'badge-low'}">${priority || '—'}</span>`;
}

function statusBadge(status) {
  const map = {
    'Open':         'badge-open',
    'Acknowledged': 'badge-acknowledged',
    'Resolved':     'badge-resolved',
  };
  return `<span class="badge-pill ${map[status] || 'badge-low'}">${status || '—'}</span>`;
}
