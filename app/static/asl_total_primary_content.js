
async function fetchData() {
    const res = await fetch('/api/asl_total_primary_content');
    const data = await res.json();

    if(data.error){
        alert("Error: " + data.error);
        return;
    }

    const tableBody = document.querySelector("#primarycontentTable tbody");
    tableBody.innerHTML = "";

    const provinces = [...new Set(data.breakdown.map(b => b.school_province))].sort();
    const maleCounts = [], femaleCounts = [], unknownCounts = [];

    provinces.forEach(prov => {
        const male = data.breakdown
            .filter(b => b.school_province === prov && b.gender === "Male")
            .reduce((a,b)=>a+b.count,0);
        const female = data.breakdown
            .filter(b => b.school_province === prov && b.gender === "Female")
            .reduce((a,b)=>a+b.count,0);
        const unknown = data.breakdown
            .filter(b => b.school_province === prov && b.gender === "Unknown")
            .reduce((a,b)=>a+b.count,0);
        const total = male + female + unknown;

        maleCounts.push(male);
        femaleCounts.push(female);
        unknownCounts.push(unknown);

        tableBody.innerHTML += `<tr>
            <td>${prov}</td>
            <td>${male}</td>
            <td>${female}</td>
            <td>${unknown}</td>
            <td>${total}</td>
        </tr>`;
    });

    // Remove any existing canvas to avoid duplicates
    const chartContainer = document.getElementById('prychartContainer');
    chartContainer.innerHTML = ""; // Clear previous chart
    const canvas = document.createElement('canvas');
    canvas.id = 'primarycontentChart';
    chartContainer.appendChild(canvas);

    new Chart(canvas.getContext('2d'), {
        type: 'bar',
        data: {
            labels: provinces,
            datasets: [
                { label: 'Male', data: maleCounts, backgroundColor: 'rgba(54, 162, 235, 0.7)' },
                { label: 'Female', data: femaleCounts, backgroundColor: 'rgba(255, 99, 132, 0.7)' },
                { label: 'Unknown', data: unknownCounts, backgroundColor: 'rgba(201, 203, 207, 0.7)' }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top' } },
            scales: { 
                x: { stacked: true },
                y: { stacked: true, beginAtZero: true }
            }
        }
    });
}

fetchData();

