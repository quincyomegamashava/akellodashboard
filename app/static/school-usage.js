
$(document).ready(function () {
    $.ajax({
        url: "/api/school-usage",
        method: "GET",
        dataType: "json",
        success: function (data) {
            const thead = $("#schoolUsageHead");
            const tbody = $("#schoolUsageBody");

            tbody.empty();
            thead.html(`
                <tr>
                    <th class="w3-center w3-teal w3-opacity" colspan="5">School Usage Summary</th>
                </tr>
            `);

            if (!data || data.length === 0) {
                thead.append('<tr><th colspan="5">No Data Found</th></tr>');
                return;
            }

            // Dynamic headers
            const headers = Object.keys(data[0]);
            thead.append('<tr>' + headers.map(h => `<th>${h.replace(/_/g, ' ')}</th>`).join('') + '</tr>');

            // Populate table body
            data.forEach(row => {
                const rowHTML = '<tr>' + headers.map(h => `<td>${row[h]}</td>`).join('') + '</tr>';
                tbody.append(rowHTML);
            });
        },
        error: function (xhr, status, error) {
            $("#schoolUsageHead").html('<tr><th colspan="5">Error Loading Data</th></tr>');
            $("#schoolUsageBody").html(`<tr><td colspan="5">${error}</td></tr>`);
            console.error("Error fetching school usage data:", error);
        }
    });
});

