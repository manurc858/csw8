// ───── Referencias DOM ─────
const angleInput = document.getElementById("angleInput");
const tempInput = document.getElementById("tempInput");
const updateBtn = document.getElementById("updateBtn");
const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");
const osdC = document.getElementById("osdContainer");
const plot3d = document.getElementById("plot3d");
const titleInput = document.getElementById("chartTitle");
const descInput = document.getElementById("chartDesc");

// ───── Estado global ─────
let viewer = null; // Visualizador 2D (OpenSeadragon)

// ───── Utilidades ─────
const toRad = deg => deg * Math.PI / 180;

// ───── Función: Actualizar carta solar ─────
async function requestChart() {
  const angleVal = parseFloat(angleInput.value) || 0;
  const tminVal = parseFloat(tempInput.value) || -273.15;

  statusEl.textContent = "Generando carta…";
  statusEl.classList.remove("error");
  updateBtn.disabled = true;

  // EXTRAER project ID desde la URL
  const urlParts = window.location.pathname.split("/");
  const projId = urlParts[2];

  const res = await fetch(`/api/carta-solar?project=${projId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      angle: angleVal,
      tmin: tminVal,
      shades: window.shadeList
    })
  });

  if (!res.ok) {
    statusEl.textContent = "⛔ " + (await res.text());
    statusEl.classList.add("error");
    updateBtn.disabled = false;
    return;
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);

  if (viewer) viewer.destroy();
  viewer = OpenSeadragon({
    element: osdC,
    prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.0/images/",
    tileSources: { type: "image", url },
    maxZoomPixelRatio: 4,
    gestureSettingsMouse: { clickToZoom: false }
  });

  /* ─── Overlay de sombras en OpenSeadragon 2-D ─────────────────────────── */
  viewer.addHandler("open", function () {

    viewer.clearOverlays();

    /* Datos básicos de la imagen/carta */
    const size = viewer.world.getItemAt(0).getContentSize();
    const cx = size.x / 2;
    const cy = size.y / 2;
    const R = Math.min(cx, cy);   // radio exacto del disco
    const safeR = R - 0.5;            // medio píxel de margen

    /* deg → (x,y) */
    const polarToPx = deg => {
      const rad = deg * Math.PI / 180;
      return {
        x: cx + safeR * Math.cos(rad),
        y: cy - safeR * Math.sin(rad)
      };
    };

    /* Proyecta |p−c| al disco si se pasa */
    const clamp = p => {
      const dx = p.x - cx, dy = p.y - cy;
      const d = Math.hypot(dx, dy);
      if (d > safeR) {
        const k = safeR / d;
        return { x: cx + dx * k, y: cy + dy * k };
      }
      return p;
    };

    /* Construye vértices */
    const pts = (window.shadeList || []).map(sh => {
      if (sh.type === 'h') {
        /* ϕ = (azimut fachada + 90°) − θ_visera  → [0,360) */
        const az = Number(sh.orient) || 0;
        const phi = ((az + 90) - sh.extra + 360) % 360;
        return clamp(polarToPx(phi));
      }
      /* verticales u otros */
      return clamp(polarToPx(sh.extra));
    });

    if (pts.length) {
      const svgNS = "http://www.w3.org/2000/svg";
      const poly = document.createElementNS(svgNS, "polygon");
      poly.setAttribute("points", pts.map(p => `${p.x},${p.y}`).join(" "));
      poly.setAttribute("fill", "rgba(255,0,0,0.4)");
      viewer.addOverlay({ element: poly, location: pts });
    }
  });


  statusEl.textContent = "Listo.";
  updateBtn.disabled = false;
  draw3D();
}

// ───── Función: Guardar cambios ─────
async function saveChart() {
  try {
    updatePlotAndShades(); // Asumiendo que esta función genera las sombras y las coloca
    const container = document.getElementById('osdContainer');
    const canvas = await html2canvas(container);
    const previewData = canvas.toDataURL('image/png');
    const payload = {
      angle: parseFloat(angleInput.value),
      temp: parseFloat(tempInput.value),
      shades: window.shadeList,
      title: titleInput.value,
      description: descInput.value,
      hHeight: parseFloat(document.getElementById('hHeight').value),
      hLength: parseFloat(document.getElementById('hLength').value),
      chkH: document.getElementById('chkH').checked,
      vLength: parseFloat(document.getElementById('vLength').value),
      vWidth: parseFloat(document.getElementById('vWidth').value),
      vSide: document.getElementById('vSide').value,
      chkV: document.getElementById('chkV').checked,
      preview: previewData
    };

    const urlParts = window.location.pathname.split("/");
    const projId = urlParts[2];
    const chartId = urlParts[4];

    const response = await fetch(`/projects/${projId}/solar-charts/${chartId}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!response.ok) throw new Error("Error al guardar la carta solar");

    const result = await response.json();
    statusEl.textContent = result.message || "✔ Guardado con éxito";

  } catch (err) {
    console.error(err);
    statusEl.textContent = "❌ Error al guardar";
  }
}

// ───── Función: Actualizar visualización ─────
function updateUI(data) {
  console.log("Datos de actualización recibidos:", data);
  // Aquí podrías redibujar el gráfico, actualizar visual, etc.
}

async function draw3D() {
  const parts = window.location.pathname.split("/");
  const projId = parts[2];

  // ❶ Pedimos datos al backend, incluyendo el project ID
  const res = await fetch(`/api/solar-data?project=${projId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tmin: tempInput.value })
  });

  if (!res.ok) {
    statusEl.textContent = "⛔ " + (await res.text());
    statusEl.classList.add("error");
    plot3d.style.display = "none";
    return;
  }
  const d = await res.json();

  /* ─── trazos del 21 de cada mes ───────────── */
  const day21Traces = (d.day21 || []).map(seg => {
    const azL = seg.azi.map(toRad);
    const elL = seg.elev.map(toRad);
    return {
      type: "scatter3d",
      mode: "lines",
      x: elL.map((e, i) => Math.cos(e) * Math.sin(azL[i])),
      y: elL.map((e, i) => Math.cos(e) * Math.cos(azL[i])),
      z: elL.map(e => Math.sin(e)),
      line: { width: 1, color: "dimgray" },
      hoverinfo: "skip",
      showlegend: false
    };
  });

  /* Coordenadas cartesianas de todos los puntos */
  const azR = d.azi.map(toRad), elR = d.elev.map(toRad);
  const x = elR.map((e, i) => Math.cos(e) * Math.sin(azR[i]));
  const y = elR.map((e, i) => Math.cos(e) * Math.cos(azR[i]));
  const z = elR.map(e => Math.sin(e));

  const tracePts = {
    type: "scatter3d", mode: "markers", x, y, z,
    marker: {
      size: 2,
      color: d.temp,
      colorscale: "Turbo",
      showscale: true,
      colorbar: { title: "T (°C)" }
    },
    hovertemplate:
      "Az %{customdata[0]:.1f}°<br>El %{customdata[1]:.1f}°<br>T %{marker.color:.1f}°C",
    customdata: d.azi.map((a, i) => [a, d.elev[i]])
  };

  /* Hemisferio translúcido */
  function hemi(n = 30) {
    const u = [], v = [], w = [];
    for (let i = 0; i <= n; i++) {
      u[i] = []; v[i] = []; w[i] = [];
      const th = i * Math.PI / 2 / n;
      for (let j = 0; j <= n; j++) {
        const ph = j * 2 * Math.PI / n, r = Math.cos(th);
        u[i][j] = r * Math.sin(ph);
        v[i][j] = r * Math.cos(ph);
        w[i][j] = Math.sin(th);
      }
    }
    return {
      type: "surface", x: u, y: v, z: w,
      opacity: 0.12, showscale: false,
      colorscale: [['0', 'lightgray'], ['1', 'lightgray']]
    };
  }

  /* Circunferencias suelo cada 10° */
  const rings = [];
  for (let elev = 10; elev < 90; elev += 10) {
    const r = Math.cos(toRad(elev));
    const phi = [...Array(361).keys()].map(a => toRad(a));
    rings.push({
      type: "scatter3d", mode: "lines",
      x: phi.map(p => r * Math.sin(p)),
      y: phi.map(p => r * Math.cos(p)),
      z: phi.map(() => 0),
      line: { width: 1, color: "lightgray", dash: "dot" },
      hoverinfo: "skip", showlegend: false
    });
  }

  Plotly.react("plot3d",
    [tracePts, hemi(), ...rings, ...day21Traces],
    {
      scene: { aspectmode: "data" },
      margin: { l: 0, r: 0, b: 0, t: 0 },
      width: 400, height: 280
    }
  );
  plot3d.style.display = "block";
}

// ───── Precarga de datos de carta guardada ─────
async function preloadChartData() {
  let data;
  try {
    // 1. Extraer IDs de la URL
    const parts = window.location.pathname.split("/");
    const projId = parts[2];
    const chartId = parts[4];

    // 2. Pedir datos al backend
    const res = await fetch(`/projects/${projId}/solar-charts/${chartId}/data`);
    if (!res.ok) throw new Error("No se pudo cargar la carta solar");

    // 3. Leer JSON
    data = await res.json();

    // 4. Rellenar inputs con los datos cargados
    titleInput.value = data.title ?? "";
    descInput.value = data.description ?? "";
    angleInput.value = data.angle ?? 0;
    tempInput.value = data.temp ?? 0;

    // 5. Voladizo horizontal
    document.getElementById("chkH").checked = Boolean(data.chkH);
    document.getElementById("hHeight").value = data.hHeight ?? 1.5;
    document.getElementById("hLength").value = data.hLength ?? 0;

    // 6. Voladizo vertical
    document.getElementById("chkV").checked = Boolean(data.chkV);
    document.getElementById("vWidth").value = data.vWidth ?? 1.5;
    document.getElementById("vLength").value = data.vLength ?? 0;
    document.getElementById("vSide").value = data.vSide || "left";

    // 7. Asignar lista de sombras global
    window.shadeList = Array.isArray(data.shades) ? data.shades : [];

    statusEl.textContent = "✅ Datos precargados";

    // 8. Recalcular sombras 3D y actualizar carta 2D
    updatePlotAndShades();
    requestChart();

  } catch (err) {
    console.error(err);
    statusEl.textContent = "❌ Error al precargar";
    // No continuar con requestChart() si falla la carga
  }
}

document.addEventListener("DOMContentLoaded", preloadChartData);
if (updateBtn) {
  updateBtn.addEventListener("click", () => {
    updatePlotAndShades();   // 1️⃣ llena window.shadeList y dibuja voladizos
    requestChart();          // 2️⃣ envía los datos al backend y refresca OSD
  });
}
if (saveBtn) saveBtn.addEventListener("click", saveChart);
requestChart();
