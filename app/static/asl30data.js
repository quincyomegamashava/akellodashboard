async function loadData() {
      const response = await fetch("/asl_active30");
      const data = await response.json();

      if (data.error) {
        document.body.innerHTML += `<p style="color:red;">Error: ${data.error}</p>`;
        return;
      }

      const genders = ["Male", "Female", "Unknown"];
      const provinces = [...new Set(data.breakdown.map(d => d.school_province))];

      // Build table data
      const tbody = document.querySelector("#asl30data-table tbody");
      tbody.innerHTML = "";
      provinces.forEach(prov => {
        let row = { Male: 0, Female: 0, Unknown: 0, Total: 0 };
        data.breakdown.forEach(b => {
          if (b.school_province === prov) {
            row[b.gender] = b.active_count;
            row.Total += b.active_count;
          }
        });

        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="w3-hover-shadow"><a href="{{ url_for('provincestats', provincename=${prov}) }}"
              style="text-decoration: none;">${prov}</a></td>
          <td>${row.Male}</td>
          <td>${row.Female}</td>
          <td>${row.Unknown}</td>
          <td><b>${row.Total}</b></td>
        `;
        tbody.appendChild(tr);
      });

      // Prepare chart datasets
      const datasets = genders.map((g, i) => ({
        label: g,
        data: provinces.map(p => {
          const item = data.breakdown.find(b => b.school_province === p && b.gender === g);
          return item ? item.active_count : 0;
        }),
        backgroundColor: i === 0 ? "rgba(54, 162, 235, 0.7)"
                        : i === 1 ? "rgba(255, 99, 132, 0.7)"
                        : "rgba(201, 203, 207, 0.7)"
      }));

      // Render chart
      const ctx = document.getElementById("asl30barChart").getContext("2d");
      new Chart(ctx, {
        type: "bar",
        data: {
          labels: provinces,
          datasets: datasets
        },
        options: {
          responsive: true,
          scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true }
          }
        }
      });
    }

    loadData();