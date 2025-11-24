
        $(document).ready(function () {
            $.ajax({
                url: "/api/province-usage",
                method: "GET",
                dataType: "json",
                success: function (data) {
                    const tbody = $("#usage-table tbody");
                    tbody.empty();

                    data.forEach(row => {
                        const tr = $("<tr>");
                        tr.append($("<td>").text(row.province));
                          tr.append($("<td>").text('view'));
                        tr.append($("<td>").text(row.stu_usage));
                        tbody.append(tr);
                    });

                    $("#loader").hide();
                    $("#usage-table").show();
                },
                error: function (xhr, status, error) {
                    $("#loader").text("Failed to load data.");
                    console.error("Error fetching data:", error);
                }
            });
        });
 