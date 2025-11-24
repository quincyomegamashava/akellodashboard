async function loadData() {
            try {
                const res = await fetch('/api/asl_total_sec_content');
                const data = await res.json();

                if (data.error) {
                    console.error("API Error:", data.error);
                    alert("Error fetching data: " + data.error);
                    return;
                }

                const breakdown = data.breakdown;
                const provinces = {};
                
                // Aggregate by province and gender
                breakdown.forEach(item => {
                    const prov = item.school_province;
                    if (!provinces[prov]) provinces[prov] = { Male: 0, Female: 0, Unknown: 0 };
                    provinces[prov][item.gender] = item.count;
                });

                // Build table
                const tbody = document.querySelector('#secContentdataTable tbody');
                tbody.innerHTML = '';
                for (const [prov, genders] of Object.entries(provinces)) {
                    const total = genders.Male + genders.Female + genders.Unknown;
                    if (total === 0) continue; // skip zero totals
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${prov}</td>
                        <td>${genders.Male}</td>
                        <td>${genders.Female}</td>
                        <td>${genders.Unknown}</td>
                        <td>${total}</td>
                    `;
                    tbody.appendChild(tr);
                }

                // Build chart
                const labels = Object.keys(provinces).filter(prov => {
                    const g = provinces[prov];
                    return g.Male + g.Female + g.Unknown > 0;
                });
                const maleData = labels.map(p => provinces[p].Male);
                const femaleData = labels.map(p => provinces[p].Female);
                const unknownData = labels.map(p => provinces[p].Unknown);

                const ctx = document.getElementById('secContentprovinceChart').getContext('2d');
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [
                            { label: 'Male', data: maleData, backgroundColor: 'rgba(54, 162, 235, 0.7)' },
                            { label: 'Female', data: femaleData, backgroundColor: 'rgba(255, 99, 132, 0.7)' },
                            { label: 'Unknown', data: unknownData, backgroundColor: 'rgba(201, 203, 207, 0.7)' }
                        ]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            title: { display: true, text: 'ASL Secondary Content by Province & Gender' },
                            tooltip: { mode: 'index', intersect: false }
                        },
                        scales: {
                            x: { stacked: true },
                            y: { stacked: true, beginAtZero: true }
                        }
                    }
                });

            } catch (err) {
                console.error(err);
                alert("Failed to load data: " + err);
            }
        }

        loadData();