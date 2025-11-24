const api = (path, opts={}) => fetch(path, {
  headers: {'Content-Type':'application/json'},
  ...opts
}).then(r => r.ok ? r.json() : r.json().then(e => { throw e; }));

let currentProjectId = null;
const boardArea = document.getElementById('boardArea');
const projectSelect = document.getElementById('projectSelect');
const newProjectBtn = document.getElementById('newProjectBtn');

async function loadProjects(){
  const projects = await api('/api/projects');
  projectSelect.innerHTML = '';
  for(const p of projects){
    const opt = document.createElement('option');
    opt.value = p.id;
    opt.textContent = p.name;
    projectSelect.appendChild(opt);
  }
  if(projects.length){
    currentProjectId = projects[0].id;
    projectSelect.value = currentProjectId;
    loadBoard(currentProjectId);
  }
}

projectSelect.addEventListener('change', (e) => {
  currentProjectId = e.target.value;
  loadBoard(currentProjectId);
});

newProjectBtn.addEventListener('click', async () => {
  const name = prompt("Project name?");
  if(!name) return;
  const p = await api('/api/projects', {method:'POST', body: JSON.stringify({name})});
  await loadProjects();
  projectSelect.value = p.id;
  currentProjectId = p.id;
  loadBoard(currentProjectId);
});

async function loadBoard(projectId){
  boardArea.innerHTML = '';
  const board = await api(`/api/projects/${projectId}/board`);
  board.columns.forEach(c => renderColumn(c));
}

function renderColumn(col){
  const colWrap = document.createElement('div');
  colWrap.className = 'bg-white rounded shadow p-3 flex-shrink-0';
  colWrap.style.width = '300px';
  colWrap.dataset.colId = col.id;

  const header = document.createElement('div');
  header.className = 'flex items-center justify-between mb-2';
  header.innerHTML = `<h3 class="font-semibold">${col.title}</h3><button class="text-sm text-gray-500" data-add>+ task</button>`;
  colWrap.appendChild(header);

  const taskList = document.createElement('div');
  taskList.className = 'min-h-[50px]';
  taskList.id = `col-${col.id}-list`;

  col.tasks.forEach(t => {
    const card = createTaskCard(t);
    taskList.appendChild(card);
  });

  colWrap.appendChild(taskList);

  // add controls: add task
  header.querySelector('[data-add]').addEventListener('click', async () => {
    const title = prompt("Task title?");
    if(!title) return;
    await api(`/api/columns/${col.id}/tasks`, {method:'POST', body: JSON.stringify({title})});
    loadBoard(currentProjectId);
  });

  boardArea.appendChild(colWrap);

  enableSortableOnColumn(taskList);
}

// create draggable task card
function createTaskCard(t){
  const card = document.createElement('div');
  card.className = 'bg-gray-50 p-2 rounded mb-2 shadow-sm cursor-grab';
  card.dataset.taskId = t.id;
  card.innerHTML = `<div class="font-medium">${escapeHtml(t.title)}</div><div class="text-xs text-gray-500">${t.description||''}</div>`;
  return card;
}

function enableSortableOnColumn(container){
  new Sortable(container, {
    group: 'tasks',
    animation: 150,
    onEnd: async (evt) => {
      // evt.item -> moved DOM element
      // determine new column id and position
      const taskId = evt.item.dataset.taskId;
      const newColElem = evt.to.closest('[data-col-id]');
      const newColId = parseInt(newColElem.dataset.colId, 10);
      const items = Array.from(evt.to.children);
      const newPos = items.findIndex(it => it.dataset.taskId === taskId);

      await api(`/api/tasks/${taskId}`, {
        method: 'PATCH',
        body: JSON.stringify({column_id: newColId, position: newPos})
      });
      // re-load to normalize positions (could be optimized)
      loadBoard(currentProjectId);
    }
  });

  // also allow column reordering via drag of whole column (optional)
  if(!window.columnsSortableInitialized){
    window.columnsSortableInitialized = true;
    new Sortable(boardArea, {
      animation: 200,
      handle: '.font-semibold',
      onEnd: async (evt)=>{
        // update column order
        const order = Array.from(boardArea.children).map(c => parseInt(c.dataset.colId,10));
        await api(`/api/projects/${currentProjectId}/columns/reorder`, {method:'POST', body: JSON.stringify({order})});
      }
    });
  }
}

// minimal helper
function escapeHtml(s){ return (s||'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

loadProjects();
