let chart;
let chartType = 'bar';

async function fetchData() {
  try {
    const response = await fetch('/api/chat-log-by-province');
    const data = await response.json();
    if (data.error) throw new Error(data.error);

    createTable(data);
    renderChart(data, chartType);
  } catch (error) {
    console.error('Fetch error:', error);
    document.getElementById('table-container').innerHTML = '<p>Error loading data</p>';
  }
}

function createTable(data) {
  const container = document.getElementById('table-container');
  let html = `<table class="table table-striped w3-small table-bordered"><thead>
    <tr>
      <th class="w3-center w3-blue w3-opacity" colspan="2">Ask Akello Province Usage</th>
    </tr>
    <tr><th>Province</th><th>Total Students</th></tr></thead><tbody>`;
  data.forEach(row => {
    html += `<tr><td>${row.province}</td><td>${row.total_students}</td></tr>`;
  });
  html += `</tbody></table>`;
  container.innerHTML = html;
}

function renderChart(data, type) {
  const labels = data.map(d => d.province);
  const values = data.map(d => d.total_students);

  const canvas = document.getElementById('provinceChart');

  // Apply class based on chart type
  if (type === 'pie') {
    canvas.classList.add('pie-style');
  } else {
    canvas.classList.remove('pie-style');
  }

  const config = {
    type: type,
    data: {
      labels: labels,
      datasets: [{
        label: 'Total Students',
        data: values,
        backgroundColor: [
          '#4e73df', '#1cc88a', '#36b9cc', '#f6c23e', '#e74a3b',
          '#858796', '#fd7e14', '#20c997', '#6f42c1', '#ff6384'
        ],
        borderColor: '#ddd',
        borderWidth: 1
      }]
    },
    options: {
      responsive: type !== 'pie', // only bar is responsive
      maintainAspectRatio: type !== 'pie',
      plugins: {
        legend: {
          display: type === 'pie'
        }
      },
      scales: type === 'bar' ? {
        y: {
          beginAtZero: true
        }
      } : {}
    }
  };

  if (chart) chart.destroy();
  const ctx = canvas.getContext('2d');
  chart = new Chart(ctx, config);
}

function toggleChart() {
  chartType = chartType === 'bar' ? 'pie' : 'bar';
  fetchData();
}

// Load data and chart on DOM content load
document.addEventListener('DOMContentLoaded', fetchData);
