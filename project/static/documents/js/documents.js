/* ISI PedagoApp — Documents JS */
(function () {
  "use strict";

  /* Confirm before triggering any generation link */
  document.querySelectorAll(".generate-confirm").forEach(function (el) {
    el.addEventListener("click", function (e) {
      var label = this.dataset.label || "ce document";
      if (!confirm("Générer " + label + " ? Un nouveau fichier sera créé.")) {
        e.preventDefault();
      }
    });
  });

  /* Batch attestations — select all / none */
  var selectAll = document.getElementById("selectAll");
  var selectNone = document.getElementById("selectNone");
  var checkboxes = document.querySelectorAll(".attestation-checkbox");

  if (selectAll) {
    selectAll.addEventListener("click", function (e) {
      e.preventDefault();
      checkboxes.forEach(function (cb) { cb.checked = true; });
    });
  }
  if (selectNone) {
    selectNone.addEventListener("click", function (e) {
      e.preventDefault();
      checkboxes.forEach(function (cb) { cb.checked = false; });
    });
  }
})();
