// Global function to load smartlearning data with optional date range
window.loadSmartlearningData = function(startDate = null, endDate = null) {
  const schoolId = document.body.dataset.schoolId;
  const schoolName = document.body.dataset.schoolName;

  const payload = {
    school_id: schoolId,
    school_name: schoolName
  };
  
  if (startDate && endDate) {
    payload.start_date = startDate;
    payload.end_date = endDate;
  }

  fetch('/api/smartlearning-school', {
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
      document.getElementById("total-count").textContent = "Error loading data";
      return;
    }

    // Set total count
    document.getElementById("total-count").textContent = data.total_count;

    // Build header
    const headerRow = document.getElementById("student-table-header");
    headerRow.innerHTML = '';
    data.columns.forEach(col => {
      const th = document.createElement("th");
      th.textContent = col.replace(/_/g, ' ').toUpperCase();
      headerRow.appendChild(th);
    });

    // Create tbody reference
    const tbody = document.querySelector("#student-table tbody");

    // Function to render table rows
    function renderTableRows(filteredRows) {
      tbody.innerHTML = '';
      filteredRows.forEach(row => {
        const tr = document.createElement("tr");
        data.columns.forEach(col => {
          const td = document.createElement("td");
          td.textContent = row[col];
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }

    // Populate full table initially
    renderTableRows(data.rows);

    // Calculate and display grade-wise counts
    const gradeCounts = {};
    data.rows.forEach(row => {
      const grade = row.grade || 'Unknown';
      gradeCounts[grade] = (gradeCounts[grade] || 0) + 1;
    });

    // Build grade filter dropdown
    const filterContainer = document.getElementById("grade-filter") || document.createElement("div");
    filterContainer.id = "grade-filter";
    filterContainer.style.margin = "10px 0";

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
    document.getElementById("student-table").before(filterContainer);

    // Handle dropdown change
    gradeSelect.addEventListener("change", function () {
      const selectedGrade = this.value;
      if (selectedGrade === "all") {
        renderTableRows(data.rows);
      } else {
        const filtered = data.rows.filter(row => String(row.grade) === selectedGrade);
        renderTableRows(filtered);
      }
    });

    // ===============================
    // Grade count cards (Modern style)
    // ===============================
    const gradeCountsDiv = document.getElementById("grade-counts");
    gradeCountsDiv.innerHTML = '<h4 class="w3-hide">Students by Grade</h4>';

    // Inject lightweight styles for grade cards once
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

    // nice color gradients to rotate through
    const gradients = [
      'linear-gradient(135deg,#6366f1,#22c55e)',
      'linear-gradient(135deg,#3b82f6,#06b6d4)',
      'linear-gradient(135deg,#f59e0b,#ef4444)',
      'linear-gradient(135deg,#8b5cf6,#ec4899)',
      'linear-gradient(135deg,#10b981,#14b8a6)' 
    ];

    // Sort grades: numeric ascending first, then others alphabetically
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
    document.getElementById("total-count").textContent = "Error loading data";
  });
};

// Load data on page load with default date range
document.addEventListener("DOMContentLoaded", function () {
  window.loadSmartlearningData();
});
