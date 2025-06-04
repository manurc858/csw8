/* ─────────────────────────────────────────────────────────────
   solar_charts.js 
   ───────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  document.title = `Cartas Solares – ${PROJECT_NAME}`;
  loadProjectsInSidebar();
  loadCurrentProject();
  setupEventListeners();
});

/* ────────────────────────────────────────────────────────── */
/*  CARGA DE PROYECTOS EN LA SIDEBAR                         */
/* ────────────────────────────────────────────────────────── */
async function loadProjectsInSidebar() {
  const projects = await fetch('/api/projects').then(r => r.json());
  const list = document.getElementById('projectsList');
  list.innerHTML = '';


  projects.forEach(p => {
    const item = document.createElement('div');
    item.className = 'sidebar-item';
    item.innerHTML = `
      <span>${p.name}</span>
      <button class="icon-button open-project" data-id="${p.id}" data-name="${p.name}">
        <i class="fas fa-arrow-right"></i>
      </button>`;
    list.appendChild(item);
  });

  /* Navegación a un proyecto */
  list.querySelectorAll('.open-project').forEach(btn => {
    btn.addEventListener('click', e => {
      const id = e.currentTarget.dataset.id;
      const name = e.currentTarget.dataset.name;
      sessionStorage.setItem('currentProjectName', name);       // solo para la pestaña actual
      location.href = `/projects/${id}/solar-charts`;
    });
  });

  /* Botón “Inicio” */
  document.getElementById('btnAddProject')
    .addEventListener('click', () => location.href = '/');
}

/* ────────────────────────────────────────────────────────── */
/*  CARGA DEL PROYECTO ACTUAL                                */
/* ────────────────────────────────────────────────────────── */
async function loadCurrentProject() {
  const proj = await fetch(`/api/projects/${PROJECT_ID}`).then(r => r.json());
  document.getElementById('projectTitle').textContent = proj.name;
  document.title = `Cartas Solares – ${proj.name}`;
  loadSolarCharts(proj.charts);
}

/* ────────────────────────────────────────────────────────── */
/*  RENDER DE CARTAS SOLARES                                 */
/* ────────────────────────────────────────────────────────── */
function loadSolarCharts(chartsApi) {
  const grid = document.getElementById('chartsGrid');
  grid.innerHTML = '';

  if (!chartsApi.length) {
    grid.innerHTML =
      '<div class="empty-state"><p>No hay cartas solares. Crea una nueva con el botón +</p></div>';
    return;
  }

  const charts = chartsApi.slice(0, 12);

  charts.forEach((c, idx) => {
    const card = document.createElement('div');
    card.className = 'chart-card draggable';
    card.setAttribute('draggable', 'true');
    card.dataset.id = c.id;
    card.dataset.index = idx;

    const preview = c.preview
      ? c.preview
      : `/api/carta-solar?project=${PROJECT_ID}&orient=${c.angle || 0}&tmin=${c.temp || -273.15}`

    card.innerHTML = `
      <div class="chart-preview"><img src="${preview}" alt="${c.title || 'Carta solar'}"></div>
      <div class="chart-info">
        <h3>${c.title || 'Sin título'}</h3>
        <p>${c.description || 'Sin descripción'}</p>
      </div>
      <div class="chart-actions">
        <button class="icon-btn btnEdit"   data-id="${c.id}"><i class="fas fa-edit"></i></button>
        <button class="icon-btn btnDelete" data-id="${c.id}"><i class="fas fa-trash"></i></button>
      </div>`;

    // 1) Listener en toda la tarjeta para ir a la vista de edición:
    card.addEventListener('click', () => {
      location.href = `/projects/${PROJECT_ID}/solar-charts/${c.id}/edit`;
    });

    // 2) Evita que el clic en btnDelete propague la redirección:
    const btnDelete = card.querySelector('.btnDelete');
    btnDelete.addEventListener('click', e => {
      e.stopPropagation();
      // Aquí ya tendrías tu código de “borrar carta” existente, por ejemplo:
      // deleteChart(c.id);
    });

    // 3) (Opcional) Si aún tienes listener para btnEdit, también evita la propagación:
    const btnEdit = card.querySelector('.btnEdit');
    btnEdit.addEventListener('click', e => {
      e.stopPropagation();
      location.href = `/projects/${PROJECT_ID}/solar-charts/${c.id}/edit`;
    });

    grid.appendChild(card);
  });

  /* Editar / Eliminar */
  grid.querySelectorAll('.btnEdit').forEach(btn =>
    btn.addEventListener('click', e =>
      location.href = `/projects/${PROJECT_ID}/solar-charts/${e.currentTarget.dataset.id}/edit`));

  grid.querySelectorAll('.btnDelete').forEach(btn =>
    btn.addEventListener('click', e => {
      const id = e.currentTarget.dataset.id;
      if (confirm('¿Estás seguro de eliminar esta carta solar?')) deleteChart(id);
    }));

  /* Drag-and-drop solo para reordenar en la vista (sin persistencia) */
  setupDragAndDrop();
}

/* ────────────────────────────────────────────────────────── */
/*  EVENT LISTENERS GLOBALES                                 */
/* ────────────────────────────────────────────────────────── */
function setupEventListeners() {
  /* + Carta */
  document.getElementById('btnAddChart').addEventListener('click',
    () => document.getElementById('newChartModal').style.display = 'flex');

  /* Cerrar modal */
  document.querySelector('.close-modal').addEventListener('click',
    () => document.getElementById('newChartModal').style.display = 'none');

  /* Crear nueva carta */
  document.getElementById('newChartForm').addEventListener('submit', e => {
    e.preventDefault();
    createNewChart();
    document.getElementById('newChartModal').style.display = 'none';
  });

  /* Volver a proyectos */
  document.getElementById('btnBackToProjects').addEventListener('click',
    () => location.href = '/');
}

/* ────────────────────────────────────────────────────────── */
/*  ENDPOINTS                                                */
/* ────────────────────────────────────────────────────────── */
async function uploadEpwToServer() {
  const file = document.getElementById('epwInput').files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append('file', file);

  const res = await fetch(`/projects/${PROJECT_ID}/upload_epw`, { method: 'POST', body: fd });
  if (!res.ok) alert('Error subiendo EPW al servidor');
}

async function createChartOnServer(title, description) {
  /* 1) Crear la carta vacía (back-end asigna ID) */
  const { id } = await fetch(`/projects/${PROJECT_ID}/solar-charts`,
    { method: 'POST' }).then(r => r.json());

  /* 2) Actualizar título y descripción */
  await fetch(`/projects/${PROJECT_ID}/solar-charts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description })
  });

  loadCurrentProject();    // refresh
}

function createNewChart() {
  const title = document.getElementById('chartTitle').value.trim();
  const desc = document.getElementById('chartDescription').value.trim();
  createChartOnServer(title, desc);
}

async function deleteChart(id) {
  await fetch(`/projects/${PROJECT_ID}/solar-charts/${id}`, { method: 'DELETE' });
  loadCurrentProject();
}

/* ────────────────────────────────────────────────────────── */
/*  DRAG-AND-DROP (sólo UX local)                            */
/* ────────────────────────────────────────────────────────── */
function setupDragAndDrop() {
  const grid = document.getElementById('chartsGrid');

  grid.addEventListener('dragstart', e => {
    if (e.target.classList.contains('draggable')) {
      e.target.classList.add('dragging');
      e.dataTransfer.setData('text/plain', e.target.dataset.id);
    }
  });

  grid.addEventListener('dragend', e => {
    if (e.target.classList.contains('draggable')) {
      e.target.classList.remove('dragging');
      grid.querySelectorAll('.drop-zone').forEach(z => z.classList.remove('active'));
    }
  });

  grid.addEventListener('dragover', e => {
    e.preventDefault();
    const dragging = grid.querySelector('.dragging');
    if (!dragging) return;

    const after = getDragAfterElement(grid, e.clientY);
    after ? grid.insertBefore(dragging, after) : grid.appendChild(dragging);
  });

  grid.addEventListener('dragenter', e => {
    if (e.target.classList.contains('chart-card')) {
      e.target.classList.add('drop-zone', 'active');
    }
  });

  grid.addEventListener('dragleave', e => {
    if (e.target.classList.contains('chart-card')) e.target.classList.remove('active');
  });

  /* No persistimos el orden; sólo reorganización visual */
  grid.addEventListener('drop', e => e.preventDefault());
}

/* Devuelve el elemento inmediatamente posterior a la posición del cursor */
function getDragAfterElement(container, y) {
  const draggables = [...container.querySelectorAll('.draggable:not(.dragging)')];
  return draggables.reduce((closest, child) => {
    const box = child.getBoundingClientRect();
    const offset = y - box.top - box.height / 2;
    return offset < 0 && offset > closest.offset ? { offset, element: child } : closest;
  }, { offset: -Infinity }).element;
}
