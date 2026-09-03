$(document).ready(function () {
    let chartData = null; 
    let currentChartType = 'bar';

    // --- NEW: Define the column headers to be displayed ---
    // You can add, remove, or reorder these columns as needed.
    // Ensure the key names match those in your data.
    const displayedHeaders = [
        { key: 'province', label: 'Province' },
        { key: 'number_of_institutions', label: 'School Count' },
        { key: 'total_users', label: 'Student Count' }
    ];

    function renderChart(type) {
        if (!chartData) return;
        const chartEl = document.getElementById('provlibraryChart');
        if (!chartEl || typeof Plotly === 'undefined') return;

        // The logic to build labels and values remains the same
        const firstRow = chartData[0] || {};
        const provinceKey = Object.keys(firstRow).find(k =>
            k.toLowerCase().includes("province") || k.toLowerCase() === "name"
        ) || "Province";

        const labels = chartData.map(row => row[provinceKey] || "Unknown");

        const values = chartData.map(row => {
            if (row.Usage || row.usage || row.count) {
                return row.Usage || row.usage || row.count || 0;
            }
            return Object.keys(row).reduce((sum, key) => {
                if (key !== provinceKey && typeof row[key] === "number") {
                    return sum + row[key];
                }
                return sum;
            }, 0);
        });

        let trace;
        if (type === 'bar') {
            trace = {
                x: labels,
                y: values,
                type: 'bar',
                marker: { color: '#3498db' }
            };
        } else if (type === 'pie') {
            trace = {
                labels: labels,
                values: values,
                type: 'pie',
                textinfo: 'label+percent',
                insidetextorientation: 'radial'
            };
        }

        const layout = {
            title: type === 'bar' ? 'Library Province Usage - Bar Chart' : 'Library Province Usage - Pie Chart',
            xaxis: type === 'bar' ? { title: 'Province' } : undefined,
            yaxis: type === 'bar' ? { title: 'Usage Count' } : undefined,
            margin: { t: 50, b: 50, l: 50, r: 50 }
        };

        Plotly.newPlot('provlibraryChart', [trace], layout, { responsive: true });
    }

    $.ajax({
        url: "/api/library-institutions",
        method: "GET",
        dataType: "json",
        success: function (data) {
            const thead = $("#thead");
            const tbody = $("#libtbody");

            tbody.empty();
            thead.html(`
                <tr>
                    <th class="w3-center w3-teal w3-opacity" colspan="${displayedHeaders.length}">Library Province Usage</th>
                </tr>
            `);

            if (!data || data.length === 0) {
                thead.append('<tr><th colspan="${displayedHeaders.length}">No Data</th></tr>');
                return;
            }

            chartData = data;

            // --- UPDATED: Generate column headers from the new array ---
            const headerRowHTML = displayedHeaders.map(h => `<th>${h.label}</th>`).join('');
            thead.append('<tr>' + headerRowHTML + '</tr>');

            // --- UPDATED: Populate rows based on the defined keys ---
            data.forEach(row => {
                const rowHTML = displayedHeaders.map(h => `<td>${row[h.key] || ''}</td>`).join('');
                tbody.append('<tr>' + rowHTML + '</tr>');
            });

            renderChart(currentChartType);
        },
        error: function (xhr, status, error) {
            $("#thead").html(`
                <tr><th class="w3-center w3-teal w3-opacity" colspan="3">Library Province Usage</th></tr>
                <tr><th colspan="3">Error loading data</th></tr>
            `);
            $("#libtbody").html(`<tr><td colspan="3">${error}</td></tr>`);
            console.error("Error fetching library-institutions data:", error);
        }
    });

    // Toggle buttons
    $("#showLibBarChart").on("click", function () {
        currentChartType = 'bar';
        renderChart('bar');
    });

    $("#showLibPieChart").on("click", function () {
        currentChartType = 'pie';
        renderChart('pie');
    });
});