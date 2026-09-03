let currentSmartlearningMetrics = null;

function formatDate(date) {
  return date.toISOString().split("T")[0];
}

function toggleSpinner(show) {
  const spinner = document.getElementById("metrics-spinner");
  if (spinner) spinner.style.display = show ? "block" : "none";
  const cells = document.querySelectorAll(".metrics-loading-cell");
  cells.forEach((el) => {
    el.style.display = show ? "" : "none";
  });
}

function getDateRange() {
  const today = new Date();
  const last30 = new Date();
  last30.setDate(today.getDate() - 30);

  const startInput =
    document.getElementById("mon-start-date") ||
    document.getElementById("start-date");
  const endInput =
    document.getElementById("mon-end-date") ||
    document.getElementById("end-date");

  const startDate = startInput?.value || formatDate(last30);
  const endDate = endInput?.value || formatDate(today);

  return { startDate, endDate };
}

function fetchAllMetrics(startDate, endDate) {
  const range = startDate && endDate ? { startDate, endDate } : getDateRange();
  toggleSpinner(true);
  const exportBtn = document.getElementById("export-btn");
  if (exportBtn) exportBtn.disabled = true;

  fetchAkelloMetrics(range.startDate, range.endDate);
  fetchSmartlearningMetrics(range.startDate, range.endDate);
}

function fetchAkelloMetrics(startDate, endDate) {
  const payload = {
    start_date: startDate,
    end_date: endDate,
  };

  fetch("/akello-library-metrics", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
    .then((response) => {
      if (!response.ok) throw new Error("Akello API call failed");
      return response.json();
    })
    .then((data) => {
      renderAkelloTable(data);
      updateLibrarySummary(data);
    })
    .catch((err) => {
      console.error("Akello fetch error:", err);
      const libTable = document.getElementById("library-dataTable");
      if (libTable)
        libTable.innerHTML =
          "<tr><td colspan='2'>Failed to load Akello data</td></tr>";
    });
}

function renderAkelloTable(data) {
  const tbody = document.getElementById("library-dataTable");
  if (!tbody) return;
  tbody.innerHTML = "";

  for (const key in data) {
    const value = data[key];

    if (key === "Total Revenue (by currency)") {
      continue;
    }

    if (typeof value === "object" && value !== null) {
      for (const currency in value) {
        const row = document.createElement("tr");
        row.innerHTML = `<td>${key} (${currency})</td><td>${value[currency]}</td>`;
        tbody.appendChild(row);
      }
    } else {
      const row = document.createElement("tr");
      row.innerHTML = `<td>${key}</td><td>${value}</td>`;
      tbody.appendChild(row);
    }
  }
}

async function fetchSmartlearningMetrics(startDate, endDate) {
  const formData = new URLSearchParams();
  formData.append("start_date", startDate);
  formData.append("end_date", endDate);

  try {
    const response = await fetch("/smartlearning-metrics-update", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: formData.toString(),
    });

    if (!response.ok) throw new Error("SmartLearning API call failed");

    const smartlearningData = await response.json();
    currentSmartlearningMetrics = smartlearningData;

    renderSmartlearningTable(smartlearningData);
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

    if (key === "asl_revenue") {
      continue;
    }

    const row = document.createElement("tr");
    row.innerHTML = `<td class="w3-hover-shadow">${key}</td><td>${value}</td>`;
    tbody.appendChild(row);
  }

  if (smartlearningData.asl_active30 !== undefined) {
    const active30 = document.getElementById("active30-display");
    if (active30) active30.innerText = smartlearningData.asl_active30;
  }
}

function toNumString(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  return Number.isFinite(n) ? n.toLocaleString() : String(v);
}

function firstKey(obj, keys) {
  if (!obj) return undefined;
  for (const k of keys) {
    if (k in obj && obj[k] !== null && obj[k] !== undefined) return obj[k];
  }
  return undefined;
}

function updateSmartlearningSummary(data) {
  const elActive30 = document.getElementById("mon-metric-active30");
  const elRegMonth = document.getElementById("mon-metric-reg-month");
  const elRegToday = document.getElementById("mon-metric-reg-today");
  if (!elActive30 && !elRegMonth && !elRegToday) return;

  const active30 = firstKey(data, [
    "asl_active30",
    "active30",
    "active_30_days",
    "total_active_30d",
  ]);
  const regMonth = firstKey(data, [
    "registrations_month",
    "monthly_registrations",
    "smartlearning_registrations_month",
    "registrations_this_month",
    "asl_registrations",
  ]);
  const regToday = firstKey(data, [
    "registrations_today",
    "today_registrations",
    "smartlearning_registrations_today",
  ]);

  if (elActive30) elActive30.textContent = toNumString(active30);
  if (elRegMonth) elRegMonth.textContent = toNumString(regMonth);
  if (elRegToday) elRegToday.textContent = toNumString(regToday);
}

function updateLibrarySummary(data) {
  const elActive30 = document.getElementById("mon-lib-active30");
  const elRegMonth = document.getElementById("mon-lib-reg-month");
  const elRegToday = document.getElementById("mon-lib-reg-today");
  if (!elActive30 && !elRegMonth && !elRegToday) return;

  const active30 = firstKey(data, [
    "active30",
    "active_30_days",
    "total_active_30d",
    "total_active_users",
    "active_users_30d",
  ]);
  const regMonth = firstKey(data, [
    "registrations_month",
    "monthly_registrations",
    "registrations_this_month",
    "Total Registrations",
  ]);
  const regToday = firstKey(data, [
    "registrations_today",
    "today_registrations",
  ]);

  if (elActive30) elActive30.textContent = toNumString(active30);
  if (elRegMonth) elRegMonth.textContent = toNumString(regMonth);
  if (elRegToday) elRegToday.textContent = toNumString(regToday);
}

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

document.addEventListener("DOMContentLoaded", () => {
  const startInput =
    document.getElementById("mon-start-date") ||
    document.getElementById("start-date");
  const endInput =
    document.getElementById("mon-end-date") ||
    document.getElementById("end-date");

  // If monitor page owns dates, wait for its refresh() to call fetchAllMetrics.
  // Otherwise initialize defaults and load metrics (legacy pages).
  if (document.getElementById("mon-start-date")) {
    return;
  }

  const today = new Date();
  const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  if (startInput) startInput.value = formatDate(firstOfMonth);
  if (endInput) endInput.value = formatDate(today);
  fetchAllMetrics();
});
