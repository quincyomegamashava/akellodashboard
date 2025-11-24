
document.addEventListener("DOMContentLoaded", function () {
  const provinceInput = document.getElementById("user-province");
  const preselectedInput = document.getElementById("preselected-schools");
  const container = document.getElementById("school-checkboxes");

  if (!provinceInput || !container) {
    console.warn("Missing province input or school container.");
    return;
  }

  const province = provinceInput.value;
  const preselected = JSON.parse(preselectedInput?.value || "[]");

  fetch(`/api/get-schools-by-province?province=${encodeURIComponent(province)}`)
    .then(response => response.json())
    .then(data => {
      data.forEach(school => {
        const div = document.createElement("div");
        div.classList.add("form-check");

        const input = document.createElement("input");
        input.classList.add("form-check-input");
        input.type = "checkbox";
        input.name = "schools"; // Must match form.schools
        input.value = school.school_id;
        input.id = `school${school.school_id}`;

        if (preselected.includes(String(school.school_id))) {
          input.checked = true;
        }

        const label = document.createElement("label");
        label.classList.add("form-check-label");
        label.setAttribute("for", input.id);
        label.innerText = school.school_name;

        div.appendChild(input);
        div.appendChild(label);
        container.appendChild(div);
      });
    })
    .catch(error => {
      console.error("Error loading schools:", error);
    });
});

