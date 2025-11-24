
  const form = document.getElementById('dateForm');

  // -------------- LIBRARY ANALYTICS --------------
  const libTable = document.getElementById('dataTable');
  const libChartCtx = document.getElementById('libraryChart').getContext('2d');
  const libChartContainer = document.getElementById('chartContainer');
  const libTableWrapper = document.getElementById('tableWrapper');
  let libChart, libChartType = 'bar';

  function formatLabel(label) {
    return label.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function fetchLibraryMetrics(start, end) {
    libTable.innerHTML = '<tr><td colspan="2">Loading...</td></tr>';
    if (libChart) libChart.destroy();

    fetch(`/api/library-analytics?start_date=${start}&end_date=${end}`)
      .then(res => res.json())
      .then(data => {
        libTable.innerHTML = '';
        for (const key in data) {
          const row = document.createElement('tr');
          row.innerHTML = `<td>${formatLabel(key)}</td><td>${data[key]}</td>`;
          libTable.appendChild(row);
        }

        const labels = Object.keys(data).map(formatLabel);
        const values = Object.values(data);

        libChart = new Chart(libChartCtx, {
          type: libChartType,
          data: {
            labels: labels,
            datasets: [{
              label: 'Library Analytics',
              data: values,
              backgroundColor: ['#4dc9f6', '#f67019', '#f53794', '#537bc4'],
              borderColor: '#fff',
              borderWidth: 1
            }]
          },
          options: {
            responsive: true,
            plugins: {
              legend: { display: libChartType === 'pie' },
              title: { display: true, text: 'Library Usage Metrics' }
            }
          }
        });
      })
      .catch(() => {
        libTable.innerHTML = '<tr><td colspan="2">Error loading data.</td></tr>';
      });
  }

  function toggleLibChartType() {
    libChartType = libChartType === 'bar' ? 'pie' : 'bar';
    const start = document.getElementById('start_date').value;
    const end = document.getElementById('end_date').value;
    fetchLibraryMetrics(start, end);
  }

  function toggleLibView() {
    const visible = libChartContainer.style.display === 'block';
    libChartContainer.style.display = visible ? 'none' : 'block';
    libTableWrapper.style.display = visible ? 'block' : 'none';
  }

  // -------------- ASL ANALYTICS --------------
  let analyticsData = null;
  let usageChart, usageChartType = 'bar';
  let allChart, allChartType = 'bar';

  const usageCtx = document.getElementById('usageChart').getContext('2d');
  const allMetricsCtx = document.getElementById('allMetricsChart').getContext('2d');

  function fetchASLMetrics(start, end) {
    $("#analytics-table tbody").empty().append(`<tr><td colspan="2">Loading...</td></tr>`);
    $.ajax({
      url: `/api/analytics-summary?start_date=${start}&end_date=${end}`,
      method: "GET",
      dataType: "json",
      success: function (data) {
        analyticsData = data;
        $("#aslloader").hide();

        // Populate main table
        const tbody = $("#analytics-table tbody");
        tbody.empty();
        for (const key in data) {
          if (key === "asl_revenue") {
            data[key].forEach(entry => {
              tbody.append(`<tr><td>Revenue (${entry.currency})</td><td>${entry.value}</td></tr>`);
            });
          } else {
            tbody.append(`<tr><td>${formatLabel(key)}</td><td>${data[key]}</td></tr>`);
          }
        }

        // Populate all metrics
        const metricKeys = ["asl_active_30", "asl_registrations", "asl_unique_subscribers", "asl_unique_users"];
        const labelMap = {
          asl_active_30: "Total Active 30",
          asl_registrations: "Total Registrations",
          asl_unique_subscribers: "Total Unique Subscribers",
          asl_unique_users: "Total Unique Users"
        };

        const allBody = $("#all_metrics tbody");
        allBody.empty();
        metricKeys.forEach(key => {
          allBody.append(`<tr><td>${labelMap[key]}</td><td>${data[key]}</td></tr>`);
        });
        $("#all_metrics").show();

        renderUsageChart(data);
        renderAllMetricsChart(data);
      },
      error: function () {
        $("#aslloader").text("Failed to load analytics data.");
      }
    });
  }

  function renderUsageChart(data) {
    const labels = [], values = [];
    for (const key in data) {
      if (key === "asl_revenue") {
        data[key].forEach(entry => {
          labels.push(`Revenue (${entry.currency})`);
          values.push(entry.value);
        });
      } else {
        labels.push(formatLabel(key));
        values.push(data[key]);
      }
    }

    if (usageChart) usageChart.destroy();
    usageChart = new Chart(usageCtx, {
      type: usageChartType,
      data: {
        labels,
        datasets: [{
          label: 'Usage',
          data: values,
          backgroundColor: ['#4dc9f6', '#f67019', '#f53794', '#acc236'],
          borderColor: '#fff',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: usageChartType === 'pie' },
          title: { display: true, text: 'ASL Usage Metrics' }
        }
      }
    });
  }

  function renderAllMetricsChart(data) {
    const keys = ["asl_active_30", "asl_registrations", "asl_unique_subscribers", "asl_unique_users"];
    const labels = ["Total Active 30", "Total Registrations", "Total Unique Subscribers", "Total Unique Users"];
    const values = keys.map(k => data[k]);

    if (allChart) allChart.destroy();
    allChart = new Chart(allMetricsCtx, {
      type: allChartType,
      data: {
        labels,
        datasets: [{
          label: 'User Metrics',
          data: values,
          backgroundColor: ['#36a2eb', '#ff6384', '#4bc0c0', '#9966ff'],
          borderColor: '#fff',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: allChartType === 'pie' },
          title: { display: true, text: 'All User Metrics' }
        }
      }
    });
  }

  function toggleUsageChartType() {
    usageChartType = usageChartType === 'bar' ? 'pie' : 'bar';
    renderUsageChart(analyticsData);
  }

  function toggleUsageView() {
    const visible = $("#chart-container").is(":visible");
    $("#chart-container").toggle(!visible);
    $("#analytics-table-wrapper").toggle(visible);
    if (!visible) renderUsageChart(analyticsData);
  }

  function toggleAllChartType() {
    allChartType = allChartType === 'bar' ? 'pie' : 'bar';
    renderAllMetricsChart(analyticsData);
  }

  function toggleAllView() {
    const visible = $("#all-metrics-chart-container").is(":visible");
    $("#all-metrics-chart-container").toggle(!visible);
    $("#all-metrics-wrapper").toggle(visible);
    if (!visible) renderAllMetricsChart(analyticsData);
  }

  // Shared form handler
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    const start = document.getElementById('start_date').value;
    const end = document.getElementById('end_date').value;
    fetchLibraryMetrics(start, end);
    fetchASLMetrics(start, end);
  });

  // Initial load on page open
  window.onload = () => {
    const today = new Date().toISOString().split('T')[0];
    const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    document.getElementById('start_date').value = weekAgo;
    document.getElementById('end_date').value = today;
    fetchLibraryMetrics(weekAgo, today);
    fetchASLMetrics(weekAgo, today);
  };