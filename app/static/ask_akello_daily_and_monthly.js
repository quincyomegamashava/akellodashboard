
    async function loadDailyChats() {
      const res = await fetch("/api/askakello-daily-chats");
      const data = await res.json();

      const tbody = document.querySelector("#askdailyTable tbody");
      tbody.innerHTML = "";

      const labels = [];
      const counts = [];

      data.daily_chats.forEach(row => {
        labels.push(row.chat_date);
        counts.push(row.learner_count);

        tbody.innerHTML += `
          <tr>
            <td>${row.chat_date}</td>
            <td>${row.learner_count}</td>
          </tr>
        `;
      });

      new Chart(document.getElementById("askdailyChart"), {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: "Daily Chats",
            data: counts,
            borderColor: "blue",
            fill: false
          }]
        }
      });
    }

    async function loadMonthlyChats() {
      const res = await fetch("/api/askakello-monthly-chats");
      const data = await res.json();

      const tbody = document.querySelector("#askmonthlyTable tbody");
      tbody.innerHTML = "";

      const labels = [];
      const counts = [];

      data.monthly_chats.forEach(row => {
        labels.push(row.month);
        counts.push(row.learner_count);

        tbody.innerHTML += `
          <tr>
            <td>${row.month}</td>
            <td>${row.learner_count}</td>
          </tr>
        `;
      });

      new Chart(document.getElementById("askmonthlyChart"), {
        type: "line",
        data: {
          labels: labels,
          datasets: [{
            label: "Monthly Chats",
            data: counts,
            borderColor: "green",
            fill: false
          }]
        }
      });
    }

    // Load both
    loadDailyChats();
    loadMonthlyChats();
