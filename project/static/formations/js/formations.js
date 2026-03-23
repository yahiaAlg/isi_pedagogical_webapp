/* ISI PedagoApp — Formations JS */
(function () {
  "use strict";

  /* ── Generic row search ───────────────────────────────────── */
  function initSearch(inputId, clearId, rowClass) {
    const input = document.getElementById(inputId);
    const clear = document.getElementById(clearId);
    const rows  = document.querySelectorAll("." + rowClass);
    if (!input) return;
    input.addEventListener("input", function () {
      const q = this.value.trim().toLowerCase();
      rows.forEach(function (r) {
        r.classList.toggle("search-hidden", q.length > 0 && !r.textContent.toLowerCase().includes(q));
      });
    });
    if (clear) {
      clear.addEventListener("click", function () {
        input.value = "";
        input.dispatchEvent(new Event("input"));
        input.focus();
      });
    }
  }

  initSearch("formationSearch", "clearSearch", "formation-row");
  initSearch("sessionSearch",   "clearSearch", "session-row");

  /* ── Dirty form guard (shared) ────────────────────────────── */
  const form = document.querySelector("form.isi-dirty-guard");
  if (form) {
    let dirty = false;
    form.querySelectorAll("input, textarea, select").forEach(function (el) {
      el.addEventListener("change", function () { dirty = true; });
      el.addEventListener("input",  function () { dirty = true; });
    });
    form.addEventListener("submit", function () { dirty = false; });
    document.querySelectorAll("a.btn-ghost, a.topbar-btn").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        if (dirty && !confirm("Des modifications non enregistrées seront perdues. Continuer ?")) {
          e.preventDefault();
        }
      });
    });
  }

  /* ── AJAX score update ────────────────────────────────────── */
  function getCsrf() {
    const el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function updateResultBadge(participantId, result) {
    const badge = document.querySelector(".result-badge[data-pid='" + participantId + "']");
    if (!badge) return;
    badge.className = "isi-badge result-badge";
    badge.setAttribute("data-pid", participantId);
    const map = { passed: ["green", "Reçu"], failed: ["red", "Ajourné"], pending: ["gray", "En attente"], absent: ["red", "Absent"] };
    const [color, label] = map[result] || ["gray", result];
    badge.classList.add(color);
    badge.innerHTML = '<i class="bi bi-circle-fill" style="font-size:7px;"></i> ' + label;
  }

  document.querySelectorAll(".score-input[data-pid]").forEach(function (input) {
    input.addEventListener("change", function () {
      const pid = this.dataset.pid;
      const scoreType = this.dataset.scoreType;
      const url = "/formations/participants/" + pid + "/update-score/";
      const body = new URLSearchParams();
      body.append("csrfmiddlewaretoken", getCsrf());
      body.append(scoreType, this.value);

      fetch(url, { method: "POST", body: body })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.result) updateResultBadge(pid, data.result);
        })
        .catch(function () { /* silent */ });
    });
  });

  /* ── AJAX attendance toggle ───────────────────────────────── */
  document.querySelectorAll(".ajax-attendance[data-pid]").forEach(function (toggle) {
    toggle.addEventListener("change", function () {
      const pid = this.dataset.pid;
      const url = "/formations/participants/" + pid + "/toggle-attendance/";
      const body = new URLSearchParams();
      body.append("csrfmiddlewaretoken", getCsrf());
      body.append("present", this.checked ? "true" : "false");

      fetch(url, { method: "POST", body: body })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.result) updateResultBadge(pid, data.result);
        })
        .catch(function () { /* silent */ });
    });
  });

  /* ── location_type field show/hide ───────────────────────── */
  const locationSelect = document.getElementById("id_location_type");
  const roomField      = document.getElementById("row-room");
  const extField       = document.getElementById("row-external_location");

  function toggleLocationFields() {
    if (!locationSelect) return;
    const val = locationSelect.value;
    if (roomField) roomField.style.display = val === "institute" ? "" : "none";
    if (extField)  extField.style.display  = val === "on_site"   ? "" : "none";
  }

  if (locationSelect) {
    locationSelect.addEventListener("change", toggleLocationFields);
    toggleLocationFields();
  }

  /* ── formation auto-fill capacity ────────────────────────── */
  const formationSelect = document.getElementById("id_formation");
  const capacityInput   = document.getElementById("id_capacity");
  const formationData   = window.FORMATION_MAX_PARTICIPANTS || {};

  if (formationSelect && capacityInput) {
    formationSelect.addEventListener("change", function () {
      const max = formationData[this.value];
      if (max && !capacityInput.value) {
        capacityInput.value = max;
      }
    });
  }

})();
