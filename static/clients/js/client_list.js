/* ISI PedagoApp — Client list JS */
(function () {
  "use strict";

  const searchInput = document.getElementById("clientSearch");
  const clearBtn    = document.getElementById("clearSearch");
  const rows        = document.querySelectorAll(".client-row");

  function filterRows(query) {
    const q = query.trim().toLowerCase();
    rows.forEach(function (row) {
      const text = row.textContent.toLowerCase();
      row.classList.toggle("search-hidden", q.length > 0 && !text.includes(q));
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      filterRows(this.value);
    });
  }

  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      if (searchInput) {
        searchInput.value = "";
        filterRows("");
        searchInput.focus();
      }
    });
  }
})();
