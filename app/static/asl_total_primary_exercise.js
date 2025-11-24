fetch('/api/asl_total_primary_exercise')
.then(res => res.json())
.then(data => {
    const tableBody = document.querySelector('#primaryexercise-table tbody');
    const provinces = [...new Set(data.breakdown.map(b => b.school_province))];

    const chartData = {
        labels: provinces,
        datasets: [
            { label: 'Male', data: [], backgroundColor: 'blue' },
            { label: 'Female', data: [], backgroundColor: 'pink' },
            { label: 'Unknown', data: [], backgroundColor: 'gray' }
        ]
    };

    provinces.forEach(prov => {
        let male = 0, female = 0, unknown = 0;
        data.breakdown.forEach(b => {
            if(b.school_province === prov){
                if(b.gender === 'Male') male = b.count;
                else if(b.gender === 'Female') female = b.count;
                else unknown = b.count;
            }
        });
        const total = male + female + unknown;
        tableBody.innerHTML += `<tr>
            <td>${prov}</td>
            <td>${male}</td>
            <td>${female}</td>
            <td>${unknown}</td>
            <td>${total}</td>
        </tr>`;

        chartData.datasets[0].data.push(male);
        chartData.datasets[1].data.push(female);
        chartData.datasets[2].data.push(unknown);
    });

    new Chart(document.getElementById('primaryexerciseChart'), {
        type: 'bar',
        data: chartData,
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'top' },
                title: { display: true, text: 'Primary Exercises by Province & Gender' }
            },
            scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } }
        }
    });
});