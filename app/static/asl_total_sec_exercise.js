async function loadExercises() {
    const resp = await fetch("/api/asl_total_sec_exercise");
    const data = await resp.json();

    const tbody = document.querySelector("#exercise-table tbody");
    tbody.innerHTML = "";

    const provinces = data.province_totals.map(p => p.school_province);
    const maleData = [];
    const femaleData = [];
    const unknownData = [];

    provinces.forEach(prov => {
        // Find counts per gender for this province
        const males = data.breakdown.find(b => b.school_province === prov && b.gender === "Male")?.count || 0;
        const females = data.breakdown.find(b => b.school_province === prov && b.gender === "Female")?.count || 0;
        const unknowns = data.breakdown.find(b => b.school_province === prov && b.gender === "Unknown")?.count || 0;
        const total = males + females + unknowns;

        maleData.push(males);
        femaleData.push(females);
        unknownData.push(unknowns);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${prov}</td>
            <td>${males}</td>
            <td>${females}</td>
            <td>${unknowns}</td>
            <td>${total}</td>
        `;
        tbody.appendChild(tr);
    });

    // Chart.js stacked bar chart
    const ctx = document.getElementById('exerciseChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: provinces,
            datasets: [
                { label: 'Male', data: maleData, backgroundColor: 'rgba(54, 162, 235, 0.7)' },
                { label: 'Female', data: femaleData, backgroundColor: 'rgba(255, 99, 132, 0.7)' },
                { label: 'Unknown', data: unknownData, backgroundColor: 'rgba(201, 203, 207, 0.7)' }
            ]
        },
        options: { 
            responsive: true,
            plugins: { title: { display: true, text: 'Exercises by Province and Gender' } },
            scales: { x: { stacked: true }, y: { stacked: true } }
        }
    });
}

loadExercises();