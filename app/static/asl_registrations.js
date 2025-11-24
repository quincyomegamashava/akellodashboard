async function loadRegistrations() {
  try {
    const response = await fetch("/asl_registrations");  // <-- endpoint
    const data = await response.json();

    document.getElementById("date-range").textContent = 
      `From ${data.start_date} to ${data.end_date}`;
    document.getElementById("total").textContent = data.total_registrations;

    const tbody = document.querySelector("#registrations-table tbody");
    tbody.innerHTML = "";

    // Organize data into province → gender counts
    const provinceData = {};
    const genders = ["Male", "Female", "Unknown"];

    data.breakdown.forEach(row => {
      if (!provinceData[row.school_province]) {
        provinceData[row.school_province] = { Male: 0, Female: 0, Unknown: 0, Total: 0 };
      }
      provinceData[row.school_province][row.gender] += row.count;
      provinceData[row.school_province].Total += row.count;
    });

    // Fill table
    Object.keys(provinceData).forEach(prov => {
      const row = provinceData[prov];
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="w3-hover-shadow"><a href="{{ url_for('provincestats', provincename=${prov}) }}"
              style="text-decoration: none;">${prov}</a></td>
        <td>${row.Male}</td>
        <td>${row.Female}</td>
        <td>${row.Unknown}</td>
        <td>${row.Total}</td>
      `;
      tbody.appendChild(tr);
    });

    // Chart.js Bar Chart (stacked by gender)
    const ctxBar = document.getElementById("regbarChart").getContext("2d");
    const provinces = Object.keys(provinceData);

    const maleCounts = provinces.map(p => provinceData[p].Male);
    const femaleCounts = provinces.map(p => provinceData[p].Female);
    const unknownCounts = provinces.map(p => provinceData[p].Unknown);

    new Chart(ctxBar, {
      type: "bar",
      data: {
        labels: provinces,
        datasets: [
          { label: "Male", data: maleCounts, backgroundColor: "blue" },
          { label: "Female", data: femaleCounts, backgroundColor: "pink" },
          { label: "Unknown", data: unknownCounts, backgroundColor: "gray" }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top" } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true }
        }
      }
    });

    // Chart.js Pie Chart (gender totals)
    const ctxPie = document.getElementById("regpieChart").getContext("2d");
    const genderTotals = data.gender_totals;

    new Chart(ctxPie, {
      type: "pie",
      data: {
        labels: Object.keys(genderTotals),
        datasets: [{
          data: Object.values(genderTotals),
          backgroundColor: ["blue", "pink", "gray"]
        }]
      }
    });

  } catch (err) {
    console.error("Error loading registrations:", err);
  }
}

// Run on page load
loadRegistrations();