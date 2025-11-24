async function loadSubscribersData() {
  try {
    const res = await fetch("/api/asl_unique_subscribers");
    const data = await res.json();

    document.getElementById("totalSubscribers").textContent = data.total_subscribers;
    document.getElementById("dateRange").textContent = `${data.start_date} → ${data.end_date}`;

    // --- Table ---
    const tbody = document.querySelector("#subscribersTable tbody");
    tbody.innerHTML = "";

    // Organize data by province
    const provinces = {};
    data.breakdown.forEach(row => {
      const prov = row.school_province;
      if (!provinces[prov]) provinces[prov] = { Male: 0, Female: 0, Unknown: 0, Total: 0 };
      provinces[prov][row.gender] += row.count;
      provinces[prov].Total += row.count;
    });

    Object.entries(provinces).forEach(([prov, counts]) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${prov}</td>
        <td>${counts.Male || 0}</td>
        <td>${counts.Female || 0}</td>
        <td>${counts.Unknown || 0}</td>
        <td><strong>${counts.Total}</strong></td>
      `;
      tbody.appendChild(tr);
    });

    // --- Charts ---
    const provinceNames = Object.keys(provinces);
    const maleCounts = provinceNames.map(p => provinces[p].Male);
    const femaleCounts = provinceNames.map(p => provinces[p].Female);
    const unknownCounts = provinceNames.map(p => provinces[p].Unknown);

    // Province Bar Chart
    new Chart(document.getElementById("provinceBarChart"), {
      type: "bar",
      data: {
        labels: provinceNames,
        datasets: [
          { label: "Male", data: maleCounts, backgroundColor: "#36A2EB" },
          { label: "Female", data: femaleCounts, backgroundColor: "#FF6384" },
          { label: "Unknown", data: unknownCounts, backgroundColor: "#FFCE56" }
        ]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "top" } },
        scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
      }
    });

    // Gender Pie Chart
    new Chart(document.getElementById("genderPieChart"), {
      type: "pie",
      data: {
        labels: ["Male", "Female", "Unknown"],
        datasets: [{
          data: [
            data.gender_totals.Male,
            data.gender_totals.Female,
            data.gender_totals.Unknown
          ],
          backgroundColor: ["#36A2EB", "#FF6384", "#FFCE56"]
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { position: "bottom" } }
      }
    });

  } catch (err) {
    console.error("Error loading subscribers data:", err);
    alert("Failed to load data. Check console for details.");
  }
}

loadSubscribersData();