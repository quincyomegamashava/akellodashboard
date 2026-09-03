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
  const isPrefillLocked = Boolean(prefillId && prefillEvent);

  const stepPanels = form ? Array.from(form.querySelectorAll(".sm-step-panel")) : [];
  const wizardSteps = document.querySelectorAll(".sm-wizard-step");
  const barFill = document.getElementById("sm-wizard-bar-fill");
  const backBtn = document.getElementById("sm-back-btn");
  const nextBtn = document.getElementById("sm-next-btn");
  const submitBtn = document.getElementById("sm-submit-btn");

  const TOTAL_STEPS = 3;
  let currentStep = 1;
  let eventsAbort = null;
  let schoolsAbort = null;

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
    if (isPrefillLocked || !eventDate || !eventSelect || eventSelect.tagName !== "SELECT") return;
    const d = eventDate.value || new Date().toISOString().slice(0, 10);
    if (eventsAbort) eventsAbort.abort();
    eventsAbort = typeof AbortController !== "undefined" ? new AbortController() : null;
    try {
      const res = await fetch(
        "/api/public/marketing-events?date=" + encodeURIComponent(d),
        eventsAbort ? { signal: eventsAbort.signal } : undefined
      );
      if (!res.ok) throw new Error("Could not load events");
      const events = await res.json();
      if (!Array.isArray(events)) return;
      const cur = eventSelect.value;
      eventSelect.innerHTML = '<option value="">Not at an event / General enquiry</option>';
      events.forEach(function (ev) {
        const opt = document.createElement("option");
        opt.value = String(ev.id);
        opt.textContent = ev.name + (ev.location ? " — " + ev.location : "");
        eventSelect.appendChild(opt);
      });
      if (cur) eventSelect.value = cur;
    } catch (e) {
      if (e && e.name === "AbortError") return;
      console.error(e);
    }
  }

  async function loadSchools(provinceName) {
    if (!provinceName || !schoolList) return;
    if (schoolsAbort) schoolsAbort.abort();
    schoolsAbort = typeof AbortController !== "undefined" ? new AbortController() : null;
    try {
      const res = await fetch(
        "/api/public/schools/" + encodeURIComponent(provinceName),
        schoolsAbort ? { signal: schoolsAbort.signal } : undefined
      );
      if (!res.ok) return;
      const schools = await res.json();
      if (!Array.isArray(schools)) return;
      schoolList.innerHTML = "";
      schools.slice(0, 200).forEach(function (s) {
        const opt = document.createElement("option");
        opt.value = typeof s === "string" ? s : (s.name || s.school_name || "");
        if (opt.value) schoolList.appendChild(opt);
      });
    } catch (e) {
      if (e && e.name === "AbortError") return;
      /* optional autocomplete */
    }
  }

  if (!isPrefillLocked && eventDate) {
    eventDate.addEventListener("change", loadEvents);
    loadEvents();
  }

  if (province) {
    province.addEventListener("change", function () {
      loadSchools(province.value);
    });
  }

  if (form) {
    form.querySelectorAll(".sm-field").forEach(function (field) {
      field.addEventListener("input", function () {
        field.classList.remove("is-invalid");
        const hp = form.querySelector('[name="sm_hp_field"]');
        if (hp) {
          hp.dataset.smUserInteracted = "1";
          hp.value = "";
        }
      });
      field.addEventListener("change", function () {
        field.classList.remove("is-invalid");
        const hp = form.querySelector('[name="sm_hp_field"]');
        if (hp) {
          hp.dataset.smUserInteracted = "1";
          hp.value = "";
        }
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
        sm_hp_field: "",
      };

      // Ignore autofill in the honeypot; only treat as bot if it was filled
      // without the user interacting with real fields (see hpTouchedBelow).
      const hpInput = form.querySelector('[name="sm_hp_field"]');
      if (hpInput && hpInput.dataset.smUserInteracted !== "1" && (hpInput.value || "").trim()) {
        payload.sm_hp_field = hpInput.value.trim();
      }

      try {
        const res = await fetch("/api/public/stakeholder-leads", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(function () { return {}; });
        // Real saves return 201. Honeypot returns 200 {"ok":true} without a save.
        if (res.status !== 201 || data.ok !== true) {
          const detail = data.error || ("Submission failed (HTTP " + res.status + "). Please try again.");
          throw new Error(detail);
        }
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
