
document.addEventListener("DOMContentLoaded", function () {
    const select = document.getElementById("school-select");
    const province = "{{ user.province }}";  // passed from Flask context

    fetch(`/api/schools/${province}`)
        .then(response => response.json())
        .then(data => {
            if (Array.isArray(data)) {
                data.forEach(school => {
                    const option = document.createElement("option");
                    option.value = school.id;
                    option.textContent = `${school.name} (ID: ${school.id})`;
                    select.appendChild(option);
                });
            } else {
                console.error("Error loading schools:", data.error);
            }
        })
        .catch(err => {
            console.error("Fetch failed:", err);
        });
});

