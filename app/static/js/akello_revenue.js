/**
 * Akello Revenue tab — tables, charts, Excel import, admin edit.
 */
(function (global) {
  'use strict';

  const MONTH_NAMES = {
    1: 'January', 2: 'February', 3: 'March', 4: 'April', 5: 'May', 6: 'June',
    7: 'July', 8: 'August', 9: 'September', 10: 'October', 11: 'November', 12: 'December'
  };

  const REVENUE_FIELDS = [
    'rev_asl_hlf_usd', 'rev_asl_hlf_zwl', 'rev_lib_hlf_usd', 'rev_lib_hlf_zwl',
    'rev_asl_org_usd', 'rev_asl_org_zwl', 'rev_lib_org_usd', 'rev_lib_org_zwl'
  ];
  const SUBSCRIBER_FIELDS = [
    'sub_asl_hlf_usd', 'sub_asl_hlf_zwl', 'sub_lib_hlf_usd', 'sub_lib_hlf_zwl',
    'sub_asl_org_usd', 'sub_asl_org_zwl', 'sub_lib_org_usd', 'sub_lib_org_zwl'
  ];

  const COLORS = {
    aslHlf: '#00407d',
    libHlf: '#2563eb',
    aslOrg: '#0f766e',
    libOrg: '#14b8a6',
    hlf: '#00407d',
    organic: '#0f766e'
  };

  let state = {
    canEdit: false,
    period: null,
    periods: [],
    loaded: false,
    chartTypes: { revenue: 'bar', subs: 'bar' }
  };

  let charts = {
    contrib: null,
    summaryBar: null,
    revenue: null,
    subs: null
  };

  function csrfToken() {
    const input = document.getElementById('akello-revenue-csrf');
    if (input && input.value) return input.value;
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : '';
  }

  function money(n) {
    const v = Number(n) || 0;
    return v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  function intFmt(n) {
    return (Number(n) || 0).toLocaleString();
  }

  function pctFmt(n) {
    return ((Number(n) || 0) * 100).toFixed(1) + '%';
  }

  async function api(path, opts) {
    const options = Object.assign({ credentials: 'same-origin' }, opts || {});
    options.headers = Object.assign(
      { Accept: 'application/json', 'Content-Type': 'application/json' },
      options.headers || {}
    );
    const token = csrfToken();
    if (token && options.method && options.method !== 'GET') {
      options.headers['X-CSRFToken'] = token;
    }
    const res = await fetch('/akello-revenue' + path, options);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const err = new Error(data.error || ('Request failed (' + res.status + ')'));
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function setStatus(msg, isError) {
    const el = document.getElementById('rev-status');
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'w3-small ' + (isError ? 'w3-text-red' : 'w3-text-gray');
  }

  function destroyChart(key) {
    if (charts[key]) {
      charts[key].destroy();
      charts[key] = null;
    }
  }

  function renderPeriodSelect() {
    const sel = document.getElementById('rev-period-select');
    if (!sel) return;
    const current = state.period ? state.period.code : (sel.value || 'FY2027');
    sel.innerHTML = state.periods.map(function (p) {
      return '<option value="' + p.code + '"' + (p.code === current ? ' selected' : '') + '>' +
        (p.name || p.code) + '</option>';
    }).join('');
    if (!state.periods.length) {
      sel.innerHTML = '<option value="FY2027">FY2027</option>';
    }
  }

  function numCell(value, fmtFn, colClass) {
    const n = Number(value) || 0;
    const zero = n === 0 ? ' rev-zero' : '';
    return '<td class="rev-num ' + (colClass || '') + zero + '">' + fmtFn(n) + '</td>';
  }

  function renderSummary() {
    const s = (state.period && state.period.summary) || null;
    const body = document.getElementById('rev-summary-body');
    const contrib = document.getElementById('rev-contrib-body');
    const note = document.getElementById('rev-fx-note');
    if (!body) return;
    if (!s) {
      body.innerHTML = '<tr><td colspan="5" class="w3-center w3-text-gray">No data</td></tr>';
      if (contrib) contrib.innerHTML = '';
      if (note) note.textContent = '';
      return;
    }
    function row(label, obj, opts) {
      opts = opts || {};
      const pill = opts.dot
        ? '<span class="rev-channel-pill"><i class="rev-dot ' + opts.dot + '"></i>' + label + '</span>'
        : label;
      const trClass = opts.total ? ' class="rev-row-total"' : '';
      return '<tr' + trClass + '>' +
        '<td class="rev-sticky" scope="row">' + pill + '</td>' +
        numCell(obj.usd, money) +
        numCell(obj.zwl, money) +
        numCell(obj.zig_usd, money) +
        numCell(obj.total, money) +
        '</tr>';
    }
    body.innerHTML =
      row('HLF Total', s.hlf, { dot: 'rev-dot-hlf' }) +
      row('Organic', s.organic, { dot: 'rev-dot-org' }) +
      row('Total', s.total, { total: true });
    if (contrib) {
      const c = s.contribution_pct || {};
      function shareRow(label, pct, barClass, dot) {
        const pctVal = Math.max(0, Math.min(100, (Number(pct) || 0) * 100));
        return '<tr>' +
          '<td class="rev-sticky" scope="row"><span class="rev-channel-pill"><i class="rev-dot ' + dot + '"></i>' + label + '</span>' +
          '<div class="rev-share-bar ' + (barClass || '') + '"><span style="width:' + pctVal + '%"></span></div></td>' +
          '<td class="rev-share">' + pctFmt(pct) + '</td></tr>';
      }
      contrib.innerHTML =
        shareRow('HLF', c.hlf, '', 'rev-dot-hlf') +
        shareRow('Organic', c.organic, 'org', 'rev-dot-org') +
        '<tr class="rev-row-total"><td class="rev-sticky" scope="row">Total</td><td class="rev-share">' + pctFmt(c.total) + '</td></tr>';
    }
    if (note) note.textContent = s.note || '';
  }

  function editBtn(month) {
    if (!state.canEdit) return '';
    return '<button type="button" class="rev-edit-btn" data-month="' + month + '">Edit</button>';
  }

  function sumField(months, field) {
    return (months || []).reduce(function (a, m) { return a + (Number(m[field]) || 0); }, 0);
  }

  function metricRow(m, fields, fmtFn) {
    return '<tr>' +
      '<td class="rev-sticky" scope="row">' + (m.month_name || MONTH_NAMES[m.month] || m.month) + '</td>' +
      numCell(m[fields[0]], fmtFn, 'rev-col-hlf') +
      numCell(m[fields[1]], fmtFn, 'rev-col-hlf') +
      numCell(m[fields[2]], fmtFn, 'rev-col-hlf') +
      numCell(m[fields[3]], fmtFn, 'rev-col-hlf') +
      numCell(m[fields[4]], fmtFn, 'rev-col-org') +
      numCell(m[fields[5]], fmtFn, 'rev-col-org') +
      numCell(m[fields[6]], fmtFn, 'rev-col-org') +
      numCell(m[fields[7]], fmtFn, 'rev-col-org') +
      '<td class="rev-actions">' + editBtn(m.month) + '</td></tr>';
  }

  function metricFoot(months, fields, fmtFn) {
    return '<tr>' +
      '<td class="rev-sticky" scope="row">Total</td>' +
      fields.map(function (f, i) {
        const colClass = i < 4 ? 'rev-col-hlf' : 'rev-col-org';
        return '<td class="rev-num ' + colClass + '">' + fmtFn(sumField(months, f)) + '</td>';
      }).join('') +
      '<td class="rev-actions"></td></tr>';
  }

  function renderRevenueTable() {
    const tbody = document.getElementById('rev-revenue-body');
    const tfoot = document.getElementById('rev-revenue-foot');
    if (!tbody) return;
    const months = (state.period && state.period.months) || [];
    if (!months.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="w3-center w3-text-gray">No months yet</td></tr>';
      if (tfoot) tfoot.innerHTML = '';
      return;
    }
    tbody.innerHTML = months.map(function (m) {
      return metricRow(m, REVENUE_FIELDS, money);
    }).join('');
    if (tfoot) tfoot.innerHTML = metricFoot(months, REVENUE_FIELDS, money);
  }

  function renderSubscribersTable() {
    const tbody = document.getElementById('rev-subs-body');
    const tfoot = document.getElementById('rev-subs-foot');
    if (!tbody) return;
    const months = (state.period && state.period.months) || [];
    if (!months.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="w3-center w3-text-gray">No months yet</td></tr>';
      if (tfoot) tfoot.innerHTML = '';
      return;
    }
    tbody.innerHTML = months.map(function (m) {
      return metricRow(m, SUBSCRIBER_FIELDS, intFmt);
    }).join('');
    if (tfoot) tfoot.innerHTML = metricFoot(months, SUBSCRIBER_FIELDS, intFmt);
  }

  function renderCharts() {
    if (typeof Chart === 'undefined') return;
    const s = (state.period && state.period.summary) || null;
    const months = (state.period && state.period.months) || [];

    destroyChart('contrib');
    destroyChart('summaryBar');
    destroyChart('revenue');
    destroyChart('subs');

    const contribEl = document.getElementById('rev-contrib-chart');
    if (contribEl && s) {
      charts.contrib = new Chart(contribEl, {
        type: 'doughnut',
        data: {
          labels: ['HLF', 'Organic'],
          datasets: [{
            data: [
              Number((s.contribution_pct || {}).hlf || 0) * 100,
              Number((s.contribution_pct || {}).organic || 0) * 100
            ],
            backgroundColor: [COLORS.hlf, COLORS.organic]
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } }
        }
      });
    }

    const summaryBarEl = document.getElementById('rev-summary-bar-chart');
    if (summaryBarEl && s) {
      charts.summaryBar = new Chart(summaryBarEl, {
        type: 'bar',
        data: {
          labels: ['USD', 'ZIG-USD', 'Total'],
          datasets: [
            {
              label: 'HLF',
              data: [s.hlf.usd, s.hlf.zig_usd, s.hlf.total],
              backgroundColor: COLORS.hlf
            },
            {
              label: 'Organic',
              data: [s.organic.usd, s.organic.zig_usd, s.organic.total],
              backgroundColor: COLORS.organic
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    const labels = months.map(function (m) { return m.month_name || MONTH_NAMES[m.month] || m.month; });

    const revEl = document.getElementById('rev-revenue-chart');
    if (revEl) {
      const type = state.chartTypes.revenue || 'bar';
      charts.revenue = new Chart(revEl, {
        type: type,
        data: {
          labels: labels,
          datasets: [
            {
              label: 'ASL HLF USD',
              data: months.map(function (m) { return Number(m.rev_asl_hlf_usd) || 0; }),
              backgroundColor: COLORS.aslHlf,
              borderColor: COLORS.aslHlf,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'Lib HLF USD',
              data: months.map(function (m) { return Number(m.rev_lib_hlf_usd) || 0; }),
              backgroundColor: COLORS.libHlf,
              borderColor: COLORS.libHlf,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'ASL Org USD',
              data: months.map(function (m) { return Number(m.rev_asl_org_usd) || 0; }),
              backgroundColor: COLORS.aslOrg,
              borderColor: COLORS.aslOrg,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'Lib Org USD',
              data: months.map(function (m) { return Number(m.rev_lib_org_usd) || 0; }),
              backgroundColor: COLORS.libOrg,
              borderColor: COLORS.libOrg,
              fill: type === 'line',
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true } }
        }
      });
    }

    const subsEl = document.getElementById('rev-subs-chart');
    if (subsEl) {
      const type = state.chartTypes.subs || 'bar';
      charts.subs = new Chart(subsEl, {
        type: type,
        data: {
          labels: labels,
          datasets: [
            {
              label: 'ASL HLF',
              data: months.map(function (m) { return Number(m.sub_asl_hlf_usd) || 0; }),
              backgroundColor: COLORS.aslHlf,
              borderColor: COLORS.aslHlf,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'Lib HLF',
              data: months.map(function (m) { return Number(m.sub_lib_hlf_usd) || 0; }),
              backgroundColor: COLORS.libHlf,
              borderColor: COLORS.libHlf,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'ASL Org',
              data: months.map(function (m) { return Number(m.sub_asl_org_usd) || 0; }),
              backgroundColor: COLORS.aslOrg,
              borderColor: COLORS.aslOrg,
              fill: type === 'line',
              tension: 0.3
            },
            {
              label: 'Lib Org',
              data: months.map(function (m) { return Number(m.sub_lib_org_usd) || 0; }),
              backgroundColor: COLORS.libOrg,
              borderColor: COLORS.libOrg,
              fill: type === 'line',
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { beginAtZero: true } }
        }
      });
    }
  }

  function updateEditVisibility() {
    const bar = document.getElementById('rev-admin-actions');
    if (bar) bar.style.display = state.canEdit ? '' : 'none';
  }

  function updateTemplateLink() {
    const code = state.period && state.period.code;
    if (!code) return;
    const template = document.getElementById('rev-template-btn');
    if (template) {
      template.href = '/akello-revenue/periods/' + encodeURIComponent(code) + '/template.xlsx';
    }
  }

  function chartImageFromConfig(config, width, height) {
    if (typeof Chart === 'undefined') return null;
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvas.style.position = 'fixed';
    canvas.style.left = '-9999px';
    canvas.style.top = '0';
    document.body.appendChild(canvas);
    const opts = Object.assign({}, config.options || {}, {
      responsive: false,
      animation: false,
      maintainAspectRatio: false
    });
    const chart = new Chart(canvas.getContext('2d'), {
      type: config.type,
      data: config.data,
      options: opts
    });
    const img = chart.toBase64Image('image/png', 1);
    chart.destroy();
    document.body.removeChild(canvas);
    return img;
  }

  function buildExportChartConfigs() {
    const s = (state.period && state.period.summary) || null;
    const months = (state.period && state.period.months) || [];
    const labels = months.map(function (m) { return m.month_name || MONTH_NAMES[m.month] || m.month; });
    const revType = state.chartTypes.revenue || 'bar';
    const subType = state.chartTypes.subs || 'bar';
    const configs = {};

    if (s) {
      configs.contrib = {
        type: 'doughnut',
        data: {
          labels: ['HLF', 'Organic'],
          datasets: [{
            data: [
              Number((s.contribution_pct || {}).hlf || 0) * 100,
              Number((s.contribution_pct || {}).organic || 0) * 100
            ],
            backgroundColor: [COLORS.hlf, COLORS.organic]
          }]
        },
        options: {
          plugins: {
            legend: { position: 'bottom' },
            title: { display: true, text: 'Contribution mix' }
          }
        }
      };
      configs.summaryBar = {
        type: 'bar',
        data: {
          labels: ['USD', 'ZIG-USD', 'Total'],
          datasets: [
            { label: 'HLF', data: [s.hlf.usd, s.hlf.zig_usd, s.hlf.total], backgroundColor: COLORS.hlf },
            { label: 'Organic', data: [s.organic.usd, s.organic.zig_usd, s.organic.total], backgroundColor: COLORS.organic }
          ]
        },
        options: {
          scales: { y: { beginAtZero: true } },
          plugins: { title: { display: true, text: 'Channel totals' } }
        }
      };
    }

    configs.revenue = {
      type: revType,
      data: {
        labels: labels,
        datasets: [
          {
            label: 'ASL HLF USD',
            data: months.map(function (m) { return Number(m.rev_asl_hlf_usd) || 0; }),
            backgroundColor: COLORS.aslHlf,
            borderColor: COLORS.aslHlf,
            fill: revType === 'line',
            tension: 0.3
          },
          {
            label: 'Lib HLF USD',
            data: months.map(function (m) { return Number(m.rev_lib_hlf_usd) || 0; }),
            backgroundColor: COLORS.libHlf,
            borderColor: COLORS.libHlf,
            fill: revType === 'line',
            tension: 0.3
          },
          {
            label: 'ASL Org USD',
            data: months.map(function (m) { return Number(m.rev_asl_org_usd) || 0; }),
            backgroundColor: COLORS.aslOrg,
            borderColor: COLORS.aslOrg,
            fill: revType === 'line',
            tension: 0.3
          },
          {
            label: 'Lib Org USD',
            data: months.map(function (m) { return Number(m.rev_lib_org_usd) || 0; }),
            backgroundColor: COLORS.libOrg,
            borderColor: COLORS.libOrg,
            fill: revType === 'line',
            tension: 0.3
          }
        ]
      },
      options: {
        scales: { y: { beginAtZero: true } },
        plugins: { title: { display: true, text: 'Monthly revenue (USD)' } }
      }
    };

    configs.subs = {
      type: subType,
      data: {
        labels: labels,
        datasets: [
          {
            label: 'ASL HLF',
            data: months.map(function (m) { return Number(m.sub_asl_hlf_usd) || 0; }),
            backgroundColor: COLORS.aslHlf,
            borderColor: COLORS.aslHlf,
            fill: subType === 'line',
            tension: 0.3
          },
          {
            label: 'Lib HLF',
            data: months.map(function (m) { return Number(m.sub_lib_hlf_usd) || 0; }),
            backgroundColor: COLORS.libHlf,
            borderColor: COLORS.libHlf,
            fill: subType === 'line',
            tension: 0.3
          },
          {
            label: 'ASL Org',
            data: months.map(function (m) { return Number(m.sub_asl_org_usd) || 0; }),
            backgroundColor: COLORS.aslOrg,
            borderColor: COLORS.aslOrg,
            fill: subType === 'line',
            tension: 0.3
          },
          {
            label: 'Lib Org',
            data: months.map(function (m) { return Number(m.sub_lib_org_usd) || 0; }),
            backgroundColor: COLORS.libOrg,
            borderColor: COLORS.libOrg,
            fill: subType === 'line',
            tension: 0.3
          }
        ]
      },
      options: {
        scales: { y: { beginAtZero: true } },
        plugins: { title: { display: true, text: 'Monthly subscribers' } }
      }
    };

    return configs;
  }

  function downloadPdfReport() {
    if (!state.period) {
      setStatus('Load a period first', true);
      return;
    }
    if (!window.jspdf || !window.jspdf.jsPDF) {
      setStatus('PDF library not loaded', true);
      return;
    }

    setStatus('Building PDF…');
    try {
      const jsPDF = window.jspdf.jsPDF;
      const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
      const pageW = doc.internal.pageSize.getWidth();
      const pageH = doc.internal.pageSize.getHeight();
      const margin = 36;
      const code = state.period.code;
      const name = state.period.name || code;
      const s = state.period.summary || {};
      const months = state.period.months || [];
      const configs = buildExportChartConfigs();

      const contribImg = configs.contrib ? chartImageFromConfig(configs.contrib, 520, 360) : null;
      const summaryBarImg = configs.summaryBar ? chartImageFromConfig(configs.summaryBar, 640, 360) : null;
      const revenueImg = chartImageFromConfig(configs.revenue, 1000, 420);
      const subsImg = chartImageFromConfig(configs.subs, 1000, 420);

      // ---- Page 1: Summary ----
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(16);
      doc.setTextColor(0, 64, 125);
      doc.text('Akello Revenue Report', margin, margin);
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(11);
      doc.setTextColor(51, 65, 85);
      doc.text(name + ' (' + code + ')', margin, margin + 18);
      doc.setFontSize(9);
      doc.setTextColor(100, 116, 139);
      doc.text('Generated ' + new Date().toLocaleString(), margin, margin + 32);
      if (s.note) {
        doc.text(String(s.note), margin, margin + 44);
      }

      const summaryHead = [['Channel', 'US$', 'ZWL', 'ZIG → USD', 'Total']];
      const summaryBody = [
        ['HLF Total', money((s.hlf || {}).usd), money((s.hlf || {}).zwl), money((s.hlf || {}).zig_usd), money((s.hlf || {}).total)],
        ['Organic', money((s.organic || {}).usd), money((s.organic || {}).zwl), money((s.organic || {}).zig_usd), money((s.organic || {}).total)],
        ['Total', money((s.total || {}).usd), money((s.total || {}).zwl), money((s.total || {}).zig_usd), money((s.total || {}).total)]
      ];
      doc.autoTable({
        startY: margin + 56,
        head: summaryHead,
        body: summaryBody,
        theme: 'grid',
        styles: { fontSize: 9, cellPadding: 4 },
        headStyles: { fillColor: [0, 64, 125], textColor: 255 },
        footStyles: { fillColor: [15, 23, 42], textColor: 255 },
        margin: { left: margin, right: margin }
      });

      let y = (doc.lastAutoTable && doc.lastAutoTable.finalY ? doc.lastAutoTable.finalY : margin + 120) + 14;
      const pct = s.contribution_pct || {};
      doc.autoTable({
        startY: y,
        head: [['Channel', 'Share']],
        body: [
          ['HLF', pctFmt(pct.hlf)],
          ['Organic', pctFmt(pct.organic)],
          ['Total', pctFmt(pct.total)]
        ],
        theme: 'grid',
        styles: { fontSize: 9, cellPadding: 4 },
        headStyles: { fillColor: [15, 118, 110], textColor: 255 },
        margin: { left: margin, right: pageW / 2 + 8 },
        tableWidth: pageW / 2 - margin - 16
      });

      y = (doc.lastAutoTable && doc.lastAutoTable.finalY ? doc.lastAutoTable.finalY : y) + 16;
      const chartH = 160;
      const chartW = (pageW - margin * 2 - 16) / 2;
      if (contribImg) {
        doc.addImage(contribImg, 'PNG', margin, y, chartW, chartH);
      }
      if (summaryBarImg) {
        doc.addImage(summaryBarImg, 'PNG', margin + chartW + 16, y, chartW, chartH);
      }

      // ---- Page 2: Revenue ----
      doc.addPage();
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(0, 64, 125);
      doc.text('Revenue — ' + code, margin, margin);
      if (revenueImg) {
        doc.addImage(revenueImg, 'PNG', margin, margin + 12, pageW - margin * 2, 200);
      }

      const revHead = [[
        'Month',
        'ASL HLF USD', 'ASL HLF ZWL', 'Lib HLF USD', 'Lib HLF ZWL',
        'ASL Org USD', 'ASL Org ZWL', 'Lib Org USD', 'Lib Org ZWL'
      ]];
      const revBody = months.map(function (m) {
        return [
          m.month_name || MONTH_NAMES[m.month] || m.month,
          money(m.rev_asl_hlf_usd), money(m.rev_asl_hlf_zwl),
          money(m.rev_lib_hlf_usd), money(m.rev_lib_hlf_zwl),
          money(m.rev_asl_org_usd), money(m.rev_asl_org_zwl),
          money(m.rev_lib_org_usd), money(m.rev_lib_org_zwl)
        ];
      });
      if (months.length) {
        revBody.push([
          'Total',
          money(sumField(months, 'rev_asl_hlf_usd')), money(sumField(months, 'rev_asl_hlf_zwl')),
          money(sumField(months, 'rev_lib_hlf_usd')), money(sumField(months, 'rev_lib_hlf_zwl')),
          money(sumField(months, 'rev_asl_org_usd')), money(sumField(months, 'rev_asl_org_zwl')),
          money(sumField(months, 'rev_lib_org_usd')), money(sumField(months, 'rev_lib_org_zwl'))
        ]);
      }
      doc.autoTable({
        startY: margin + 220,
        head: revHead,
        body: revBody,
        theme: 'grid',
        styles: { fontSize: 7, cellPadding: 3, halign: 'right' },
        columnStyles: { 0: { halign: 'left', fontStyle: 'bold' } },
        headStyles: { fillColor: [0, 64, 125], textColor: 255, fontSize: 7 },
        margin: { left: margin, right: margin }
      });

      // ---- Page 3: Subscribers ----
      doc.addPage();
      doc.setFont('helvetica', 'bold');
      doc.setFontSize(14);
      doc.setTextColor(0, 64, 125);
      doc.text('Subscribers — ' + code, margin, margin);
      if (subsImg) {
        doc.addImage(subsImg, 'PNG', margin, margin + 12, pageW - margin * 2, 200);
      }

      const subHead = [[
        'Month',
        'ASL HLF USD', 'ASL HLF ZWL', 'Lib HLF USD', 'Lib HLF ZWL',
        'ASL Org USD', 'ASL Org ZWL', 'Lib Org USD', 'Lib Org ZWL'
      ]];
      const subBody = months.map(function (m) {
        return [
          m.month_name || MONTH_NAMES[m.month] || m.month,
          intFmt(m.sub_asl_hlf_usd), intFmt(m.sub_asl_hlf_zwl),
          intFmt(m.sub_lib_hlf_usd), intFmt(m.sub_lib_hlf_zwl),
          intFmt(m.sub_asl_org_usd), intFmt(m.sub_asl_org_zwl),
          intFmt(m.sub_lib_org_usd), intFmt(m.sub_lib_org_zwl)
        ];
      });
      if (months.length) {
        subBody.push([
          'Total',
          intFmt(sumField(months, 'sub_asl_hlf_usd')), intFmt(sumField(months, 'sub_asl_hlf_zwl')),
          intFmt(sumField(months, 'sub_lib_hlf_usd')), intFmt(sumField(months, 'sub_lib_hlf_zwl')),
          intFmt(sumField(months, 'sub_asl_org_usd')), intFmt(sumField(months, 'sub_asl_org_zwl')),
          intFmt(sumField(months, 'sub_lib_org_usd')), intFmt(sumField(months, 'sub_lib_org_zwl'))
        ]);
      }
      doc.autoTable({
        startY: margin + 220,
        head: subHead,
        body: subBody,
        theme: 'grid',
        styles: { fontSize: 7, cellPadding: 3, halign: 'right' },
        columnStyles: { 0: { halign: 'left', fontStyle: 'bold' } },
        headStyles: { fillColor: [15, 118, 110], textColor: 255, fontSize: 7 },
        margin: { left: margin, right: margin }
      });

      const pageCount = doc.internal.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184);
        doc.text('Page ' + i + ' of ' + pageCount, pageW - margin, pageH - 16, { align: 'right' });
      }

      doc.save('Akello_Revenue_' + code + '.pdf');
      setStatus('PDF downloaded');
    } catch (e) {
      console.error(e);
      setStatus(e.message || 'PDF export failed', true);
    }
  }

  function renderAll() {
    renderPeriodSelect();
    renderSummary();
    renderRevenueTable();
    renderSubscribersTable();
    renderCharts();
    updateEditVisibility();
    updateTemplateLink();
  }

  async function loadPeriodsList() {
    const data = await api('/periods');
    state.periods = data.periods || [];
    state.canEdit = !!data.can_edit;
    renderPeriodSelect();
  }

  async function loadPeriod(code) {
    setStatus('Loading…');
    const data = await api('/periods/' + encodeURIComponent(code));
    state.period = data.period;
    state.canEdit = !!data.can_edit;
    state.loaded = true;
    renderAll();
    setStatus('');
  }

  function findMonth(month) {
    const months = (state.period && state.period.months) || [];
    return months.find(function (m) { return m.month === month; }) || null;
  }

  function fillModal(month, isNew) {
    const title = document.getElementById('rev-modal-title');
    const monthSel = document.getElementById('rev-modal-month');
    const existing = findMonth(month);
    if (title) {
      title.textContent = isNew
        ? 'Add month'
        : ('Edit ' + (MONTH_NAMES[month] || month));
    }
    if (monthSel) {
      monthSel.disabled = !isNew;
      monthSel.value = String(month || 3);
    }
    const src = existing || {};
    REVENUE_FIELDS.concat(SUBSCRIBER_FIELDS).forEach(function (f) {
      const el = document.getElementById('rev-field-' + f);
      if (el) el.value = src[f] != null ? src[f] : 0;
    });
  }

  function openModal(month, isNew) {
    fillModal(month, isNew);
    const modal = document.getElementById('rev-month-modal');
    if (modal) modal.style.display = 'block';
  }

  function closeModal() {
    const modal = document.getElementById('rev-month-modal');
    if (modal) modal.style.display = 'none';
  }

  function collectPayload() {
    const payload = {};
    REVENUE_FIELDS.forEach(function (f) {
      const el = document.getElementById('rev-field-' + f);
      payload[f] = el ? parseFloat(el.value) || 0 : 0;
    });
    SUBSCRIBER_FIELDS.forEach(function (f) {
      const el = document.getElementById('rev-field-' + f);
      payload[f] = el ? parseInt(el.value, 10) || 0 : 0;
    });
    return payload;
  }

  async function saveMonth() {
    if (!state.period) return;
    const monthSel = document.getElementById('rev-modal-month');
    const month = parseInt(monthSel && monthSel.value, 10);
    if (!month || month < 1 || month > 12) {
      setStatus('Select a valid month', true);
      return;
    }
    const payload = collectPayload();
    const isNew = monthSel && !monthSel.disabled;
    const saveBtn = document.getElementById('rev-modal-save');
    if (saveBtn) saveBtn.disabled = true;
    try {
      setStatus('Saving…');
      let data;
      if (isNew) {
        payload.month = month;
        data = await api('/periods/' + encodeURIComponent(state.period.code) + '/months', {
          method: 'POST',
          body: JSON.stringify(payload)
        });
      } else {
        data = await api(
          '/periods/' + encodeURIComponent(state.period.code) + '/months/' + month,
          { method: 'PUT', body: JSON.stringify(payload) }
        );
      }
      state.period = data.period;
      renderAll();
      closeModal();
      setStatus('Saved');
    } catch (e) {
      setStatus(e.message || 'Save failed', true);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  async function createPeriod() {
    const code = window.prompt('New period code (e.g. FY2028):');
    if (!code) return;
    const name = window.prompt('Display name:', code.trim().toUpperCase()) || code.trim().toUpperCase();
    try {
      setStatus('Creating period…');
      const data = await api('/periods', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim(), name: name.trim() })
      });
      await loadPeriodsList();
      await loadPeriod(data.period.code);
      setStatus('Period created');
    } catch (e) {
      setStatus(e.message || 'Create failed', true);
    }
  }

  async function importWorkbook(file) {
    if (!state.period || !file) return;
    const form = new FormData();
    form.append('file', file);
    form.append('mode', 'upsert');
    setStatus('Importing…');
    try {
      const headers = { Accept: 'application/json' };
      const token = csrfToken();
      if (token) headers['X-CSRFToken'] = token;
      const res = await fetch(
        '/akello-revenue/periods/' + encodeURIComponent(state.period.code) + '/import',
        { method: 'POST', credentials: 'same-origin', headers: headers, body: form }
      );
      const data = await res.json().catch(function () { return {}; });
      if (!res.ok || !data.success) {
        throw new Error(data.error || ('Import failed (' + res.status + ')'));
      }
      state.period = data.period;
      renderAll();
      const errCount = (data.errors || []).length;
      setStatus(
        'Imported ' + (data.applied || 0) + ' month(s)' +
          (errCount ? (' · ' + errCount + ' warning(s)') : '')
      );
    } catch (e) {
      setStatus(e.message || 'Import failed', true);
    }
  }

  function bindEvents() {
    const sel = document.getElementById('rev-period-select');
    if (sel) {
      sel.addEventListener('change', function () {
        loadPeriod(sel.value).catch(function (e) {
          setStatus(e.message || 'Load failed', true);
        });
      });
    }
    const addBtn = document.getElementById('rev-add-month-btn');
    if (addBtn) {
      addBtn.addEventListener('click', function () {
        const used = ((state.period && state.period.months) || []).map(function (m) { return m.month; });
        const next = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2].find(function (m) {
          return used.indexOf(m) === -1;
        }) || 3;
        openModal(next, true);
      });
    }
    const newPeriodBtn = document.getElementById('rev-new-period-btn');
    if (newPeriodBtn) newPeriodBtn.addEventListener('click', createPeriod);
    const saveBtn = document.getElementById('rev-modal-save');
    if (saveBtn) saveBtn.addEventListener('click', saveMonth);
    const cancelBtn = document.getElementById('rev-modal-cancel');
    if (cancelBtn) cancelBtn.addEventListener('click', closeModal);
    const closeBtn = document.getElementById('rev-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);

    const importBtn = document.getElementById('rev-import-btn');
    const importFile = document.getElementById('rev-import-file');
    if (importBtn && importFile) {
      importBtn.addEventListener('click', function () { importFile.click(); });
      importFile.addEventListener('change', function () {
        const file = importFile.files && importFile.files[0];
        if (file) importWorkbook(file);
        importFile.value = '';
      });
    }

    const reportBtn = document.getElementById('rev-report-btn');
    if (reportBtn) {
      reportBtn.addEventListener('click', function () {
        downloadPdfReport();
      });
    }

    document.querySelectorAll('.rev-chart-type').forEach(function (btn) {
      btn.addEventListener('click', function () {
        const chart = btn.getAttribute('data-chart');
        const type = btn.getAttribute('data-type');
        if (!chart || !type) return;
        state.chartTypes[chart] = type;
        const group = btn.parentElement;
        if (group) {
          group.querySelectorAll('.rev-chart-type').forEach(function (b) {
            if (b.getAttribute('data-chart') === chart) {
              b.classList.toggle('w3-blue', b === btn);
              b.classList.toggle('w3-white', b !== btn);
            }
          });
        }
        renderCharts();
      });
    });

    document.addEventListener('click', function (ev) {
      const btn = ev.target.closest && ev.target.closest('.rev-edit-btn');
      if (!btn) return;
      const month = parseInt(btn.getAttribute('data-month'), 10);
      openModal(month, false);
    });
  }

  async function initAndLoad() {
    if (!document.getElementById('revenue')) return;
    try {
      await loadPeriodsList();
      const sel = document.getElementById('rev-period-select');
      const code = (sel && sel.value) || (state.periods[0] && state.periods[0].code) || 'FY2027';
      await loadPeriod(code);
    } catch (e) {
      setStatus(e.message || 'Failed to load revenue data', true);
    }
  }

  function onTabOpened() {
    if (!state.loaded) {
      initAndLoad();
    } else {
      renderCharts();
    }
  }

  function boot() {
    bindEvents();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  global.AkelloRevenue = {
    onTabOpened: onTabOpened,
    reload: initAndLoad,
    getState: function () { return state; }
  };
})(window);
