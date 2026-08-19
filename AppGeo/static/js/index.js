// ── Config ────────────────────────────────────────────────────────────────────
const API_BASE    = "http://localhost:8001";
const STREAM_URL  = "http://localhost:8000/geojson/municipios/stream?tolerance=0.005";

// ── Mapa ──────────────────────────────────────────────────────────────────────
const map = L.map("map", { zoomControl: true, attributionControl: false });
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  maxZoom: 19, subdomains: "abcd"
}).addTo(map);

const styleDefault = { color:"#1a3a55", weight:0.8, opacity:0.6, fillColor:"#1a3a55", fillOpacity:0.12 };
const styleActive  = { color:"#00e5a0", weight:2.2, opacity:1,   fillColor:"#00e5a0", fillOpacity:0.22 };

let allFeatures  = [];
let layerMap     = {};
let globalBounds = null;

// Camada dos municípios base (não selecionados)
const visibleLayer = L.geoJSON(null, {
  style: () => styleDefault,
  onEachFeature(feature, layer) {
    const p = feature.properties;
    layerMap[p.cd_mun] = layer;
    layer.on({
      mouseover(e) {
        if (!layer._highlighted) layer.setStyle({ ...styleDefault, fillOpacity: 0.28, color:"#38bdf8" });
        layer.bindTooltip(
          `<b>${p.nm_mun}</b><br>${p.area_km2 ? p.area_km2.toFixed(0) + " km²" : ""}`,
          { sticky: true, direction: "auto" }
        ).openTooltip(e.latlng);
      },
      mouseout() {
        if (!layer._highlighted) layer.setStyle(styleDefault);
        layer.closeTooltip();
      },
    });
  },
}).addTo(map);

// Camada de destaque (resultado do agente)
const highlightLayer = L.geoJSON(null, {
  style: () => styleActive,
  onEachFeature(feature, layer) {
    const p = feature.properties;
    layer._highlighted = true;
    layer.on({
      click() {
        layer.bindPopup(`
          <b>${p.nm_mun}</b>
          Código IBGE: ${p.cd_mun}<br>
          Estado: ${p.nm_uf || "—"}<br>
          Área: ${p.area_km2 ? p.area_km2.toFixed(2) + " km²" : "—"}
        `).openPopup();
      },
      mouseover(e) {
        layer.setStyle({ ...styleActive, fillOpacity: 0.4, weight: 3 });
        layer.bindTooltip(
          `<b>${p.nm_mun}</b><br>${p.nm_uf} · ${p.area_km2 ? p.area_km2.toFixed(0) + " km²" : ""}`,
          { sticky: true, direction: "auto" }
        ).openTooltip(e.latlng);
      },
      mouseout() {
        layer.setStyle(styleActive);
        layer.closeTooltip();
      },
    });
  },
}).addTo(map);

// ── Viewport culling ──────────────────────────────────────────────────────────
let debounceTimer;
function refreshViewport() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    const bounds = map.getBounds().pad(0.1);
    const inView = allFeatures.filter(f => {
      const b = f._bbox;
      return b && bounds.overlaps(L.latLngBounds([b[1],b[0]], [b[3],b[2]]));
    });
    visibleLayer.clearLayers();
    layerMap = {};
    visibleLayer.addData({ type:"FeatureCollection", features:inView });
  }, 150);
}
map.on("moveend zoomend", refreshViewport);

// ── Utilitários ───────────────────────────────────────────────────────────────
function calcBbox(feature) {
  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  function walk(c) {
    if (typeof c[0]==="number") {
      if (c[0]<minX) minX=c[0]; if (c[0]>maxX) maxX=c[0];
      if (c[1]<minY) minY=c[1]; if (c[1]>maxY) maxY=c[1];
    } else c.forEach(walk);
  }
  if (feature.geometry?.coordinates) walk(feature.geometry.coordinates);
  else return null;
  return [minX,minY,maxX,maxY];
}

// ── Carregamento inicial do mapa ──────────────────────────────────────────────
async function loadBaseMap() {
  const loadingEl = document.getElementById("loading");
  const loadingP  = loadingEl.querySelector("p");
  try {
    const res = await fetch(STREAM_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";
    let   count   = 0;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();
      for (const line of lines) {
        const trimmed = line.replace(/^,/, "").trim();
        if (!trimmed.startsWith("{")) continue;
        try {
          const feature = JSON.parse(trimmed);
          if (feature.type !== "Feature") continue;
          feature._bbox = calcBbox(feature);
          if (feature._bbox) {
            const b  = feature._bbox;
            const fb = L.latLngBounds([b[1],b[0]], [b[3],b[2]]);
            globalBounds = globalBounds ? globalBounds.extend(fb) : fb;
          }
          allFeatures.push(feature);
          count++;
          if (count % 50 === 0) loadingP.textContent = `Carregando… ${count} municípios`;
        } catch(_) {}
      }
    }
    if (globalBounds) map.fitBounds(globalBounds, { padding:[20,20] });
    refreshViewport();
  } catch(err) {
    loadingEl.innerHTML = `<p style="color:#f87171">Erro ao carregar mapa.<br><small>${err.message}</small></p>`;
    return;
  }
  loadingEl.classList.add("hidden");
}
loadBaseMap();

// ── Chat ──────────────────────────────────────────────────────────────────────
let activeChart = null;

function sendExample(btn) {
  document.getElementById("question-input").value = btn.textContent.trim();
  sendQuestion();
}

function autoResize(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 110) + "px";
}

document.getElementById("question-input").addEventListener("input", function() {
  autoResize(this);
});

document.getElementById("question-input").addEventListener("keydown", function(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendQuestion();
  }
});

document.querySelectorAll(".example-btn").forEach((btn) => {
  btn.addEventListener("click", () => sendExample(btn));
});

document.getElementById("send-btn").addEventListener("click", sendQuestion);

async function sendQuestion() {
  const input    = document.getElementById("question-input");
  const question = input.value.trim();
  if (!question) return;

  // Remove welcome screen se ainda visível
  const welcome = document.getElementById("welcome-screen");
  if (welcome) welcome.remove();

  input.value = "";
  input.style.height = "auto";
  document.getElementById("send-btn").disabled = true;

  const history = document.getElementById("chat-history");

  // Mensagem do usuário
  appendMsg("user", `<div class="bubble">${escHtml(question)}</div>`);

  // Placeholder "pensando"
  const aiId = "ai-" + Date.now();
  appendMsg("ai", `
    <div class="label thinking" id="lbl-${aiId}">GeoIA — pensando…</div>
    <div class="answer-text" id="ans-${aiId}">
      <span style="color:var(--muted)">⏳ Consultando banco de dados…</span>
    </div>
  `, aiId);

  history.scrollTop = history.scrollHeight;

  try {
    // 1. Chama /ask para texto + dados do gráfico
    const askRes = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!askRes.ok) throw new Error(`HTTP ${askRes.status}`);
    const data = await askRes.json();

    // Atualiza label
    document.getElementById(`lbl-${aiId}`).textContent = "GeoIA";
    document.getElementById(`lbl-${aiId}`).classList.remove("thinking");

    // Resposta textual + SQL
    const ansEl = document.getElementById(`ans-${aiId}`);
    ansEl.innerHTML = `
      ${escHtml(data.answer)}
      <div style="margin-top:8px">
        <div class="sql-pill" title="Clique para copiar" onclick="copyText(this, \`${escAttr(data.sql)}\`)">${escHtml(data.sql)}</div>
      </div>
    `;

    // Gráfico (se disponível)
    if (data.chart && data.chart.labels && data.chart.labels.length > 1) {
      const chartEl = document.createElement("div");
      chartEl.className = "chart-wrap";
      chartEl.innerHTML = `<canvas id="chart-${aiId}"></canvas>`;
      document.getElementById(aiId).appendChild(chartEl);

      if (activeChart) { activeChart.destroy(); activeChart = null; }
      activeChart = new Chart(document.getElementById(`chart-${aiId}`), {
        type: "bar",
        data: {
          labels: data.chart.labels,
          datasets: [{
            label: data.chart.y_label,
            data:  data.chart.values,
            backgroundColor: "rgba(0,229,160,.25)",
            borderColor:     "rgba(0,229,160,.8)",
            borderWidth: 1,
            borderRadius: 3,
          }]
        },
        options: {
          responsive: true,
          animation: { duration: 500 },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: "#0d1625",
              borderColor: "#1a2d45",
              borderWidth: 1,
              titleColor: "#00e5a0",
              bodyColor: "#dce8f5",
            }
          },
          scales: {
            x: {
              ticks: { color:"#4d6a85", font:{ size:9 }, maxRotation:35 },
              grid:  { color:"#1a2d45" },
            },
            y: {
              ticks: { color:"#4d6a85", font:{ size:9 } },
              grid:  { color:"#1a2d45" },
            }
          }
        }
      });
    }

    // 2. Chama /ask/geojson para destacar no mapa
    try {
      // Envia o mesmo SQL do /ask — garante que os municípios destacados
      // sejam exatamente os mesmos do resultado (sem nova chamada ao LLM)
      const geoRes = await fetch(`${API_BASE}/ask/geojson`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, sql: data.sql }),
      });
      if (geoRes.ok) {
        const geoData = await geoRes.json();
        if (geoData.features && geoData.features.length > 0) {
          highlightLayer.clearLayers();
          highlightLayer.addData(geoData);
          const bounds = highlightLayer.getBounds();
          if (bounds.isValid()) map.fitBounds(bounds, { padding:[40,40], maxZoom:9 });

          const cdMuns    = geoData.features.map(f => f.properties.cd_mun);
          const count     = geoData.features.length;
          const aiMsgEl   = document.getElementById(aiId);

          // Notícia no mapa
          const noticeEl = document.createElement("div");
          noticeEl.className = "map-notice";
          noticeEl.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
            </svg>
            ${count} município${count>1?"s":""} destacado${count>1?"s":""} no mapa
          `;
          aiMsgEl.appendChild(noticeEl);

          // Botão de download shapefile
          const dlBtn = document.createElement("button");
          dlBtn.className = "download-btn";
          dlBtn.innerHTML = `
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Baixar Shapefile (${count} município${count>1?"s":""})
          `;
          dlBtn.onclick = () => downloadShapefile(cdMuns, question, dlBtn);
          aiMsgEl.appendChild(dlBtn);

          // Atualiza badge do header
          const statusEl = document.getElementById("map-status");
          statusEl.textContent = `${count} destacado${count>1?"s":""}`;
          statusEl.classList.add("active");
        }
      }
    } catch(_) { /* silencia falha de geojson */ }

  } catch(err) {
    document.getElementById(`lbl-${aiId}`).textContent = "Erro";
    document.getElementById(`lbl-${aiId}`).classList.remove("thinking");
    document.getElementById(`ans-${aiId}`).innerHTML =
      `<div class="error-msg">❌ ${escHtml(err.message)}</div>`;
  }

  document.getElementById("send-btn").disabled = false;
  history.scrollTop = history.scrollHeight;
}

function appendMsg(role, html, id) {
  const history = document.getElementById("chat-history");
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  if (id) div.id = id;
  div.innerHTML = html;
  history.appendChild(div);
}

function escHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;")
    .replace(/</g,"&lt;")
    .replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;");
}
function escAttr(str) {
  return String(str).replace(/`/g,"\\`").replace(/\\/g,"\\\\");
}

async function copyText(el, text) {
  try {
    await navigator.clipboard.writeText(text);
    const orig = el.style.color;
    el.style.color = "var(--accent)";
    setTimeout(() => el.style.color = orig, 800);
  } catch(_) {}
}

async function downloadShapefile(cdMuns, question, btn) {
  btn.disabled = true;
  const origHtml = btn.innerHTML;
  btn.innerHTML = `
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin .7s linear infinite">
      <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
    </svg>
    Gerando arquivo…
  `;

  // Gera filename a partir da pergunta (primeiras 40 letras, sem espaços)
  const filename = question.replace(/[^a-zA-Z0-9À-ú ]/g, "").trim().slice(0, 40).replace(/ +/g, "_") || "resultado";

  try {
    const res = await fetch(`${API_BASE}/download/shapefile/result`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cd_muns: cdMuns, filename }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `${filename}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    btn.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="20 6 9 17 4 12"/>
      </svg>
      Download concluído!
    `;
    setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; }, 3000);

  } catch(err) {
    btn.innerHTML = `❌ Erro: ${escHtml(err.message)}`;
    btn.style.color = "#fca5a5";
    btn.style.borderColor = "rgba(239,68,68,.3)";
    setTimeout(() => { btn.innerHTML = origHtml; btn.disabled = false; btn.style.color = ""; btn.style.borderColor = ""; }, 4000);
  }
}
