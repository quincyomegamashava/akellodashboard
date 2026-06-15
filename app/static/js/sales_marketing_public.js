(function () {
  const form = document.getElementById("sm-public-form");
  const alertEl = document.getElementById("sm-alert");
  const thankYou = document.getElementById("sm-thank-you");
  const eventDate = document.getElementById("sm-event-date");
  const eventSelect = document.getElementById("sm-event-id");
  const province = document.getElementById("sm-province");
  const schoolList = document.getElementById("sm-school-list");
  const prefillId = window.SM_PREFILL_EVENT_ID;
  const prefillEvent = window.SM_PREFILL_EVENT;

  function showAlert(msg, type) {
    if (!alertEl) return;
    alertEl.className = "alert alert-" + (type || "info");
    alertEl.textContent = msg;
    alertEl.classList.remove("d-none");
  }

  function showThankYou() {
    if (form) form.classList.add("d-none");
    if (thankYou) thankYou.classList.remove("d-none");
    if (alertEl) alertEl.classList.add("d-none");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function loadEvents() {
    if (!eventDate || !eventSelect) return;
    const d = eventDate.value || new Date().toISOString().slice(0, 10);
    try {
      const res = await fetch("/api/public/marketing-events?date=" + encodeURIComponent(d));
      const events = await res.json();
      const cur = eventSelect.value;
      eventSelect.innerHTML = '<option value="">Not at an event / General enquiry</option>';
      const seen = {};
      if (prefillEvent && prefillId) {
        const opt = document.createElement("option");
        opt.value = String(prefillId);
        opt.textContent = prefillEvent.name + (prefillEvent.location ? " — " + prefillEvent.location : "");
        eventSelect.appendChild(opt);
        seen[prefillId] = true;
        eventSelect.value = String(prefillId);
      }
      events.forEach(function (ev) {
        if (seen[ev.id]) return;
        const opt = document.createElement("option");
        opt.value = String(ev.id);
        opt.textContent = ev.name + (ev.location ? " — " + ev.location : "");
        eventSelect.appendChild(opt);
      });
      if (cur) eventSelect.value = cur;
    } catch (e) {
      console.error(e);
    }
  }

  if (eventDate) {
    eventDate.addEventListener("change", loadEvents);
    loadEvents();
  }

  if (province) {
    province.addEventListener("change", async function () {
      const p = province.value;
      if (!p || !schoolList) return;
      try {
        const res = await fetch("/api/schools/" + encodeURIComponent(p));
        const schools = await res.json();
        schoolList.innerHTML = "";
        (schools || []).slice(0, 200).forEach(function (s) {
          const opt = document.createElement("option");
          opt.value = typeof s === "string" ? s : (s.name || s.school_name || "");
          schoolList.appendChild(opt);
        });
      } catch (e) { /* optional */ }
    });
  }

  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const btn = document.getElementById("sm-submit-btn");
      if (btn) btn.disabled = true;
      const fd = new FormData(form);
      const payload = {
        full_name: fd.get("full_name"),
        occupation: fd.get("occupation"),
        email: fd.get("email"),
        mobile: fd.get("mobile"),
        province: fd.get("province"),
        school_name: fd.get("school_name"),
        organization: fd.get("organization"),
        role_category: fd.get("role_category"),
        event_id: fd.get("event_id") || null,
        interest_option_id: fd.get("interest_option_id"),
        preferred_contact: fd.get("preferred_contact"),
        heard_about: fd.get("heard_about"),
        comments: fd.get("comments"),
        consent_marketing: fd.get("consent_marketing") === "1",
        website: fd.get("website"),
      };
      try {
        const res = await fetch("/api/public/stakeholder-leads", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(function () { return {}; });
        if (!res.ok) throw new Error(data.error || "Submission failed");
        if (data.duplicate_warning) {
          showAlert("Submitted — we already have a recent entry from this email.", "warning");
          setTimeout(showThankYou, 2500);
        } else {
          showThankYou();
        }
      } catch (err) {
        showAlert(err.message || "Could not submit. Please try again.", "danger");
        if (btn) btn.disabled = false;
      }
    });
  }
})();
