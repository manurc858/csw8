/* global Plotly */
/* ─── PlotlyVol.js  ·  Gestión 3-D de voladizos y ventana (dinámico) ───────────── */

// Variables globales para primeros renderizados
let pv_firstPlot = true;
const WALL_WIDTH = 4;
const WALL_HEIGHT = 3;

// Utilidades para generar superficies Plotly
function surf(x, y, z, color, op = 1) {
  return {
    type: 'surface', x, y, z, showscale: false,
    colorscale: [[0, color], [1, color]], opacity: op,
    hoverinfo: 'skip'
  };
}

// Generación de muro
function createWall(winW, winH, winLeft, winBottom) {
  const p = (x0, x1, z0, z1) =>
    surf([[x0, x1], [x0, x1]], [[0, 0], [0, 0]], [[z0, z0], [z1, z1]], 'lightgray');
  return [
    p(0, WALL_WIDTH, 0, winBottom),
    p(0, WALL_WIDTH, winBottom + winH, WALL_HEIGHT),
    p(0, winLeft, winBottom, winBottom + winH),
    p(winLeft + winW, WALL_WIDTH, winBottom, winBottom + winH)
  ];
}


// Generación de ventana
function createWindow(winW, winH, winLeft, winBottom) {
  // 1. Calcula los extremos de la ventana
  const x0 = winLeft;
  const x1 = winLeft + winW;
  const z0 = winBottom;
  const z1 = winBottom + winH;
  const y0 = 0; // La ventana siempre en la pared

  // 2. Cara de la ventana (plano semi-transparente)
  const face = surf(
    [[x0, x1], [x0, x1]],   // X desde x0 hasta x1
    [[y0, y0], [y0, y0]],   // Y fijo en la pared
    [[z0, z0], [z1, z1]],   // Z desde z0 hasta z1
    'cyan', 0.45
  );

  // 3. Marco de la ventana (líneas perimetrales)
  const frame = {
    type: 'scatter3d',
    mode: 'lines',
    x: [x0, x1, x1, x0, x0],
    y: [y0, y0, y0, y0, y0],
    z: [z0, z0, z1, z1, z0],
    line: { width: 5, color: 'blue' },
    hoverinfo: 'skip',
    showlegend: false
  };

  return [face, frame];
}


function createOverhangH(len, winW, winH, winLeft, winBottom) {
  return surf(
    [[0, WALL_WIDTH], [0, WALL_WIDTH]],
    [[0, 0], [len, len]],
    [[winBottom + winH, winBottom + winH], [winBottom + winH, winBottom + winH]],
    'red'
  );
}

function createOverhangV(len, side, winH, winLeft, winBottom, vWidth) {
  const x0 = side === 'right' ? winLeft + vWidth : winLeft;
  return surf(
    [[x0, x0], [x0, x0]],
    [[0, 0], [len, len]],
    [[0, WALL_HEIGHT], [0, WALL_HEIGHT]],
    'red'
  );
}



// Función principal para renderizar sombras 3D y actualizar lista global
window.updatePlotAndShades = function updatePlotAndShades() {
  const chkH = document.getElementById('chkH');
  const chkV = document.getElementById('chkV');
  const hLen = document.getElementById('hLength');
  const hHigh = document.getElementById('hHeight');
  const vSide = document.getElementById('vSide');
  const vLen = document.getElementById('vLength');
  const vWidthEl = document.getElementById('vWidth');
  const plotEl = document.getElementById('shadeDiagram');
  const angleEl = document.getElementById('shadeAngle');

  // Reset
  window.shadeList = [];

  // Valores de la ventana
  const wRaw = parseFloat(vWidthEl.value);
  const hRaw = parseFloat(hHigh.value);
  const wWin = isNaN(wRaw) || wRaw <= 0 ? 1.5 : wRaw;
  const hWin = isNaN(hRaw) || hRaw <= 0 ? 1.5 : hRaw;

  // Coordenadas dinámicas base de ventana
  const winLeft = 1.25;
  const winBottom = 0.75;

  let data = [
    ...createWall(wWin, hWin, winLeft, winBottom),
    ...createWindow(wWin, hWin, winLeft, winBottom)
  ];
  let angles = [];

  if (chkH.checked) {
    const lenH = parseFloat(hLen.value) || 0;
    if (lenH > 0) {
      const angH = Math.atan(lenH / hWin) * 180 / Math.PI;
      data.push(createOverhangH(lenH, wWin, hWin, winLeft, winBottom));
      window.shadeList.push({ type: 'h', extra: angH, orient: window.currentOrient || 0, side: null });
      angles.push(`H: ${angH.toFixed(1)}°`);
    }
  }

  if (chkV.checked) {
    const lenV = parseFloat(vLen.value) || 0;
    const side = vSide.value;
    const vWidth = parseFloat(vWidthEl.value) || hWin;
    if (lenV > 0) {
      const angV = Math.atan(lenV / wWin) * 180 / Math.PI;
      data.push(createOverhangV(lenV, side, hWin, winLeft, winBottom, vWidth));
      window.shadeList.push({ type: 'v', extra: angV, side: side });
      angles.push(`${side === 'right' ? 'D' : 'I'}: ${angV.toFixed(1)}°`);
    }
  }

  // Mostrar ángulos en UI
  angleEl.textContent = angles.join('   ');
  angleEl.classList.remove('error');

  // Plotly render
  const layout = {
    scene: { xaxis: { visible: false }, yaxis: { visible: false }, zaxis: { visible: false }, aspectmode: 'data' },
    margin: { l: 0, r: 0, t: 0, b: 0 }
  };
  if (pv_firstPlot) {
    Plotly.newPlot(plotEl, data, layout, { displayModeBar: false });
    pv_firstPlot = false;
  } else {
    Plotly.react(plotEl, data, layout);
    Plotly.relayout(plotEl, {
      'scene.xaxis.autorange': true,
      'scene.yaxis.autorange': true,
      'scene.zaxis.autorange': true
    });
  }
};
