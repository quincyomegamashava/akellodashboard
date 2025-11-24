async function fetchTeacherActivities() {
      try {
        const response = await fetch("/api/asl_teacher_set_activities");
        const data = await response.json();

        // Display date range and total
        document.getElementById("teacher_setdateRange").textContent = 
          `${data.start_date} → ${data.end_date}`;
        document.getElementById("teacher_settotal").textContent = data.total_teacher_set_activities;

        // Organize data by province
        const provinceData = {};
        data.breakdown.forEach(item => {
          const prov = item.school_province;
          if (!provinceData[prov]) {
            provinceData[prov] = { Male: 0, Female: 0, Unknown: 0, Total: 0 };
          }
          provinceData[prov][item.gender] += item.count;
          provinceData[prov].Total += item.count;
        });

        // Fill the table
        const tbody = document.querySelector("#teacher_setdataTable tbody");
        tbody.innerHTML = "";
        Object.entries(provinceData).forEach(([prov, counts]) => {
          const row = `
            <tr>
              <td>${prov}</td>
              <td>${counts.Male}</td>
              <td>${counts.Female}</td>
              <td>${counts.Unknown}</td>
              <td>${counts.Total}</td>
            </tr>
          `;
          tbody.innerHTML += row;
        });

        // Prepare data for bar chart
        const provinces = Object.keys(provinceData);
        const maleCounts = provinces.map(p => provinceData[p].Male);
        const femaleCounts = provinces.map(p => provinceData[p].Female);
        const unknownCounts = provinces.map(p => provinceData[p].Unknown);

        // Render chart
        const ctx = document.getElementById("teacher_setchartCanvas").getContext("2d");
        new Chart(ctx, {
          type: "bar",
          data: {
            labels: provinces,
            datasets: [
              { label: "Male", data: maleCounts, backgroundColor: "rgba(54, 162, 235, 0.7)" },
              { label: "Female", data: femaleCounts, backgroundColor: "rgba(255, 99, 132, 0.7)" },
              { label: "Unknown", data: unknownCounts, backgroundColor: "rgba(201, 203, 207, 0.7)" }
            ]
          },
          options: {
            responsive: true,
            scales: {
              x: { stacked: true },
              y: { stacked: true, beginAtZero: true }
            }
          }
        });

      } catch (err) {
        console.error("Error loading data:", err);
      }
    }

    fetchTeacherActivities();