/* ISI PedagoApp — Trainer form JS */
(function () {
  "use strict";

  /* RTL on Arabic fields */
  ["id_first_name_ar", "id_last_name_ar"].forEach(function (id) {
    const el = document.getElementById(id);
    if (el) el.setAttribute("dir", "rtl");
  });

  /* Dirty-form leave guard */
  const form = document.querySelector("form[method='post']");
  let dirty = false;
  if (form) {
    form.querySelectorAll("input, textarea, select").forEach(function (el) {
      el.addEventListener("change", function () { dirty = true; });
      el.addEventListener("input",  function () { dirty = true; });
    });
    form.addEventListener("submit", function () { dirty = false; });
    document.querySelectorAll("a.btn-ghost").forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        if (dirty && !confirm("Des modifications non enregistrées seront perdues. Continuer ?")) {
          e.preventDefault();
        }
      });
    });
  }
})();
