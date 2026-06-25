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

  const stepPanels = form ? Array.from(form.querySelectorAll(".sm-step-panel")) : [];
  const wizardSteps = document.querySelectorAll(".sm-wizard-step");
  const stepNumEl = document.getElementById("sm-step-num");
  const stepLabelEl = document.getElementById("sm-step-label");
  const barFill = document.getElementById("sm-wizard-bar-fill");
  const backBtn = document.getElementById("sm-back-btn");
  const nextBtn = document.getElementById("sm-next-btn");
  const submitBtn = document.getElementById("sm-submit-btn");

  const STEP_LABELS = ["Contact details", "Your context", "Your interest"];
  const TOTAL_STEPS = 3;
  let currentStep = 1;

  function showAlert(msg, type) {
    if (!alertEl) return;
    alertEl.className = "alert alert-" + (type || "info");
    alertEl.textContent = msg;
    alertEl.classList.remove("d-none");
    alertEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function hideAlert() {
    if (alertEl) alertEl.classList.add("d-none");
  }

  function showThankYou() {
    if (form) form.classList.add("d-none");
    if (thankYou) thankYou.classList.remove("d-none");
    if (alertEl) alertEl.classList.add("d-none");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function getFieldsForStep(step) {
    const panel = form.querySelector('.sm-step-panel[data-sm-step="' + step + '"]');
    if (!panel) return [];
    return Array.from(panel.querySelectorAll(".sm-field[required], .sm-field[aria-required='true']"));
  }

  function validateStep(step) {
    const fields = getFieldsForStep(step);
    let valid = true;
    let firstInvalid = null;

    fields.forEach(function (field) {
      field.classList.remove("is-invalid");
      if (field.type === "checkbox") {
        if (!field.checked) {
          field.classList.add("is-invalid");
          valid = false;
          if (!firstInvalid) firstInvalid = field;
        }
      } else if (!field.checkValidity()) {
        field.classList.add("is-invalid");
        valid = false;
        if (!firstInvalid) firstInvalid = field;
      }
    });

    if (!valid && firstInvalid) {
      firstInvalid.focus({ preventScroll: true });
      firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
      showAlert("Please complete the required fields before continuing.", "warning");
    } else {
      hideAlert();
    }

    return valid;
  }

  function updateProgressUI() {
    stepPanels.forEach(function (panel) {
      const step = parseInt(panel.getAttribute("data-sm-step"), 10);
      panel.classList.toggle("d-none", step !== currentStep);
    });

    wizardSteps.forEach(function (el) {
      const step = parseInt(el.getAttribute("data-step"), 10);
      el.classList.remove("is-active", "is-complete");
      if (step < currentStep) el.classList.add("is-complete");
      if (step === currentStep) el.classList.add("is-active");
    });

    if (stepNumEl) stepNumEl.textContent = String(currentStep);
    if (stepLabelEl) stepLabelEl.textContent = STEP_LABELS[currentStep - 1] || "";

    if (barFill) {
      const pct = currentStep === 1 ? 0 : ((currentStep - 1) / (TOTAL_STEPS - 1)) * 100;
      barFill.style.width = pct + "%";
    }

    if (backBtn) backBtn.classList.toggle("d-none", currentStep === 1);
    if (nextBtn) nextBtn.classList.toggle("d-none", currentStep === TOTAL_STEPS);
    if (submitBtn) submitBtn.classList.toggle("d-none", currentStep !== TOTAL_STEPS);

    const progress = document.querySelector(".sm-wizard-progress");
    if (progress) {
      progress.setAttribute("aria-valuenow", String(currentStep));
      progress.setAttribute("aria-valuemax", String(TOTAL_STEPS));
    }
  }

  function goToStep(step) {
    if (step < 1 || step > TOTAL_STEPS) return;
    currentStep = step;
    updateProgressUI();
    hideAlert();

    const panel = form.querySelector('.sm-step-panel[data-sm-step="' + step + '"]');
    const heading = panel ? panel.querySelector(".sm-section-heading") : null;
    if (heading) {
      heading.setAttribute("tabindex", "-1");
      heading.focus({ preventScroll: true });
    }

    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function setSubmitting(isSubmitting) {
    if (!submitBtn) return;
    const label = submitBtn.querySelector(".sm-btn-label");
    const spinner = submitBtn.querySelector(".sm-btn-spinner");
    submitBtn.disabled = isSubmitting;
    if (nextBtn) nextBtn.disabled = isSubmitting;
    if (backBtn) backBtn.disabled = isSubmitting;
    if (label) label.textContent = isSubmitting ? "Submitting…" : "Submit";
    if (spinner) spinner.classList.toggle("d-none", !isSubmitting);
    submitBtn.classList.toggle("is-loading", isSubmitting);
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
    form.querySelectorAll(".sm-field").forEach(function (field) {
      field.addEventListener("input", function () {
        field.classList.remove("is-invalid");
      });
      field.addEventListener("change", function () {
        field.classList.remove("is-invalid");
      });
    });
  }

  if (backBtn) {
    backBtn.addEventListener("click", function () {
      if (currentStep > 1) goToStep(currentStep - 1);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      if (!validateStep(currentStep)) return;
      if (currentStep < TOTAL_STEPS) goToStep(currentStep + 1);
    });
  }

  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      if (currentStep < TOTAL_STEPS) {
        if (validateStep(currentStep)) goToStep(currentStep + 1);
        return;
      }
      if (!validateStep(currentStep)) return;

      setSubmitting(true);
      hideAlert();

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
        setSubmitting(false);
      }
    });
  }

  updateProgressUI();
})();
