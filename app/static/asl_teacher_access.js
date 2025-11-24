async function loadTeacherAccess() {
      try {
        const res = await fetch("/api/asl_teacher_access");
        const data = await res.json();

        console.log("API response:", data); // Debugging

        if (data.error) {
          document.getElementById("date-range").textContent =
            "Error: " + data.error;
          return;
        }

        document.getElementById("date-range").textContent =
          `From ${data.start_date} to ${data.end_date} — Total Teachers: ${data.total_teachers}`;

        if (!data.breakdown || data.breakdown.length === 0) {
          document.querySelector("#teacherTable tbody").innerHTML =
            `<tr><td colspan="5">No data available</td></tr>`;
          return;
        }

        // --- Aggregate by province ---
        const provinceMap = {};
        data.breakdown.forEach(item => {
          const prov = item.school_province || "Unknown";
          const g = item.gender || "Unknown";
          if (!provinceMap[prov]) {
            provinceMap[prov] = { Male: 0, Female: 0, Unknown: 0 };
          }
          if (g.toLowerCase().startsWith("m")) provinceMap[prov].Male += item.count;
          else if (g.toLowerCase().startsWith("f")) provinceMap[prov].Female += item.count;
          else provinceMap[prov].Unknown += item.count;
        });

        // --- Populate table ---
        const tbody = document.querySelector("#teacherTable tbody");
        tbody.innerHTML = "";
        for (const [prov, counts] of Object.entries(provinceMap)) {
          const total = counts.Male + counts.Female + counts.Unknown;
          const row = `
            <tr>
              <td>${prov}</td>
              <td>${counts.Male}</td>
              <td>${counts.Female}</td>
              <td>${counts.Unknown}</td>
              <td>${total}</td>
            </tr>`;
          tbody.insertAdjacentHTML("beforeend", row);
        }

        // --- Bar chart ---
        const ctx = document.getElementById("teacherChart").getContext("2d");
        if (window.teacherChartInstance) {
          window.teacherChartInstance.destroy();
        }
        window.teacherChartInstance = new Chart(ctx, {
          type: "bar",
          data: {
            labels: Object.keys(provinceMap),
            datasets: [
              {
                label: "Male",
                data: Object.values(provinceMap).map(c => c.Male),
                backgroundColor: "rgba(54, 162, 235, 0.6)"
              },
              {
                label: "Female",
                data: Object.values(provinceMap).map(c => c.Female),
                backgroundColor: "rgba(255, 99, 132, 0.6)"
              },
              {
                label: "Unknown",
                data: Object.values(provinceMap).map(c => c.Unknown),
                backgroundColor: "rgba(201, 203, 207, 0.6)"
              }
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
      } catch (err) {
        console.error("Fetch error:", err);
        document.getElementById("date-range").textContent = "Error loading data.";
      }
    }

    loadTeacherAccess();