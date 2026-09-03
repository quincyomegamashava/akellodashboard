// Global function to load smartlearning data with optional date range
window.loadSmartlearningData = function(startDate = null, endDate = null) {
  const schoolEl = document.getElementById('school-profile') || document.body;
  const schoolId = schoolEl.dataset.schoolId || schoolEl.dataset.aslSchoolId;
  const schoolName = schoolEl.dataset.schoolName;

  const payload = {};
  if (schoolId) payload.school_id = schoolId;
  if (schoolName) payload.school_name = schoolName;

  if (!payload.school_id && !payload.school_name) {
    const totalEl = document.getElementById("total-count");
    if (totalEl) totalEl.textContent = "Missing school";
    return Promise.resolve();
  }

  if (startDate && endDate) {
    payload.start_date = startDate;
    payload.end_date = endDate;
  }

  const totalEl = document.getElementById("total-count");
  if (totalEl) totalEl.textContent = "…";

  return fetch('/api/smartlearning-school', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      console.error("API Error:", data.error);
      if (totalEl) totalEl.textContent = "Error";
      return;
    }

    if (totalEl) totalEl.textContent = data.total_count;

    const headerRow = document.getElementById("student-table-header");
    if (headerRow) {
      headerRow.innerHTML = '';
      (data.columns || []).forEach(col => {
        const th = document.createElement("th");
        th.textContent = col.replace(/_/g, ' ').toUpperCase();
        headerRow.appendChild(th);
      });
    }

    const tbody = document.querySelector("#student-table tbody");
    if (!tbody) return;

    function renderTableRows(filteredRows) {
      tbody.innerHTML = '';
      filteredRows.forEach(row => {
        const tr = document.createElement("tr");
        (data.columns || []).forEach(col => {
          const td = document.createElement("td");
          if (col === 'username' && row[col]) {
            const link = document.createElement("a");
            link.href = `/learner-profile/${encodeURIComponent(row[col])}`;
            link.textContent = row[col];
            link.style.color = '#6366f1';
            link.style.textDecoration = 'none';
            link.style.fontWeight = '600';
            link.style.cursor = 'pointer';
            td.appendChild(link);
          } else {
            td.textContent = row[col] != null ? String(row[col]) : '';
          }
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    renderTableRows(data.rows || []);

    const gradeCounts = {};
    (data.rows || []).forEach(row => {
      const grade = row.grade || 'Unknown';
      gradeCounts[grade] = (gradeCounts[grade] || 0) + 1;
    });

    let filterContainer = document.getElementById("grade-filter");
    if (!filterContainer) {
      filterContainer = document.createElement("div");
      filterContainer.id = "grade-filter";
      filterContainer.style.margin = "10px 0";
      const table = document.getElementById("student-table");
      if (table) table.before(filterContainer);
    }
    filterContainer.innerHTML = '';

    const gradeSelect = document.createElement("select");
    gradeSelect.style.padding = "5px";
    gradeSelect.style.fontSize = "14px";

    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = "All Grades";
    gradeSelect.appendChild(allOption);

    Object.keys(gradeCounts).sort((a, b) => parseInt(a) - parseInt(b)).forEach(grade => {
      const option = document.createElement("option");
      option.value = grade;
      option.textContent = `Grade ${grade}`;
      gradeSelect.appendChild(option);
    });

    filterContainer.appendChild(gradeSelect);

    gradeSelect.addEventListener("change", function () {
      const selectedGrade = this.value;
      if (selectedGrade === "all") {
        renderTableRows(data.rows || []);
      } else {
        const filtered = (data.rows || []).filter(row => String(row.grade) === selectedGrade);
        renderTableRows(filtered);
      }
    });

    const gradeCountsDiv = document.getElementById("grade-counts");
    if (!gradeCountsDiv) return;
    gradeCountsDiv.innerHTML = '<h4 class="w3-hide">Students by Grade</h4>';

    (function injectGradeCardStyles(){
      const STYLE_ID = 'grade-cards-styles';
      if (document.getElementById(STYLE_ID)) return;
      const css = `
        .grade-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
        .grade-card{background:#fff;border:1px solid #e9eef5;border-radius:14px;padding:14px 14px 12px;box-shadow:0 6px 16px rgba(13,38,76,.06);transition:transform .05s ease, box-shadow .2s ease}
        .grade-card:hover{transform:translateY(-1px);box-shadow:0 10px 24px rgba(13,38,76,.10)}
        .gc-icon{width:38px;height:38px;border-radius:10px;display:grid;place-items:center;color:#fff;font-size:16px;margin-bottom:10px}
        .gc-title{font-size:.80rem;color:#6b7a90;text-transform:uppercase;letter-spacing:.04em}
        .gc-value{font:700 1.4rem/1.1 system-ui,-apple-system,Segoe UI,Roboto;color:#0b213f;margin-top:4px}
        .gc-sub{font-size:.75rem;color:#7d8aa3}
      `;
      const style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = css;
      document.head.appendChild(style);
    })();

    const gradients = [
      'linear-gradient(135deg,#6366f1,#22c55e)',
      'linear-gradient(135deg,#3b82f6,#06b6d4)',
      'linear-gradient(135deg,#f59e0b,#ef4444)',
      'linear-gradient(135deg,#8b5cf6,#ec4899)',
      'linear-gradient(135deg,#10b981,#14b8a6)'
    ];

    const gradeKeys = Object.keys(gradeCounts).sort((a,b)=>{
      const na = parseInt(a,10); const nb = parseInt(b,10);
      const ia = Number.isFinite(na); const ib = Number.isFinite(nb);
      if (ia && ib) return na - nb;
      if (ia) return -1; if (ib) return 1;
      return String(a).localeCompare(String(b));
    });

    const gradeContainer = document.createElement("div");
    gradeContainer.className = "grade-grid";

    gradeKeys.forEach((grade, idx) => {
      const card = document.createElement("div");
      card.className = "grade-card";

      const icon = document.createElement('div');
      icon.className = 'gc-icon';
      icon.style.background = gradients[idx % gradients.length];
      icon.innerHTML = '<i class="fa fa-users"></i>';

      const title = document.createElement('div');
      title.className = 'gc-title';
      title.textContent = `Grade ${grade}`;

      const value = document.createElement('div');
      value.className = 'gc-value';
      value.textContent = (gradeCounts[grade] || 0).toLocaleString();

      const sub = document.createElement('div');
      sub.className = 'gc-sub';
      sub.textContent = 'students';

      card.appendChild(icon);
      card.appendChild(title);
      card.appendChild(value);
      card.appendChild(sub);
      gradeContainer.appendChild(card);
    });

    gradeCountsDiv.appendChild(gradeContainer);
  })
  .catch(error => {
    console.error("Fetch error:", error);
    if (totalEl) totalEl.textContent = "Error";
  });
};

// Do not auto-fetch on DOMContentLoaded — page script drives loadAllData with dates.
