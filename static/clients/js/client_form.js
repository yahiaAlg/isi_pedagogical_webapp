/* ISI PedagoApp — Client form JS */
(function () {
  "use strict";

  /* RTL detection for Arabic field */
  const nameArInput = document.getElementById("id_name_ar");
  if (nameArInput) {
    nameArInput.setAttribute("dir", "rtl");
  }

  /* Confirm before navigating away if form is dirty */
  const form = document.querySelector("form[method='post']");
  let formDirty = false;

  if (form) {
    const inputs = form.querySelectorAll("input, textarea, select");
    inputs.forEach(function (el) {
      el.addEventListener("change", function () { formDirty = true; });
      el.addEventListener("input",  function () { formDirty = true; });
    });

    form.addEventListener("submit", function () { formDirty = false; });

    const cancelBtns = document.querySelectorAll("a.btn-ghost");
    cancelBtns.forEach(function (btn) {
      btn.addEventListener("click", function (e) {
        if (formDirty) {
          if (!confirm("Des modifications non enregistrées seront perdues. Continuer ?")) {
            e.preventDefault();
          }
        }
      });
    });
  }
})();
