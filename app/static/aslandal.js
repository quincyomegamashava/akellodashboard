
  let analyticsData = null;
  let currentChartType = 'bar';
  let chart;

  const ctx = document.getElementById('libusageChart').getContext('2d');

  function formatLabel(key) {
    return key.replace(/_/g, " ")
              .replace("asl", "ASL")
              .replace(/\b\w/g, c => c.toUpperCase());
  }

  function populateTable(data) {
    const tbody = $("#libanalytics-table tbody");
    tbody.empty();

    for (const key in data) {
      if (key === "asl_revenue") {
        data[key].forEach(entry => {
          const row = $("<tr>");
          row.append($("<td>").text("Revenue (" + entry.currency + ")"));
          row.append($("<td>").text(entry.value));
          tbody.append(row);
        });
      } else {
        const row = $("<tr>");
        row.append($("<td>").text(formatLabel(key)));
        row.append($("<td>").text(data[key]));
        tbody.append(row);
      }
    }
  }

  function renderChart(data) {
    const labels = [];
    const values = [];

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

    const config = {
      type: currentChartType,
      data: {
        labels: labels,
        datasets: [{
          label: 'Usage',
          data: values,
          backgroundColor: [
            '#4dc9f6','#f67019','#f53794','#537bc4','#acc236',
            '#166a8f','#00a950','#58595b','#8549ba','#ff6384'
          ],
          borderColor: '#fff',
          borderWidth: 1
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            display: currentChartType === 'pie'
          },
          title: {
            display: true,
            text: 'AL Usage Metrics'
          }
        }
      }
    };

    if (chart) chart.destroy();
    chart = new Chart(ctx, config);
  }

  function togglelibChartType() {
    currentChartType = currentChartType === 'bar' ? 'pie' : 'bar';
    renderChart(analyticsData);
  }

  function togglelibView() {
    const chartVisible = $("#libchart-container").is(":visible");

    if (chartVisible) {
      $("#libchart-container").hide();
      $("#libanalytics-table-wrapper").show();
    } else {
      $("#libanalytics-table-wrapper").hide();
      $("#libchart-container").show();
      renderChart(analyticsData); // render only when shown
    }
  }

  $(document).ready(function () {
    $.ajax({
      url: "/api/analytics-summary",
      method: "GET",
      dataType: "json",
      success: function (data) {
        analyticsData = data;
        $("#aslloader").hide();

        populateTable(data);
        $("#libanalytics-table-wrapper").show(); // show table by default

        // Chart is hidden initially, render only when shown
      },
      error: function (xhr, status, error) {
        $("#aslloader").text("Failed to load analytics data.");
        console.error("Error:", error);
      }
    });
  });