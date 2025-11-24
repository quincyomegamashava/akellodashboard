async function loadData() {
      const res = await fetch("/api/asl_total_zimsec_access");
      const data = await res.json();
      console.log(data);

      document.getElementById("zimsecsummary").innerHTML =
        `<b>Total Access:</b> ${data.total_access} 
         (From ${data.start_date} to ${data.end_date})`;

      // --- Table ---
      let table = `<tr>
        <th>Province</th><th>Male</th><th>Female</th><th>Unknown</th><th>Total</th>
      </tr>`;
      const provMap = {};
      data.breakdown.forEach(r => {
        if (!provMap[r.school_province]) provMap[r.school_province] = {Male:0,Female:0,Unknown:0};
        provMap[r.school_province][r.gender] = r.count;
      });
      data.province_totals.forEach(p => {
        const row = provMap[p.school_province];
        table += `<tr>
          <td>${p.school_province}</td>
          <td>${row.Male||0}</td>
          <td>${row.Female||0}</td>
          <td>${row.Unknown||0}</td>
          <td>${p.total}</td>
        </tr>`;
      });
      document.getElementById("zimsecdata-table").innerHTML = table;

      // --- Charts ---
      const provinces = data.province_totals.map(p => p.school_province);
      const totals = data.province_totals.map(p => p.total);
      const male = provinces.map(prov => provMap[prov]?.Male || 0);
      const female = provinces.map(prov => provMap[prov]?.Female || 0);
      const unknown = provinces.map(prov => provMap[prov]?.Unknown || 0);

      new Chart(document.getElementById("zimsecbarChart"), {
        type: 'bar',
        data: {
          labels: provinces,
          datasets: [{label:"Total Access", data: totals, backgroundColor:"steelblue"}]
        },
        options: { responsive:true, plugins:{legend:{display:false}} }
      });

      new Chart(document.getElementById("zimsecstackedChart"), {
        type: 'bar',
        data: {
          labels: provinces,
          datasets: [
            {label:"Male", data: male, backgroundColor:"blue"},
            {label:"Female", data: female, backgroundColor:"pink"},
            {label:"Unknown", data: unknown, backgroundColor:"gray"}
          ]
        },
        options: {
          responsive:true,
          plugins:{title:{display:true,text:"Gender Distribution by Province"}},
          scales:{ x:{stacked:true}, y:{stacked:true} }
        }
      });
    }
    loadData();