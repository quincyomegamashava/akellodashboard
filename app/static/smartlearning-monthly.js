
          async function loadMonthlyLogins() {
            try {
              const response = await fetch('/api/smartlearning-monthly-logins');
              const data = await response.json();

              const tableBody = document.querySelector('#aslloginsTable tbody');
              tableBody.innerHTML = ''; // clear old rows

              const months = [];
              const counts = [];

              data.monthly_logins.forEach(entry => {
                // Add to table
                const row = `
            <tr>
              <td>${entry.month}</td>
              <td>${entry.year}</td>
              <td>${entry.student_count}</td>
            </tr>
          `;
                tableBody.insertAdjacentHTML('beforeend', row);

                // Add to chart data
                months.push(entry.month);
                counts.push(entry.student_count);
              });

              // Render Chart.js line chart
              const ctx = document.getElementById('aslloginsChart').getContext('2d');
              new Chart(ctx, {
                type: 'line',
                data: {
                  labels: months,
                  datasets: [{
                    label: 'Monthly Logins',
                    data: counts,
                    borderColor: 'blue',
                    backgroundColor: 'rgba(0, 123, 255, 0.2)',
                    fill: true,
                    tension: 0.3
                  }]
                },
                options: {
                  responsive: true,
                  plugins: {
                    legend: { display: true },
                    tooltip: { enabled: true }
                  },
                  scales: {
                    y: { beginAtZero: true }
                  }
                }
              });

            } catch (error) {
              console.error('Error loading data:', error);
            }
          }

          // Load data on page load
          loadMonthlyLogins();
