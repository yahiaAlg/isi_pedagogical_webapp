/* ISI PedagoApp — Trainer list JS */
(function () {
  "use strict";

  const searchInput = document.getElementById("trainerSearch");
  const clearBtn    = document.getElementById("clearSearch");
  const rows        = document.querySelectorAll(".trainer-row");

  function filterRows(query) {
    const q = query.trim().toLowerCase();
    rows.forEach(function (row) {
      row.classList.toggle("search-hidden", q.length > 0 && !row.textContent.toLowerCase().includes(q));
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () { filterRows(this.value); });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      if (searchInput) { searchInput.value = ""; filterRows(""); searchInput.focus(); }
    });
  }
})();
