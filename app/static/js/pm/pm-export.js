/**
 * Project management — styled PDF, PowerPoint, and Excel exports.
 */
(function (global) {
  'use strict';

  const THEME = {
    primary: [0, 64, 125],
    primaryHex: '00407D',
    primaryLight: [239, 246, 255],
    muted: [100, 116, 139],
    text: [15, 23, 42],
    border: [226, 232, 240],
    white: [255, 255, 255],
    altRow: [248, 250, 252],
  };

  const PDF_MARGINS = { left: 14, right: 14, top: 58, bottom: 28 };
  const PPTX_ROWS_PER_SLIDE = 12;
  const ALLOWED_SCOPES = new Set(['all', 'board', 'incomplete', 'schedule']);

  function normalizeScope(scope) {
    const s = scope === 'timeline' ? 'incomplete' : scope;
    return ALLOWED_SCOPES.has(s) ? s : 'all';
  }

  function scopesForExport(scope) {
    const s = normalizeScope(scope);
    if (s === 'all') return ['board', 'incomplete', 'schedule'];
    return [s];
  }

  function formatDate(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return String(iso);
      return d.toLocaleDateString();
    } catch {
      return String(iso);
    }
  }

  function sanitizeFilenamePart(name) {
    const s = String(name || 'Project').replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').trim();
    return s || 'Project';
  }

  function truncateCell(val, maxLen) {
    const s = val == null ? '' : String(val);
    if (s.length <= maxLen) return s;
    return s.slice(0, maxLen) + '…';
  }

  function pmAssigneeNamesFromList(assignees) {
    return (Array.isArray(assignees) ? assignees : [])
      .map((a) => (a && a.name) ? a.name : '')
      .filter(Boolean);
  }

  function pmFlattenBoardScheduleEntries(boardData) {
    const entries = [];
    (boardData?.columns || []).forEach((col) => {
      (col.tasks || []).forEach((task) => {
        entries.push({ kind: 'task', task, col, subtask: null });
        (task.subtasks || []).forEach((st) => {
          entries.push({ kind: 'subtask', task, col, subtask: st });
        });
      });
    });
    return entries;
  }

  function pmScheduleTaskLike(entry) {
    if (entry.kind === 'subtask') {
      const st = entry.subtask;
      const parent = entry.task;
      return {
        id: parent.id,
        item_type: 'subtask',
        subtask_id: st.id,
        title: '↳ ' + (st.title || ''),
        description: '',
        start_date: st.start_date || null,
        end_date: st.end_date || null,
        assignees: st.assignees || [],
        progress: st.is_done ? 100 : 0,
      };
    }
    const t = entry.task;
    return {
      id: t.id,
      item_type: 'task',
      title: t.title || '',
      description: t.description != null ? String(t.description) : '',
      start_date: t.start_date || null,
      end_date: t.end_date || null,
      assignees: t.assignees || [],
      progress: typeof t.progress === 'number' ? t.progress : 0,
    };
  }

  function ganttStripTime(d) {
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }

  function ganttParseLocal(iso) {
    if (!iso) return null;
    const s = String(iso).slice(0, 10);
    const p = s.split('-').map(Number);
    if (p.length < 3 || !p[0]) return null;
    return new Date(p[0], p[1] - 1, p[2]);
  }

  function ganttCountBizInclusive(s, e) {
    let n = 0;
    let c = ganttStripTime(s);
    const end = ganttStripTime(e);
    if (c > end) return 0;
    while (c <= end) {
      const wd = c.getDay();
      if (wd !== 0 && wd !== 6) n++;
      c = new Date(c.getFullYear(), c.getMonth(), c.getDate() + 1);
    }
    return Math.max(n, 0);
  }

  function ganttAssigneeLabel(task) {
    if (Array.isArray(task.assignees) && task.assignees.length) {
      return task.assignees[0].name || String(task.assignees[0]);
    }
    return 'Unassigned';
  }

  function ganttCollectDatedTasks(boardData) {
    const out = [];
    pmFlattenBoardScheduleEntries(boardData).forEach((entry) => {
      const task = pmScheduleTaskLike(entry);
      if (!task.start_date || !task.end_date) return;
      const a = ganttParseLocal(task.start_date);
      const b = ganttParseLocal(task.end_date);
      if (!a || !b || isNaN(a.getTime()) || isNaN(b.getTime())) return;
      if (b < a) return;
      out.push({ task, col: entry.col });
    });
    return out;
  }

  function readGanttFilters() {
    const dueEl = document.getElementById('ganttFilterDue');
    const ownerEl = document.getElementById('ganttFilterOwner');
    return {
      dueFilter: dueEl ? (dueEl.value || 'all') : 'all',
      ownerFilter: ownerEl ? (ownerEl.value || '') : '',
    };
  }

  function ganttDueInThisWeek(d) {
    const today = ganttStripTime(new Date());
    const dow = today.getDay();
    const monOffset = dow === 0 ? -6 : 1 - dow;
    const weekStart = new Date(today);
    weekStart.setDate(weekStart.getDate() + monOffset);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekEnd.getDate() + 6);
    const dd = ganttStripTime(d);
    return dd >= weekStart && dd <= weekEnd;
  }

  function ganttDueInThisMonth(d) {
    const now = new Date();
    return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
  }

  function ganttMatchesFilters(task, dueEnd, filters) {
    if (filters.ownerFilter && ganttAssigneeLabel(task) !== filters.ownerFilter) return false;
    if (filters.dueFilter === 'week' && !ganttDueInThisWeek(dueEnd)) return false;
    if (filters.dueFilter === 'month' && !ganttDueInThisMonth(dueEnd)) return false;
    return true;
  }

  function buildBoardExportRows(boardData) {
    const header = ['Column', 'Type', 'Task', 'Description', 'Start', 'End', 'Progress %', 'Assignees'];
    const rows = [header];
    if (!boardData || !boardData.columns) return rows;
    pmFlattenBoardScheduleEntries(boardData).forEach((entry) => {
      const sched = pmScheduleTaskLike(entry);
      const colTitle = entry.col.title || `Column ${entry.col.id}`;
      const prog = typeof sched.progress === 'number' ? `${sched.progress}%` : '';
      const desc = (sched.description || '').replace(/\s+/g, ' ').trim();
      const typeLabel = entry.kind === 'subtask' ? 'Sub-task' : 'Task';
      rows.push([
        colTitle,
        typeLabel,
        sched.title || '',
        desc,
        sched.start_date ? formatDate(sched.start_date) : '',
        sched.end_date ? formatDate(sched.end_date) : '',
        prog,
        pmAssigneeNamesFromList(sched.assignees).join(', ') || 'Unassigned',
      ]);
    });
    return rows;
  }

  function buildIncompleteExportRows(boardData) {
    const header = ['Task', 'Column', 'Progress', 'Start', 'Due', 'Assignees'];
    const rows = [header];
    if (!boardData || !boardData.columns) return rows;
    (boardData.columns || []).forEach((col) => {
      (col.tasks || []).forEach((t) => {
        const prog = typeof t.progress === 'number' ? t.progress : 0;
        if (prog >= 100) return;
        const names = (t.assignees || []).map((a) => a.name).filter(Boolean).join(', ') || 'Unassigned';
        rows.push([
          t.title || '',
          col.title || `Column ${col.id}`,
          `${prog}%`,
          t.start_date ? formatDate(t.start_date) : '',
          t.end_date ? formatDate(t.end_date) : '',
          names,
        ]);
      });
    });
    return rows;
  }

  function buildGanttExportRows(boardData) {
    const header = ['Group/Column', 'Task', 'Description', 'Owner', 'Start', 'Due', 'Days', 'Progress %'];
    const rows = [header];
    if (!boardData || !boardData.columns) return rows;

    const filters = readGanttFilters();
    const allDated = ganttCollectDatedTasks(boardData);
    if (!allDated.length) return rows;

    const filteredDated = allDated.filter(({ task }) => {
      const e = ganttParseLocal(task.end_date);
      return e && ganttMatchesFilters(task, e, filters);
    });
    if (!filteredDated.length) return rows;

    (boardData.columns || []).forEach((col) => {
      const colTitle = col.title || `Column ${col.id}`;
      const inCol = filteredDated.filter((x) => x.col.id === col.id);
      if (!inCol.length) return;
      inCol.forEach(({ task }) => {
        const s = ganttParseLocal(task.start_date);
        const e = ganttParseLocal(task.end_date);
        if (!s || !e) return;
        const dur = ganttCountBizInclusive(s, e);
        const pct = typeof task.progress === 'number' ? `${task.progress}%` : '';
        const desc = (task.description != null ? String(task.description) : '').replace(/\s+/g, ' ').trim();
        rows.push([
          colTitle,
          task.title || '',
          desc,
          ganttAssigneeLabel(task),
          formatDate(task.start_date),
          formatDate(task.end_date),
          dur,
          pct,
        ]);
      });
    });
    return rows;
  }

  function pmComputeReportStats(boardData) {
    const stats = { columns: 0, total: 0, complete: 0, open: 0, overdue: 0 };
    if (!boardData || !boardData.columns) return stats;
    stats.columns = boardData.columns.length;
    const today = ganttStripTime(new Date());
    (boardData.columns || []).forEach((col) => {
      (col.tasks || []).forEach((t) => {
        const prog = typeof t.progress === 'number' ? t.progress : 0;
        stats.total += 1;
        if (prog >= 100) stats.complete += 1;
        else stats.open += 1;
        const end = ganttParseLocal(t.end_date);
        if (end && end < today && prog < 100) stats.overdue += 1;
      });
    });
    return stats;
  }

  function getExportMeta(boardData, projectName, projectInfo) {
    const info = projectInfo || {};
    const members = Array.isArray(info.members) ? info.members : [];
    const memberLabel = members.length
      ? members.slice(0, 8).map((m) => (typeof m === 'string' ? m : m.name)).filter(Boolean).join(', ')
      : '—';
    return {
      title: projectName || 'Project',
      projectType: info.type || info.project_type || '—',
      members: memberLabel,
      generatedAt: new Date().toLocaleString(),
      dateStr: new Date().toISOString().slice(0, 10),
      stats: pmComputeReportStats(boardData),
    };
  }

  function loadExportLogo() {
    const url = global.PM_EXPORT_LOGO_URL || '/static/Logo.png';
    return fetch(url)
      .then((r) => (r.ok ? r.blob() : Promise.reject()))
      .then((blob) => new Promise((resolve) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result);
        reader.onerror = () => resolve(null);
        reader.readAsDataURL(blob);
      }))
      .catch(() => null);
  }

  function getPdfContentBounds(doc) {
    const pageW = doc.internal.pageSize.getWidth();
    return {
      left: PDF_MARGINS.left,
      right: pageW - PDF_MARGINS.right,
      width: pageW - PDF_MARGINS.left - PDF_MARGINS.right,
    };
  }

  function drawPdfPageChrome(doc, logoDataUrl, meta) {
    const pageW = doc.internal.pageSize.getWidth();
    const pageH = doc.internal.pageSize.getHeight();
    const pageNum = doc.internal.getNumberOfPages();

    doc.setFillColor(...THEME.white);
    doc.rect(0, 0, pageW, 52, 'F');
    doc.setFillColor(...THEME.primary);
    doc.rect(0, 0, pageW, 4, 'F');

    if (logoDataUrl) {
      try {
        const fmt = String(logoDataUrl).indexOf('image/png') !== -1 ? 'PNG' : 'JPEG';
        doc.addImage(logoDataUrl, fmt, PDF_MARGINS.left, 14, 88, 26);
      } catch {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(14);
        doc.setTextColor(...THEME.primary);
        doc.text('Akello', PDF_MARGINS.left, 32);
      }
    } else {
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(...THEME.primary);
      doc.text('Akello', PDF_MARGINS.left, 32);
    }

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(...THEME.muted);
    doc.text('Project Status Report', pageW - PDF_MARGINS.right, 22, { align: 'right' });
    if (meta && meta.title) {
      doc.setFontSize(8);
      doc.text(truncateCell(meta.title, 48), pageW - PDF_MARGINS.right, 34, { align: 'right' });
    }

    doc.setDrawColor(...THEME.border);
    doc.setLineWidth(0.5);
    doc.line(PDF_MARGINS.left, 52, pageW - PDF_MARGINS.right, 52);
    doc.line(PDF_MARGINS.left, pageH - 28, pageW - PDF_MARGINS.right, pageH - 28);

    doc.setFontSize(8);
    doc.setTextColor(...THEME.muted);
    const footerY = pageH - 14;
    doc.text('Page ' + pageNum, pageW - PDF_MARGINS.right, footerY, { align: 'right' });
    if (meta && meta.title) {
      doc.text(truncateCell(meta.title, 72), PDF_MARGINS.left, footerY);
    }
  }

  function drawPdfStatChip(doc, x, y, label, value, fillRgb) {
    doc.setFillColor(...fillRgb);
    doc.setDrawColor(...THEME.border);
    doc.setLineWidth(0.4);
    doc.roundedRect(x, y, 108, 42, 6, 6, 'FD');
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(16);
    doc.setTextColor(...THEME.primary);
    doc.text(String(value), x + 12, y + 22);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(8);
    doc.setTextColor(...THEME.muted);
    doc.text(label, x + 12, y + 34);
  }

  function renderPdfCover(doc, logoDataUrl, meta) {
    drawPdfPageChrome(doc, logoDataUrl, meta);
    const bounds = getPdfContentBounds(doc);
    let y = 78;

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(22);
    doc.setTextColor(...THEME.primary);
    const titleLines = doc.splitTextToSize(meta.title || 'Project', bounds.width - 20);
    doc.text(titleLines, bounds.left, y);
    y += titleLines.length * 26 + 4;

    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(...THEME.muted);
    doc.text('Project Status Report', bounds.left, y);
    y += 18;
    doc.setFontSize(9);
    doc.text('Generated ' + meta.generatedAt, bounds.left, y);
    y += 12;
    doc.text('Project type: ' + (meta.projectType || '—'), bounds.left, y);
    y += 12;
    doc.text('Members: ' + truncateCell(meta.members, 80), bounds.left, y);
    y += 18;

    const st = meta.stats || {};
    drawPdfStatChip(doc, bounds.left, y, 'Total tasks', st.total || 0, THEME.primaryLight);
    drawPdfStatChip(doc, bounds.left + 118, y, 'Complete', st.complete || 0, [240, 253, 244]);
    drawPdfStatChip(doc, bounds.left + 236, y, 'Open', st.open || 0, [255, 251, 235]);
    drawPdfStatChip(doc, bounds.left + 354, y, 'Overdue', st.overdue || 0, [254, 242, 242]);
  }

  function sectionTitleForScope(key) {
    if (key === 'board') return 'Board';
    if (key === 'incomplete') return 'Open Tasks';
    if (key === 'schedule') return 'Schedule';
    return key;
  }

  function rowsForScope(key, boardData) {
    if (key === 'board') return buildBoardExportRows(boardData);
    if (key === 'incomplete') return buildIncompleteExportRows(boardData);
    if (key === 'schedule') return buildGanttExportRows(boardData);
    return [['—']];
  }

  function addPdfTableSection(doc, logoDataUrl, meta, title, aoa, startY) {
    if (!aoa || aoa.length < 1) return startY;
    const PDF_TRUNC = 200;
    const head = aoa[0].map((c) => truncateCell(c, PDF_TRUNC));
    const body = aoa.slice(1).map((row) => row.map((c) => truncateCell(c, PDF_TRUNC)));

    let cursorY = startY;
    if (cursorY > 240) {
      doc.addPage();
      drawPdfPageChrome(doc, logoDataUrl, meta);
      cursorY = PDF_MARGINS.top;
    }

    doc.setFont('helvetica', 'bold');
    doc.setFontSize(13);
    doc.setTextColor(...THEME.primary);
    doc.text(title, PDF_MARGINS.left, cursorY);
    cursorY += 8;

    doc.autoTable({
      head: [head],
      body: body.length ? body : [['No data']],
      startY: cursorY,
      margin: { left: PDF_MARGINS.left, right: PDF_MARGINS.right },
      styles: { fontSize: 7.5, cellPadding: 2, textColor: THEME.text },
      headStyles: { fillColor: THEME.primary, textColor: THEME.white, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: THEME.altRow },
      didDrawPage: (data) => {
        if (data.pageNumber > 1) drawPdfPageChrome(doc, logoDataUrl, meta);
      },
    });
    return doc.lastAutoTable.finalY + 14;
  }

  async function exportStyledPdf(scope, boardData, meta) {
    if (!global.jspdf || !global.jspdf.jsPDF) {
      throw new Error('PDF export library is not available.');
    }
    const { jsPDF } = global.jspdf;
    const doc = new jsPDF({ orientation: 'portrait', unit: 'pt', format: 'a4' });
    const logo = await loadExportLogo();
    const projLabel = sanitizeFilenamePart(meta.title);
    const sections = scopesForExport(scope);

    renderPdfCover(doc, logo, meta);

    if (sections.length === 1) {
      doc.addPage();
      drawPdfPageChrome(doc, logo, meta);
      addPdfTableSection(doc, logo, meta, sectionTitleForScope(sections[0]), rowsForScope(sections[0], boardData), PDF_MARGINS.top);
    } else {
      sections.forEach((key) => {
        doc.addPage();
        drawPdfPageChrome(doc, logo, meta);
        addPdfTableSection(doc, logo, meta, sectionTitleForScope(key), rowsForScope(key, boardData), PDF_MARGINS.top);
      });
    }

    const suffix = normalizeScope(scope) === 'all' ? 'report' : normalizeScope(scope);
    doc.save(`${projLabel}_${suffix}_${meta.dateStr}.pdf`);
  }

  function getPptxConstructor() {
    if (global.PptxGenJS) return global.PptxGenJS;
    if (typeof PptxGenJS !== 'undefined') return PptxGenJS;
    return null;
  }

  function chunkRows(aoa, chunkSize) {
    if (!aoa || aoa.length <= 1) return [aoa || [['—']]];
    const header = aoa[0];
    const body = aoa.slice(1);
    if (!body.length) return [aoa];
    const chunks = [];
    for (let i = 0; i < body.length; i += chunkSize) {
      chunks.push([header, ...body.slice(i, i + chunkSize)]);
    }
    return chunks;
  }

  function truncatePptxRow(row, maxLen) {
    return row.map((c) => truncateCell(c, maxLen));
  }

  async function exportStyledPptx(scope, boardData, meta) {
    const PptxCtor = getPptxConstructor();
    if (!PptxCtor) {
      throw new Error('PowerPoint library not loaded. Hard refresh the page and try again.');
    }
    const logo = await loadExportLogo();
    const pptx = new PptxCtor();
    pptx.layout = 'LAYOUT_WIDE';
    pptx.author = 'Akello';
    pptx.subject = 'Project Status Report';
    pptx.title = meta.title || 'Project';

    const sections = scopesForExport(scope);
    const st = meta.stats || {};
    const cols = boardData?.columns || [];

    let slideNum = 0;
    const slideNums = [];

    function slideFooter(s, n, total) {
      s.addText((meta.title || 'Project') + '  ·  Project Status Report', {
        x: 0.5, y: 6.9, w: 8.5, h: 0.3, fontSize: 9, color: '64748B',
      });
      s.addText(String(n) + ' / ' + String(total), {
        x: 11.0, y: 6.9, w: 2.0, h: 0.3, fontSize: 9, color: '64748B', align: 'right',
      });
    }

    function addHeader(s) {
      s.addShape(pptx.ShapeType.rect, {
        x: 0, y: 0, w: 13.333, h: 0.06,
        fill: { color: THEME.primaryHex }, line: { color: THEME.primaryHex },
      });
      if (logo) {
        s.addImage({ data: logo, x: 0.5, y: 0.15, w: 1.8, h: 0.52 });
      } else {
        s.addText('Akello', { x: 0.5, y: 0.2, w: 2, h: 0.4, bold: true, fontSize: 20, color: THEME.primaryHex });
      }
    }

    const plannedSlides = [];
    plannedSlides.push('cover', 'glance');
    if (sections.includes('board')) {
      if (cols.length <= 6 && cols.length > 0) {
        cols.forEach((col) => plannedSlides.push('board-col:' + col.id));
      } else {
        chunkRows(buildBoardExportRows(boardData), PPTX_ROWS_PER_SLIDE).forEach((_, i) => {
          plannedSlides.push('board-chunk:' + i);
        });
      }
    }
    if (sections.includes('incomplete')) {
      chunkRows(buildIncompleteExportRows(boardData), PPTX_ROWS_PER_SLIDE).forEach((_, i) => {
        plannedSlides.push('incomplete-chunk:' + i);
      });
    }
    if (sections.includes('schedule')) {
      chunkRows(buildGanttExportRows(boardData), PPTX_ROWS_PER_SLIDE).forEach((_, i) => {
        plannedSlides.push('schedule-chunk:' + i);
      });
    }
    const totalSlides = plannedSlides.length;

    slideNum += 1;
    let s = pptx.addSlide();
    addHeader(s);
    s.addText('AKELLO', { x: 0.6, y: 1.1, w: 3.2, h: 0.5, bold: true, fontSize: 34, color: THEME.primaryHex });
    s.addText('Read · Learn · Play', { x: 0.6, y: 1.6, w: 3.2, h: 0.3, fontSize: 12, color: '64748B' });
    s.addText(meta.title || 'Project', { x: 0.6, y: 2.15, w: 8.8, h: 0.7, bold: true, fontSize: 30, color: '0F172A' });
    s.addText('Project Status Report', { x: 0.6, y: 2.88, w: 7.5, h: 0.4, bold: true, fontSize: 16, color: THEME.primaryHex });
    let cy = 3.5;
    [
      ['GENERATED', meta.generatedAt],
      ['PROJECT TYPE', meta.projectType || '—'],
      ['MEMBERS', truncateCell(meta.members, 120)],
    ].forEach((r) => {
      s.addShape(pptx.ShapeType.roundRect, {
        x: 0.6, y: cy, w: 12.1, h: 0.58, radius: 0.03,
        line: { color: 'E2E8F0', pt: 1 }, fill: { color: 'FFFFFF' },
      });
      s.addText(r[0], { x: 0.8, y: cy + 0.08, w: 1.8, h: 0.2, bold: true, fontSize: 9, color: '64748B' });
      s.addText(String(r[1] || '—'), { x: 2.3, y: cy + 0.22, w: 10.0, h: 0.2, fontSize: 11, color: '0F172A' });
      cy += 0.7;
    });
    slideFooter(s, slideNum, totalSlides);

    slideNum += 1;
    s = pptx.addSlide();
    addHeader(s);
    s.addText('At a glance', { x: 0.6, y: 0.95, w: 3.5, h: 0.4, bold: true, fontSize: 26, color: THEME.primaryHex });
    s.addText('Summary of tasks and columns in this project.', { x: 0.6, y: 1.35, w: 6.5, h: 0.3, fontSize: 11, color: '64748B' });
    [
      ['Total tasks', String(st.total || 0)],
      ['Complete', String(st.complete || 0)],
      ['Open', String(st.open || 0)],
      ['Overdue', String(st.overdue || 0)],
    ].forEach((c, i) => {
      const x = 0.6 + i * 3.05;
      s.addShape(pptx.ShapeType.roundRect, {
        x, y: 1.9, w: 2.85, h: 1.0, radius: 0.08,
        line: { color: 'E2E8F0', pt: 1 }, fill: { color: 'EFF6FF' },
      });
      s.addText(c[1], { x: x + 0.22, y: 2.15, w: 2.4, h: 0.25, fontSize: 24, bold: true, color: THEME.primaryHex });
      s.addText(c[0], { x: x + 0.22, y: 2.52, w: 2.4, h: 0.2, fontSize: 10, color: '64748B' });
    });
    s.addText('Columns: ' + String(st.columns || 0), { x: 0.6, y: 3.2, w: 4, h: 0.3, fontSize: 11, color: '64748B' });
    slideFooter(s, slideNum, totalSlides);

    function addTableSlides(title, subtitle, aoa) {
      const chunks = chunkRows(aoa, PPTX_ROWS_PER_SLIDE);
      chunks.forEach((chunk, idx) => {
        slideNum += 1;
        const slide = pptx.addSlide();
        addHeader(slide);
        const pageLabel = chunks.length > 1 ? ` (${idx + 1}/${chunks.length})` : '';
        slide.addText(title + pageLabel, { x: 0.6, y: 0.95, w: 8, h: 0.4, bold: true, fontSize: 24, color: THEME.primaryHex });
        if (subtitle) {
          slide.addText(subtitle, { x: 0.6, y: 1.35, w: 8, h: 0.3, fontSize: 11, color: '64748B' });
        }
        const tableRows = chunk.map((row, ri) => (
          ri === 0
            ? row.map((c) => ({ text: String(c), options: { bold: true, fill: THEME.primaryHex, color: 'FFFFFF' } }))
            : truncatePptxRow(row, 60).map((c) => ({ text: String(c) }))
        ));
        slide.addTable(tableRows, {
          x: 0.6, y: 1.85, w: 12.1, fontSize: 9,
          border: { pt: 1, color: 'E2E8F0' }, fill: 'FFFFFF',
        });
        slideFooter(slide, slideNum, totalSlides);
      });
    }

    if (sections.includes('board')) {
      if (cols.length <= 6 && cols.length > 0) {
        cols.forEach((col) => {
          const colTitle = col.title || `Column ${col.id}`;
          const header = ['Type', 'Task', 'Start', 'End', 'Progress', 'Assignees'];
          const rows = [header];
          pmFlattenBoardScheduleEntries({ columns: [col] }).forEach((entry) => {
            const sched = pmScheduleTaskLike(entry);
            rows.push([
              entry.kind === 'subtask' ? 'Sub-task' : 'Task',
              sched.title || '',
              sched.start_date ? formatDate(sched.start_date) : '—',
              sched.end_date ? formatDate(sched.end_date) : '—',
              typeof sched.progress === 'number' ? `${sched.progress}%` : '—',
              pmAssigneeNamesFromList(sched.assignees).join(', ') || 'Unassigned',
            ]);
          });
          slideNum += 1;
          const slide = pptx.addSlide();
          addHeader(slide);
          slide.addText('Board: ' + colTitle, { x: 0.6, y: 0.95, w: 8, h: 0.4, bold: true, fontSize: 24, color: THEME.primaryHex });
          slide.addText('Tasks and sub-tasks in this column.', { x: 0.6, y: 1.35, w: 8, h: 0.3, fontSize: 11, color: '64748B' });
          const tableRows = rows.length > 1
            ? rows.map((row, ri) => (
              ri === 0
                ? row.map((c) => ({ text: String(c), options: { bold: true, fill: THEME.primaryHex, color: 'FFFFFF' } }))
                : truncatePptxRow(row, 50).map((c) => ({ text: String(c) }))
            ))
            : [header.map((c) => ({ text: String(c), options: { bold: true, fill: THEME.primaryHex, color: 'FFFFFF' } })), [{ text: 'No tasks' }, { text: '—' }, { text: '—' }, { text: '—' }, { text: '—' }, { text: '—' }]];
          slide.addTable(tableRows, { x: 0.6, y: 1.85, w: 12.1, fontSize: 9, border: { pt: 1, color: 'E2E8F0' }, fill: 'FFFFFF' });
          slideFooter(slide, slideNum, totalSlides);
        });
      } else {
        addTableSlides('Board', 'All columns, tasks, and sub-tasks.', buildBoardExportRows(boardData));
      }
    }
    if (sections.includes('incomplete')) {
      addTableSlides('Open Tasks', 'Tasks not yet 100% complete.', buildIncompleteExportRows(boardData));
    }
    if (sections.includes('schedule')) {
      addTableSlides('Schedule', 'Tasks with start and end dates.', buildGanttExportRows(boardData));
    }

    const projLabel = sanitizeFilenamePart(meta.title);
    const suffix = normalizeScope(scope) === 'all' ? 'report' : normalizeScope(scope);
    await pptx.writeFile({ fileName: `${projLabel}_${suffix}_${meta.dateStr}.pptx` });
  }

  function exportExcel(scope, boardData, meta) {
    if (typeof XLSX === 'undefined' || !XLSX.utils) {
      throw new Error('Excel export library is not available.');
    }
    const s = normalizeScope(scope);
    const projLabel = sanitizeFilenamePart(meta.title);
    const dateStr = meta.dateStr;
    const wb = XLSX.utils.book_new();

    const appendBoard = () => {
      const ws = XLSX.utils.aoa_to_sheet(buildBoardExportRows(boardData));
      ws['!cols'] = [{ wch: 18 }, { wch: 28 }, { wch: 44 }, { wch: 14 }, { wch: 14 }, { wch: 12 }, { wch: 28 }];
      XLSX.utils.book_append_sheet(wb, ws, 'Board');
    };
    const appendIncomplete = () => {
      const ws = XLSX.utils.aoa_to_sheet(buildIncompleteExportRows(boardData));
      ws['!cols'] = [{ wch: 28 }, { wch: 18 }, { wch: 10 }, { wch: 14 }, { wch: 14 }, { wch: 28 }];
      XLSX.utils.book_append_sheet(wb, ws, 'Open Tasks');
    };
    const appendSchedule = () => {
      const ws = XLSX.utils.aoa_to_sheet(buildGanttExportRows(boardData));
      ws['!cols'] = [{ wch: 20 }, { wch: 28 }, { wch: 40 }, { wch: 22 }, { wch: 14 }, { wch: 14 }, { wch: 8 }, { wch: 12 }];
      XLSX.utils.book_append_sheet(wb, ws, 'Schedule');
    };

    if (s === 'all') {
      appendBoard();
      appendIncomplete();
      appendSchedule();
      XLSX.writeFile(wb, `${projLabel}_report_${dateStr}.xlsx`);
    } else if (s === 'board') {
      appendBoard();
      XLSX.writeFile(wb, `${projLabel}_board_${dateStr}.xlsx`);
    } else if (s === 'incomplete') {
      appendIncomplete();
      XLSX.writeFile(wb, `${projLabel}_open_tasks_${dateStr}.xlsx`);
    } else {
      appendSchedule();
      XLSX.writeFile(wb, `${projLabel}_schedule_${dateStr}.xlsx`);
    }
  }

  async function runExport(opts) {
    const format = opts.format || 'pdf';
    const scope = opts.scope || 'all';
    const boardData = opts.boardData;
    const meta = opts.meta;

    if (!boardData || !boardData.columns) {
      throw new Error('No project data loaded. Select a project and wait for the board to load.');
    }

    if (format === 'pdf') await exportStyledPdf(scope, boardData, meta);
    else if (format === 'pptx') await exportStyledPptx(scope, boardData, meta);
    else if (format === 'excel') exportExcel(scope, boardData, meta);
    else throw new Error('Unknown export format: ' + format);
  }

  function openExportModal() {
    const backdrop = document.getElementById('pmExportModalBackdrop');
    if (!backdrop) return;
    backdrop.classList.remove('hidden');
    backdrop.classList.add('flex');
  }

  function closeExportModal() {
    const backdrop = document.getElementById('pmExportModalBackdrop');
    if (!backdrop) return;
    backdrop.classList.add('hidden');
    backdrop.classList.remove('flex');
  }

  function wireExportModal(getContext) {
    const btn = document.getElementById('pmExportBtn');
    const backdrop = document.getElementById('pmExportModalBackdrop');
    const cancelBtn = document.getElementById('pmExportCancel');
    const confirmBtn = document.getElementById('pmExportConfirm');

    if (btn) {
      btn.onclick = () => {
        const ctx = typeof getContext === 'function' ? getContext() : {};
        if (!ctx.boardData || !ctx.boardData.columns) {
          alert('Select a project and wait for the board to load before exporting.');
          return;
        }
        openExportModal();
      };
    }
    if (cancelBtn) cancelBtn.onclick = closeExportModal;
    if (backdrop) {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) closeExportModal();
      });
    }
    if (confirmBtn) {
      confirmBtn.onclick = async () => {
        const formatEl = document.querySelector('input[name="pm-export-format"]:checked');
        const scopeEl = document.querySelector('input[name="pm-export-scope"]:checked');
        const format = formatEl ? formatEl.value : 'pdf';
        const scope = scopeEl ? scopeEl.value : 'all';
        const ctx = typeof getContext === 'function' ? getContext() : {};
        if (!ctx.boardData || !ctx.boardData.columns) {
          alert('No project data loaded.');
          return;
        }
        confirmBtn.disabled = true;
        const prevText = confirmBtn.textContent;
        confirmBtn.textContent = 'Exporting…';
        try {
          await runExport({ format, scope, boardData: ctx.boardData, meta: ctx.meta });
          closeExportModal();
        } catch (err) {
          alert(err.message || String(err));
        } finally {
          confirmBtn.disabled = false;
          confirmBtn.textContent = prevText;
        }
      };
    }
  }

  async function fetchPortfolioExportDetail(ctx) {
    const API = global.PM_API_BASE || '/api';
    const params = new URLSearchParams();
    if (ctx && ctx.programId) params.set('program_id', ctx.programId);
    let health = ctx && ctx.health;
    if (ctx && ctx.scope === 'at_risk') health = 'red';
    else if (ctx && ctx.scope === 'executive_summary') {
      params.set('executive_summary', '1');
    }
    else if (health) params.set('health', health);
    const q = params.toString();
    return pmApiGET(`${API}/pm/portfolio/export-detail${q ? '?' + q : ''}`);
  }

  function portfolioHealthRgb(health) {
    if (health === 'red') return [220, 38, 38];
    if (health === 'yellow') return [217, 119, 6];
    return [5, 150, 105];
  }

  function portfolioProjectKpiLine(p) {
    const parts = [
      `${p.pct_complete}% complete`,
      `${p.open_task_count || 0} open`,
      `${p.overdue_count || 0} overdue`,
      `${p.blocked_count || 0} blocked`,
    ];
    if (p.owner_name) parts.push(`Owner: ${p.owner_name}`);
    if ((p.program_names || []).length) parts.push(`Programs: ${p.program_names.join(', ')}`);
    return parts.join('  ·  ');
  }

  async function exportPortfolioPdf(detail, title, options) {
    if (!global.jspdf || !global.jspdf.jsPDF) throw new Error('jsPDF not loaded');
    const rows = detail || [];
    const logo = await loadExportLogo();
    const doc = new global.jspdf.jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const dateStr = new Date().toISOString().slice(0, 10);
    const meta = {
      title: title || 'Portfolio Executive Report',
      generatedAt: new Date().toLocaleString(),
      dateStr,
      stats: pmPortfolioSummaryFromStats(rows),
    };

    // Cover page
    drawPdfPageChrome(doc, logo, meta);
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(20);
    doc.setTextColor(...THEME.primary);
    doc.text('Portfolio Executive Report', PDF_MARGINS.left, 70);
    doc.setFont('helvetica', 'normal');
    doc.setFontSize(10);
    doc.setTextColor(...THEME.text);
    doc.text(`Generated ${meta.generatedAt}`, PDF_MARGINS.left, 82);
    const sum = meta.stats;
    let y = 96;
    doc.text(`Portfolio overview: ${sum.total} projects — ${sum.red} at risk, ${sum.yellow} watch, ${sum.green} on track`, PDF_MARGINS.left, y);
    y += 6;
    doc.text(`Aggregate overdue tasks: ${sum.overdue}  |  Blocked tasks: ${sum.blocked}`, PDF_MARGINS.left, y);

    // Summary table page
    doc.addPage();
    drawPdfPageChrome(doc, logo, meta);
    y = 58;
    doc.setFontSize(11);
    doc.setFont('helvetica', 'bold');
    doc.text('Portfolio summary', PDF_MARGINS.left, y);
    y += 4;
    const tableBody = rows.map((s) => [
      s.project_name || '',
      (s.health || '').toUpperCase(),
      s.owner_name || '—',
      `${s.pct_complete}%`,
      `${s.completed_tasks}/${s.total_tasks}`,
      String(s.open_task_count || 0),
      String(s.overdue_count || 0),
      String(s.blocked_count || 0),
      s.next_milestone ? truncateCell(`${s.next_milestone}${s.next_milestone_date ? ' (' + formatDate(s.next_milestone_date) + ')' : ''}`, 36) : '—',
    ]);
    if (doc.autoTable) {
      doc.autoTable({
        startY: y + 2,
        head: [['Project', 'Health', 'Owner', '%', 'Done/Total', 'Open', 'Overdue', 'Blocked', 'Next milestone']],
        body: tableBody,
        styles: { fontSize: 7.5, cellPadding: 2 },
        headStyles: { fillColor: THEME.primary },
        margin: { left: PDF_MARGINS.left, right: PDF_MARGINS.right },
      });
    }

    // Per-project detail pages
    rows.forEach((p) => {
      doc.addPage();
      drawPdfPageChrome(doc, logo, { ...meta, title: p.project_name });
      y = 58;
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(...portfolioHealthRgb(p.health));
      doc.text(p.project_name || 'Project', PDF_MARGINS.left, y);
      doc.setFontSize(9);
      doc.setTextColor(...THEME.muted);
      doc.text((p.health || '').toUpperCase(), PDF_MARGINS.left + 2, y + 6);
      y += 12;
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(8.5);
      doc.setTextColor(...THEME.text);
      const kpiLines = doc.splitTextToSize(portfolioProjectKpiLine(p), 260);
      doc.text(kpiLines, PDF_MARGINS.left, y);
      y += kpiLines.length * 4 + 4;

      if ((p.milestones || []).length) {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.text('Milestones', PDF_MARGINS.left, y);
        y += 3;
        if (doc.autoTable) {
          doc.autoTable({
            startY: y,
            head: [['Milestone', 'Due date', 'Linked tasks']],
            body: (p.milestones || []).map((m) => [
              m.title || '',
              m.due_date ? formatDate(m.due_date) : '—',
              String((m.task_ids || []).length),
            ]),
            styles: { fontSize: 7.5 },
            headStyles: { fillColor: [99, 102, 241] },
            margin: { left: PDF_MARGINS.left, right: PDF_MARGINS.right },
          });
          y = doc.lastAutoTable.finalY + 6;
        }
      }

      if ((p.columns || []).length) {
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.text('Workflow by column', PDF_MARGINS.left, y);
        y += 3;
        if (doc.autoTable) {
          doc.autoTable({
            startY: y,
            head: [['Column', 'Tasks']],
            body: (p.columns || []).map((c) => [c.title || '', String(c.count || 0)]),
            styles: { fontSize: 7.5 },
            headStyles: { fillColor: THEME.muted },
            margin: { left: PDF_MARGINS.left, right: PDF_MARGINS.right },
          });
          y = doc.lastAutoTable.finalY + 6;
        }
      }

      doc.setFont('helvetica', 'bold');
      doc.setFontSize(9);
      doc.text('All tasks — status & timeline', PDF_MARGINS.left, y);
      y += 3;
      const taskBody = (p.tasks || []).map((t) => [
        truncateCell(t.title, 42),
        t.column || '',
        t.status || '',
        `${t.progress != null ? t.progress : 0}%`,
        t.priority || '',
        t.start_date ? formatDate(t.start_date) : '—',
        t.end_date ? formatDate(t.end_date) : '—',
        (t.assignees || []).join(', ') || 'Unassigned',
      ]);
      if (doc.autoTable && taskBody.length) {
        doc.autoTable({
          startY: y,
          head: [['Task', 'Column', 'Status', '%', 'Priority', 'Start', 'Due', 'Assignees']],
          body: taskBody,
          styles: { fontSize: 6.5, cellPadding: 1.5 },
          headStyles: { fillColor: THEME.primary },
          margin: { left: PDF_MARGINS.left, right: PDF_MARGINS.right },
          didParseCell: (data) => {
            if (data.section === 'body' && data.column.index === 2) {
              const st = String(data.cell.raw || '');
              if (st === 'Overdue') data.cell.styles.textColor = [220, 38, 38];
              else if (st === 'Blocked') data.cell.styles.textColor = [217, 119, 6];
              else if (st === 'Complete') data.cell.styles.textColor = [5, 150, 105];
            }
          },
        });
      } else if (!taskBody.length) {
        doc.setFontSize(8);
        doc.setTextColor(...THEME.muted);
        doc.text('No tasks in this project.', PDF_MARGINS.left, y + 4);
      }
    });

    doc.save(`portfolio-executive-${dateStr}.pdf`);
  }

  function pmPortfolioSummaryFromStats(stats) {
    const s = stats || [];
    return {
      total: s.length,
      red: s.filter((x) => x.health === 'red').length,
      yellow: s.filter((x) => x.health === 'yellow').length,
      green: s.filter((x) => x.health === 'green').length,
      overdue: s.reduce((n, x) => n + (x.overdue_count || 0), 0),
      blocked: s.reduce((n, x) => n + (x.blocked_count || 0), 0),
    };
  }

  function buildPortfolioExcelRows(detail, scope) {
    const rows = detail || [];
    const summary = [
      ['Portfolio Executive Report'],
      ['Generated', new Date().toLocaleString()],
      ['Projects', rows.length],
      [],
      ['Project', 'Health', 'Owner', 'Type', '% Complete', 'Done/Total', 'Open', 'Overdue', 'Blocked', 'Next milestone', 'Milestone date', 'Programs'],
    ];
    const summaryData = rows.map((s) => [
      s.project_name, s.health, s.owner_name || '', s.project_type, s.pct_complete,
      `${s.completed_tasks}/${s.total_tasks}`, s.open_task_count || 0, s.overdue_count, s.blocked_count,
      s.next_milestone || '', s.next_milestone_date ? formatDate(s.next_milestone_date) : '',
      (s.program_names || []).join(', '),
    ]);
    const allTasks = [['Project', 'Task', 'Column', 'Status', 'Progress', 'Priority', 'Start', 'Due', 'Assignees']];
    const schedule = [['Project', 'Task', 'Column', 'Status', 'Start', 'Due', 'Days est.', 'Assignees']];
    const milestones = [['Project', 'Milestone', 'Due date', 'Linked tasks']];
    const overdue = [['Project', 'Task', 'Column', 'Due', 'Assignees', 'Progress']];
    rows.forEach((p) => {
      (p.milestones || []).forEach((m) => {
        milestones.push([p.project_name, m.title, m.due_date ? formatDate(m.due_date) : '', (m.task_ids || []).length]);
      });
      (p.tasks || []).forEach((t) => {
        allTasks.push([
          p.project_name, t.title, t.column, t.status, `${t.progress}%`, t.priority,
          t.start_date ? formatDate(t.start_date) : '',
          t.end_date ? formatDate(t.end_date) : '',
          (t.assignees || []).join(', '),
        ]);
        if (t.status === 'Overdue') {
          overdue.push([p.project_name, t.title, t.column, formatDate(t.end_date), (t.assignees || []).join(', '), `${t.progress}%`]);
        }
        if (t.start_date && t.end_date) {
          schedule.push([
            p.project_name, t.title, t.column, t.status,
            formatDate(t.start_date), formatDate(t.end_date), '', (t.assignees || []).join(', '),
          ]);
        }
      });
    });
    return {
      summary: summary.concat(summaryData),
      allTasks,
      schedule,
      milestones,
      overdue,
    };
  }

  async function exportPortfolioExcel(detail, options) {
    const sheets = buildPortfolioExcelRows(detail, (options || {}).scope);
    if (typeof XLSX === 'undefined') throw new Error('SheetJS not loaded');
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheets.summary), 'Summary');
    if ((options || {}).scope !== 'executive_summary') {
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheets.allTasks), 'All tasks');
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheets.schedule), 'Timeline');
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheets.overdue), 'Overdue');
      XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(sheets.milestones), 'Milestones');
    }
    XLSX.writeFile(wb, `portfolio-executive-${new Date().toISOString().slice(0, 10)}.xlsx`);
  }

  async function exportPortfolioPptx(detail, title, options) {
    const PptxGenJS = global.PptxGenJS;
    if (!PptxGenJS) throw new Error('PptxGenJS not loaded');
    const rows = detail || [];
    const sum = pmPortfolioSummaryFromStats(rows);
    const pptx = new PptxGenJS();
    pptx.author = 'Akello PM';
    const titleSlide = pptx.addSlide();
    titleSlide.addText(title || 'Portfolio Executive Report', { x: 0.5, y: 1.0, w: 9, fontSize: 28, color: '00407D', bold: true });
    titleSlide.addText(`Generated ${new Date().toLocaleString()}`, { x: 0.5, y: 2.0, fontSize: 12, color: '64748B' });
    titleSlide.addText(
      `${sum.total} projects  ·  ${sum.red} at risk  ·  ${sum.yellow} watch  ·  ${sum.green} on track`,
      { x: 0.5, y: 2.5, w: 9, fontSize: 14, color: '334155' }
    );

    const sumSlide = pptx.addSlide();
    sumSlide.addText('Portfolio summary', { x: 0.5, y: 0.35, fontSize: 20, color: '00407D', bold: true });
    const sumRows = [
      [{ text: 'Project', options: { bold: true, fill: '00407D', color: 'FFFFFF' } }, 'Health', 'Owner', '%', 'Open', 'Overdue', 'Blocked'],
      ...rows.slice(0, 14).map((s) => [
        s.project_name,
        (s.health || '').toUpperCase(),
        s.owner_name || '—',
        `${s.pct_complete}%`,
        String(s.open_task_count || 0),
        String(s.overdue_count || 0),
        String(s.blocked_count || 0),
      ]),
    ];
    sumSlide.addTable(sumRows, { x: 0.3, y: 1.0, w: 9.2, fontSize: 10, border: { pt: 0.5, color: 'E2E8F0' } });

    rows.forEach((p) => {
      const hdr = pptx.addSlide();
      const hColor = p.health === 'red' ? 'DC2626' : (p.health === 'yellow' ? 'D97706' : '059669');
      hdr.addText(p.project_name, { x: 0.5, y: 0.4, fontSize: 24, color: hColor, bold: true });
      hdr.addText(portfolioProjectKpiLine(p), { x: 0.5, y: 1.2, w: 9, fontSize: 11, color: '475569' });
      if ((p.milestones || []).length) {
        hdr.addText(
          'Milestones: ' + (p.milestones || []).map((m) => `${m.title} (${m.due_date ? formatDate(m.due_date) : 'no date'})`).join(' · '),
          { x: 0.5, y: 2.0, w: 9, fontSize: 10, color: '6366F1' }
        );
      }

      const tasks = p.tasks || [];
      for (let i = 0; i < tasks.length; i += 10) {
        const chunk = tasks.slice(i, i + 10);
        const sl = pptx.addSlide();
        sl.addText(`${p.project_name} — tasks (${i + 1}–${i + chunk.length} of ${tasks.length})`, {
          x: 0.4, y: 0.3, w: 9.2, fontSize: 14, color: '00407D', bold: true,
        });
        const tRows = [
          [{ text: 'Task', options: { bold: true, fill: '00407D', color: 'FFFFFF' } }, 'Column', 'Status', 'Due', 'Assignees'],
          ...chunk.map((t) => [
            truncateCell(t.title, 48),
            t.column || '',
            t.status || '',
            t.end_date ? formatDate(t.end_date) : '—',
            truncateCell((t.assignees || []).join(', ') || 'Unassigned', 28),
          ]),
        ];
        sl.addTable(tRows, { x: 0.3, y: 0.9, w: 9.2, fontSize: 9, border: { pt: 0.5, color: 'E2E8F0' } });
      }
    });

    await pptx.writeFile({ fileName: `portfolio-executive-${new Date().toISOString().slice(0, 10)}.pptx` });
  }

  async function runPortfolioExport({ format, detail, scope, title, ctx }) {
    let payload = detail;
    if (!payload) {
      payload = await fetchPortfolioExportDetail({ ...(ctx || {}), scope: scope || 'all' });
    }
    const options = { scope: scope || 'all' };
    if (format === 'pdf') return exportPortfolioPdf(payload, title, options);
    if (format === 'xlsx') return exportPortfolioExcel(payload, options);
    if (format === 'pptx') return exportPortfolioPptx(payload, title, options);
    throw new Error('Unknown format');
  }

  function wirePortfolioExportModal(getContext) {
    const btn = document.getElementById('pmPortfolioExportBtn');
    const backdrop = document.getElementById('pmPortfolioExportBackdrop');
    const cancel = document.getElementById('pmPortfolioExportCancel');
    const confirm = document.getElementById('pmPortfolioExportConfirm');
    if (!btn || !backdrop) return;
    const open = () => { backdrop.classList.remove('hidden'); backdrop.setAttribute('aria-hidden', 'false'); };
    const close = () => { backdrop.classList.add('hidden'); backdrop.setAttribute('aria-hidden', 'true'); };
    btn.onclick = open;
    if (cancel) cancel.onclick = close;
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) close(); });
    if (confirm) {
      confirm.onclick = async () => {
        const formatEl = document.querySelector('input[name="pm-portfolio-format"]:checked');
        const scopeEl = document.querySelector('input[name="pm-portfolio-scope"]:checked');
        const format = formatEl ? formatEl.value : 'pdf';
        const scope = scopeEl ? scopeEl.value : 'all';
        const ctx = typeof getContext === 'function' ? getContext() : {};
        confirm.disabled = true;
        const prevText = confirm.textContent;
        confirm.textContent = 'Preparing…';
        try {
          await runPortfolioExport({
            format,
            scope,
            title: 'Portfolio Executive Report',
            ctx: {
              programId: ctx.programId || null,
              health: ctx.health || null,
              scope,
            },
          });
          close();
        } catch (e) {
          alert(e.message || e);
        } finally {
          confirm.disabled = false;
          confirm.textContent = prevText;
        }
      };
    }
  }

  global.PmExport = {
    runExport,
    exportPortfolioPdf,
    runPortfolioExport,
    wirePortfolioExportModal,
    openExportModal,
    closeExportModal,
    wireExportModal,
    getExportMeta,
    pmComputeReportStats,
    buildBoardExportRows,
    buildIncompleteExportRows,
    buildGanttExportRows,
    sanitizeFilenamePart,
  };
})(typeof window !== 'undefined' ? window : globalThis);
