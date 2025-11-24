async function loadData() {
  try {
    const res = await fetch("/api/asl_unique_users");
    const data = await res.json();

    // Debug raw JSON
    document.getElementById("raw").textContent = JSON.stringify(data, null, 2);

    if (!data.breakdown) {
      return; // API error
    }

    // --- Group breakdown by province ---
    const grouped = {};
    data.breakdown.forEach(row => {
      const prov = row.school_province;
      if (!grouped[prov]) grouped[prov] = {Male:0, Female:0, Unknown:0};
      grouped[prov][row.gender] = row.count;
    });

    // --- Fill table ---
    const tbody = document.querySelector("#uniqueusersTable tbody");
    tbody.innerHTML = "";
    Object.entries(grouped).forEach(([prov, g]) => {
      const total = (g.Male||0) + (g.Female||0) + (g.Unknown||0);
      if (total > 0) {
        tbody.innerHTML += `<tr>
          <td>${prov}</td>
          <td>${g.Male||0}</td>
          <td>${g.Female||0}</td>
          <td>${g.Unknown||0}</td>
          <td><b>${total}</b></td>
        </tr>`;
      }
    });

    // --- Charts ---
    const provinces = Object.keys(grouped);
    const maleData = provinces.map(p => grouped[p].Male || 0);
    const femaleData = provinces.map(p => grouped[p].Female || 0);
    const unknownData = provinces.map(p => grouped[p].Unknown || 0);

    new Chart(document.getElementById("uniquebarChart"), {
      type: "bar",
      data: {
        labels: provinces,
        datasets: [
          { label: "Male", data: maleData, backgroundColor: "blue" },
          { label: "Female", data: femaleData, backgroundColor: "pink" },
          { label: "Unknown", data: unknownData, backgroundColor: "gray" }
        ]
      },
      options: { responsive: true, scales: { x: { stacked: true }, y: { stacked: true } } }
    });

    new Chart(document.getElementById("uniquepieChart"), {
      type: "pie",
      data: {
        labels: ["Male", "Female", "Unknown"],
        datasets: [{
          data: [
            data.gender_totals?.Male || 0,
            data.gender_totals?.Female || 0,
            data.gender_totals?.Unknown || 0
          ],
          backgroundColor: ["blue", "pink", "gray"]
        }]
      }
    });

  } catch (e) {
    document.getElementById("raw").textContent = "Error loading API: " + e;
  }
}

loadData();