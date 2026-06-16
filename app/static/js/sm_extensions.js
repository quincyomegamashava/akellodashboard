(function () {
  const sm = window.smSalesMarketing;
  if (!sm) return;
  const page = window.SM_PAGE || "";

  function $(id) { return document.getElementById(id); }

  async function loadStats() {
    if (!$("sm-stat-total")) return;
    try {
      const s = await sm.fetchJson(sm.API.stats);
      $("sm-stat-total").textContent = s.total_leads;
      $("sm-stat-week").textContent = s.leads_this_week;
      $("sm-stat-consent").textContent = s.with_consent;
      $("sm-stat-dup").textContent = s.duplicates_open;
      $("sm-stat-events").textContent = s.active_events;
      const guide = $("sm-empty-guide");
      if (guide) guide.classList.toggle("d-none", s.total_leads > 0);
    } catch (e) { /* ignore */ }
  }

  let drawerLeadId = null;

  function closeDrawer() {
    const d = $("sm-lead-drawer");
    const b = $("sm-drawer-backdrop");
    if (d) d.classList.add("d-none");
    if (b) b.classList.add("d-none");
    drawerLeadId = null;
  }

  async function openLeadDrawer(id) {
    const body = $("sm-drawer-body");
    const title = $("sm-drawer-title");
    if (!body) return;
    drawerLeadId = id;
    body.innerHTML = '<p class="text-muted">Loading…</p>';
    $("sm-lead-drawer").classList.remove("d-none");
    $("sm-drawer-backdrop").classList.remove("d-none");
    try {
      const lead = await sm.fetchJson(sm.API.stakeholder(id));
      if (title) title.textContent = lead.full_name;
      let html = '<dl class="sm-drawer-dl small">';
      const fields = [
        ["Email", lead.email], ["Mobile", lead.mobile], ["Occupation", lead.occupation],
        ["Province", lead.province], ["School", lead.school_name], ["Organization", lead.organization],
        ["Event", lead.event_name], ["Interest", lead.interest_label], ["Status", lead.follow_up_status],
        ["Source", lead.source], ["Heard about", lead.heard_about],
        ["Consent", lead.consent_marketing ? "Yes" : "No"],
        ["Submitted", (lead.submitted_at || "").slice(0, 16).replace("T", " ")],
        ["Comments", lead.comments],
      ];
      fields.forEach(function (pair) {
        if (!pair[1]) return;
        html += "<dt>" + sm.esc(pair[0]) + "</dt><dd>" + sm.esc(String(pair[1])) + "</dd>";
      });
      html += "</dl>";
      if (lead.lead_score != null) {
        html += '<p class="small"><strong>Lead score:</strong> ' + lead.lead_score + "/100</p>";
      }
      try {
        const sug = await sm.fetchJson("/sales-marketing/api/stakeholders/" + id + "/suggested-action");
        if (sug.suggested_action) {
          html += '<p class="small text-primary"><strong>Next:</strong> ' + sm.esc(sug.suggested_action) + "</p>";
        }
        if (sug.whatsapp_url) {
          html += '<a class="btn btn-sm btn-success mb-2" href="' + sm.esc(sug.whatsapp_url) + '" target="_blank" rel="noopener">Open WhatsApp</a> ';
          html += '<button type="button" class="btn btn-sm btn-outline-success mb-2" id="sm-wa-log">Log WhatsApp</button>';
        }
      } catch (e2) { /* ignore */ }
      if (lead.is_duplicate_flag && !lead.duplicate_dismissed) {
        html += '<button type="button" class="btn btn-sm btn-outline-warning mb-2" id="sm-dismiss-dup">Dismiss duplicate flag</button>';
      }
      html += '<div class="sm-notes-section"><h3 class="h6">Timeline</h3><div id="sm-notes-list">';
      try {
        const tl = await sm.fetchJson("/sales-marketing/api/stakeholders/" + id + "/timeline");
        (tl.items || []).forEach(function (n) {
          html += '<div class="hub-timeline-item"><div class="hub-timeline-meta">' + sm.esc(n.actor_name) +
            " · " + sm.esc(n.activity_type) + " · " + sm.esc((n.created_at || "").slice(0, 16).replace("T", " ")) + "</div><div>" + sm.esc(n.summary) + "</div></div>";
        });
      } catch (e3) {
        (lead.notes || []).forEach(function (n) {
          html += '<div class="sm-note-item"><div class="sm-note-meta">' + sm.esc(n.author_name) +
            " · " + sm.esc((n.created_at || "").slice(0, 16).replace("T", " ")) + "</div><div>" + sm.esc(n.body) + "</div></div>";
        });
      }
      html += '</div><textarea class="form-control form-control-sm mt-2" id="sm-note-input" rows="2" placeholder="Add internal note…"></textarea>';
      html += '<button type="button" class="btn btn-sm btn-outline-primary mt-1" id="sm-note-add">Add note</button></div>';
      body.innerHTML = html;
      const dismiss = $("sm-dismiss-dup");
      if (dismiss) dismiss.addEventListener("click", async function () {
        await sm.fetchJson(sm.API.stakeholder(id) + "/dismiss-duplicate", { method: "POST" });
        openLeadDrawer(id);
        sm.loadLeads();
        loadStats();
      });
      const addNote = $("sm-note-add");
      if (addNote) addNote.addEventListener("click", async function () {
        const text = ($("sm-note-input") || {}).value;
        if (!text || !text.trim()) return;
        await sm.fetchJson(sm.API.stakeholder(id) + "/notes", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ body: text.trim() }),
        });
        openLeadDrawer(id);
      });
      const waLog = $("sm-wa-log");
      if (waLog) waLog.addEventListener("click", async function () {
        await sm.fetchJson("/sales-marketing/api/stakeholders/" + id + "/whatsapp-log", { method: "POST" });
        openLeadDrawer(id);
      });
    } catch (e) {
      body.innerHTML = '<p class="text-danger">' + sm.esc(e.message) + "</p>";
    }
  }

  window.smOpenLeadDrawer = openLeadDrawer;

  window.smOnLeadsLoadedBase = function () { loadStats(); };

  async function sendEmailPayload(payload) {
    return sm.fetchJson(sm.API.send, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  function initStakeholdersExtras() {
    loadStats();
    const copyBtn = $("sm-copy-connect");
    if (copyBtn) copyBtn.addEventListener("click", function () {
      navigator.clipboard.writeText(window.location.origin + "/connect");
      copyBtn.textContent = "Copied!";
      setTimeout(function () { copyBtn.textContent = "Copy link"; }, 2000);
    });
    const closeBtn = $("sm-drawer-close");
    const backdrop = $("sm-drawer-backdrop");
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (backdrop) backdrop.addEventListener("click", closeDrawer);
    const editBtn = $("sm-drawer-edit");
    if (editBtn) editBtn.addEventListener("click", function () {
      if (drawerLeadId) { closeDrawer(); sm.openLeadModal(drawerLeadId); }
    });
    const emailBtn = $("sm-drawer-email");
    if (emailBtn) emailBtn.addEventListener("click", function () {
      if (!drawerLeadId) return;
      sm.selectedLeadIds().clear();
      sm.selectedLeadIds().add(drawerLeadId);
      const cnt = $("sm-email-count");
      if (cnt) cnt.textContent = "1 recipient(s) with consent will be emailed.";
      new bootstrap.Modal($("smEmailModal")).show();
    });
    const bulkSel = $("sm-bulk-status");
    if (bulkSel) bulkSel.addEventListener("change", async function () {
      const status = bulkSel.value;
      if (!status) return;
      const ids = Array.from(sm.selectedLeadIds());
      if (!ids.length) { alert("Select at least one lead."); bulkSel.value = ""; return; }
      await sm.fetchJson(sm.API.bulkStatus, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stakeholder_ids: ids, follow_up_status: status }),
      });
      bulkSel.value = "";
      sm.loadLeads();
    });
    const filterEmail = $("sm-btn-email-filter");
    if (filterEmail) filterEmail.addEventListener("click", async function () {
      try {
        const preview = await sm.fetchJson(sm.API.previewCount + "?" + sm.filterParams().toString());
        if (!preview.count) { alert("No consented recipients match current filters."); return; }
        if (!confirm("Send to " + preview.count + " consented lead(s) matching filters?")) return;
        const subject = prompt("Email subject:");
        if (!subject) return;
        const body = prompt("Email message (HTML allowed):");
        if (!body) return;
        const data = await sendEmailPayload({
          filters: sm.filterParamsObject(),
          subject: subject,
          body_html: body,
        });
        alert("Sent " + data.sent + " of " + data.total);
        sm.loadLeads();
      } catch (e) { alert(e.message); }
    });
  }

  window.smOpenCampaignDetail = async function (id) {
    const body = $("sm-campaign-detail-body");
    const title = $("sm-campaign-detail-title");
    if (!body) return;
    body.innerHTML = '<p class="text-muted">Loading…</p>';
    new bootstrap.Modal($("smCampaignDetailModal")).show();
    try {
      const c = await sm.fetchJson(sm.API.campaign(id));
      if (title) title.textContent = c.subject;
      let html = '<p class="small"><strong>Status:</strong> ' + sm.esc(c.status) +
        " · <strong>Recipients:</strong> " + c.recipient_count + "</p>";
      html += '<div class="sm-campaign-body-preview border rounded p-2 mb-3 small">' + c.body_html + "</div>";
      html += '<table class="table table-sm"><thead><tr><th>Email</th><th>Status</th><th>Error</th></tr></thead><tbody>';
      (c.recipients || []).forEach(function (r) {
        html += "<tr><td>" + sm.esc(r.email) + "</td><td>" + sm.esc(r.status) +
          '</td><td class="' + (r.error_message ? "text-danger" : "") + '">' + sm.esc(r.error_message || "—") + "</td></tr>";
      });
      html += "</tbody></table>";
      body.innerHTML = html;
    } catch (e) {
      body.innerHTML = '<p class="text-danger">' + sm.esc(e.message) + "</p>";
    }
  };

  function initCampaignsExtras() {
    const tplSel = $("sm-campaign-template");
    if (tplSel) {
      sm.fetchJson("/sales-marketing/api/email-templates").then(function (rows) {
        rows.forEach(function (t) {
          const opt = document.createElement("option");
          opt.value = t.id;
          opt.textContent = t.name;
          opt.dataset.subject = t.subject;
          opt.dataset.body = t.body_html;
          tplSel.appendChild(opt);
        });
      }).catch(function () {});
      tplSel.addEventListener("change", function () {
        const opt = tplSel.options[tplSel.selectedIndex];
        if (!opt || !opt.dataset.subject) return;
        const sub = $("sm-campaign-subject");
        const body = $("sm-campaign-body");
        if (sub) sub.value = opt.dataset.subject;
        if (body) body.value = opt.dataset.body;
      });
    }
    document.querySelectorAll(".sm-token-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        const body = $("sm-campaign-body");
        if (body) body.value += chip.textContent;
      });
    });
    const sendBtn = $("sm-campaign-send");
    if (sendBtn) sendBtn.addEventListener("click", async function () {
      const subject = ($("sm-campaign-subject") || {}).value;
      const bodyHtml = ($("sm-campaign-body") || {}).value;
      const rawIds = ($("sm-campaign-ids") || {}).value || "";
      const ids = rawIds.split(",").map(function (x) { return parseInt(x.trim(), 10); }).filter(Boolean);
      if (!subject || !bodyHtml) { alert("Subject and message required."); return; }
      if (!ids.length) { alert("Enter stakeholder IDs or use Stakeholders page."); return; }
      try {
        const data = await sendEmailPayload({ stakeholder_ids: ids, subject: subject, body_html: bodyHtml });
        alert("Sent " + data.sent + " of " + data.total);
        location.reload();
      } catch (e) { alert(e.message); }
    });
  }

  window.smShowEventQr = function (eventId) {
    const ev = sm.getEventsCache().find(function (e) { return e.id === eventId; });
    const urlInput = $("sm-qr-url");
    const canvas = $("sm-qr-canvas");
    if (!ev || !urlInput) return;
    const url = ev.connect_url || (window.location.origin + "/connect?event=" + eventId);
    urlInput.value = url;
    if (canvas && window.QRCode) {
      QRCode.toCanvas(canvas, url, { width: 200, margin: 1 }, function () {});
    }
    new bootstrap.Modal($("smQrModal")).show();
  };

  function initEventsExtras() {
    const copy = $("sm-qr-copy");
    if (copy) copy.addEventListener("click", function () {
      const v = ($("sm-qr-url") || {}).value;
      if (v) navigator.clipboard.writeText(v);
      copy.textContent = "Copied!";
      setTimeout(function () { copy.textContent = "Copy link"; }, 2000);
    });
    const list = $("sm-events-list");
    if (list && !list.children.length) {
      list.innerHTML = '<div class="sm-empty-guide"><h2 class="h6">No events yet</h2><p class="small text-muted">Create your first event, assign attending staff, then share the connect link or QR code at the stand.</p></div>';
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (page === "stakeholders") initStakeholdersExtras();
    if (page === "campaigns") initCampaignsExtras();
    if (page === "events") initEventsExtras();
  });
})();
