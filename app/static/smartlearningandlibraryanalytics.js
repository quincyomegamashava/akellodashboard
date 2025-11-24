let currentSmartlearningMetrics = null;

function formatDate(date) {
  return date.toISOString().split("T")[0];
}

function toggleSpinner(show) {
  const spinner = document.getElementById("spinner");
  if (spinner) spinner.style.display = show ? "block" : "none";
}

function getDateRange() {
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

  const startInput = document.getElementById("start-date");
  const endInput = document.getElementById("end-date");

  const startDate = startInput?.value || formatDate(firstOfMonth);
  const endDate = endInput?.value || formatDate(today);

  return { startDate, endDate };
}

function fetchAllMetrics() {
  const { startDate, endDate } = getDateRange();
  toggleSpinner(true);
  const exportBtn = document.getElementById("export-btn");
  if (exportBtn) exportBtn.disabled = true;

  fetchAkelloMetrics(startDate, endDate);
  fetchSmartlearningMetrics(startDate, endDate);
}

// 🔵 AKELLO METRICS
function fetchAkelloMetrics(startDate, endDate) {
  const payload = {
    start_date: startDate,
    end_date: endDate
  };

  fetch("/akello-library-metrics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  })
    .then(response => {
      if (!response.ok) throw new Error("Akello API call failed");
      return response.json();
  })
    .then(data => {
      renderAkelloTable(data);
      // Try to update Library summary metrics on monitor if present
      updateLibrarySummary(data);
    })
    .catch(err => {
      console.error("Akello fetch error:", err);
      const libTable = document.getElementById("library-dataTable");
      if (libTable) libTable.innerHTML = "<tr><td colspan='2'>Failed to load Akello data</td></tr>";
    });
}

function renderAkelloTable(data) {
  const tbody = document.getElementById("library-dataTable");
  tbody.innerHTML = "";

  for (const key in data) {
    const value = data[key];

    // Hide the "Total Revenue (by currency)" row in the Library Month to Date table
    if (key === "Total Revenue (by currency)") {
      continue;
    }

    if (typeof value === "object" && value !== null) {
      for (const currency in value) {
        const row = document.createElement("tr");
        row.setAttribute("onclick", `document.getElementById('${key}').style.display='block'`);
        row.innerHTML = `<td>${key} (${currency})</td><td>${value[currency]}</td>`;
        tbody.appendChild(row);
      }
    } else {
      const row = document.createElement("tr");
      row.setAttribute("onclick", `document.getElementById('${key}').style.display='block'`);
      row.innerHTML = `<td>${key}</td><td>${value}</td>`;
      tbody.appendChild(row);
    }
  }
}

// 🟢 SMARTLEARNING METRICS
async function fetchSmartlearningMetrics(startDate, endDate) {
  const formData = new URLSearchParams();
  formData.append("start_date", startDate);
  formData.append("end_date", endDate);

  try {
    const response = await fetch("/smartlearning-metrics-update", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: formData.toString()
    });

    if (!response.ok) throw new Error("SmartLearning API call failed");

    const smartlearningData = await response.json();
    currentSmartlearningMetrics = smartlearningData;

    renderSmartlearningTable(smartlearningData);
    // Update compact Smartlearning metrics on monitor if present
    updateSmartlearningSummary(smartlearningData);
    const exportBtn = document.getElementById("export-btn");
    if (exportBtn) exportBtn.disabled = false;
  } catch (error) {
    const tbody = document.querySelector("#smartlearning-table tbody");
    if (tbody) {
      tbody.innerHTML = `<tr><td colspan="2" style="color: red;">Error: ${error.message}</td></tr>`;
    }
    currentSmartlearningMetrics = null;
  } finally {
    toggleSpinner(false);
  }
}

function renderSmartlearningTable(smartlearningData) {
  const tbody = document.querySelector("#smartlearning-table tbody");
  if (!tbody) return;

  tbody.innerHTML = "";

  for (const key in smartlearningData) {
    const value = smartlearningData[key];

    // Hide the asl_revenue row in the Smartlearning Month to Date table
    if (key === "asl_revenue") {
      continue;
    }

    if (key === "asl_revenue" && Array.isArray(value)) {
      value.forEach(entry => {
        const row = document.createElement("tr");
        row.setAttribute("onclick", `document.getElementById('${key}').style.display='block'`);
        row.innerHTML = `<td>asl_revenue (${entry.currency})</td><td>${entry.amount}</td>`;
        tbody.appendChild(row);
      });
    } else {
      const row = document.createElement("tr");
      row.setAttribute("onclick", `document.getElementById('${key}').style.display='block'`);
      row.innerHTML = `<td clas="w3-hover-shadow" style="cursor:pointer;">${key}</td><td>${value}</td>`;
      tbody.appendChild(row);
    }
  }

  if (smartlearningData.asl_active30 !== undefined) {
    const active30 = document.getElementById("active30-display");
    if (active30) active30.innerText = smartlearningData.asl_active30;
  }
}

// ==== Monitor compact metrics updaters ====
function toNumString(v){
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString() : String(v);
}

function firstKey(obj, keys){
  if (!obj) return undefined;
  for (const k of keys){ if (k in obj && obj[k] !== null && obj[k] !== undefined) return obj[k]; }
  return undefined;
}

function updateSmartlearningSummary(data){
  // Smartlearning compact metrics (if elements exist)
  const elActive30 = document.getElementById('mon-metric-active30');
  const elRegMonth = document.getElementById('mon-metric-reg-month');
  const elRegToday = document.getElementById('mon-metric-reg-today');
  if (!elActive30 && !elRegMonth && !elRegToday) return; // not on this page

  const active30 = firstKey(data, ['asl_active30','active30','active_30_days','total_active_30d']);
  const regMonth = firstKey(data, ['registrations_month','monthly_registrations','smartlearning_registrations_month','registrations_this_month']);
  const regToday = firstKey(data, ['registrations_today','today_registrations','smartlearning_registrations_today']);

  if (elActive30) elActive30.textContent = toNumString(active30);
  if (elRegMonth) elRegMonth.textContent = toNumString(regMonth);
  if (elRegToday) elRegToday.textContent = toNumString(regToday);
}

function updateLibrarySummary(data){
  // Library compact metrics (if elements exist)
  const elActive30 = document.getElementById('mon-lib-active30');
  const elRegMonth = document.getElementById('mon-lib-reg-month');
  const elRegToday = document.getElementById('mon-lib-reg-today');
  if (!elActive30 && !elRegMonth && !elRegToday) return;

  // Heuristic key mapping depending on API shape
  const active30 = firstKey(data, ['active30','active_30_days','total_active_30d','total_active_users','active_users_30d']);
  const regMonth = firstKey(data, ['registrations_month','monthly_registrations','registrations_this_month']);
  const regToday = firstKey(data, ['registrations_today','today_registrations']);

  if (elActive30) elActive30.textContent = toNumString(active30);
  if (elRegMonth) elRegMonth.textContent = toNumString(regMonth);
  if (elRegToday) elRegToday.textContent = toNumString(regToday);
}

// 📁 Export SmartLearning JSON
function exportMetrics() {
  if (!currentSmartlearningMetrics) return;

  const blob = new Blob(
    [JSON.stringify(currentSmartlearningMetrics, null, 2)],
    { type: "application/json" }
  );
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = "smartlearning_metrics.json";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// 🚀 Init on load
document.addEventListener("DOMContentLoaded", () => {
  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);

  const startInput = document.getElementById("start-date");
  const endInput = document.getElementById("end-date");

  if (startInput) startInput.value = formatDate(firstOfMonth);
  if (endInput) endInput.value = formatDate(today);

  fetchAllMetrics();
});




// Export SmartLearning metrics
function exportMetrics() {
    const smartlearningTable = document.getElementById('smartlearning-table');
    const libraryTable = document.getElementById('library-mets');
    
    // Create workbook
    const wb = XLSX.utils.book_new();
    
    // Process SmartLearning data
    const smartlearningData = [];
    const smartlearningRows = smartlearningTable.querySelectorAll('tbody tr:not(:first-child)');
    smartlearningRows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
            smartlearningData.push({
                Metric: cells[0].textContent.trim(),
                Value: cells[1].textContent.trim()
            });
        }
    });
    
    // Process Library data
    const libraryData = [];
    const libraryRows = libraryTable.querySelectorAll('tbody tr:not(:first-child)');
    libraryRows.forEach(row => {
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
            libraryData.push({
                Metric: cells[0].textContent.trim(),
                Usage: cells[1].textContent.trim()
            });
        }
    });
    
    // Add sheets to workbook
    if (smartlearningData.length > 0) {
        const ws1 = XLSX.utils.json_to_sheet(smartlearningData);
        XLSX.utils.book_append_sheet(wb, ws1, "SmartLearning Metrics");
    }
    
    if (libraryData.length > 0) {
        const ws2 = XLSX.utils.json_to_sheet(libraryData);
        XLSX.utils.book_append_sheet(wb, ws2, "Library Metrics");
    }
    
    // Set column widths
    if (wb.Sheets["SmartLearning Metrics"]) {
        wb.Sheets["SmartLearning Metrics"]['!cols'] = [
            { wch: 25 },  // Metric
            { wch: 20 }   // Value
        ];
    }
    
    if (wb.Sheets["Library Metrics"]) {
        wb.Sheets["Library Metrics"]['!cols'] = [
            { wch: 25 },  // Metric
            { wch: 20 }   // Usage
        ];
    }
    
    XLSX.writeFile(wb, `SmartLearning_and_Library_Metrics_${new Date().toISOString().split('T')[0]}.xlsx`);
}