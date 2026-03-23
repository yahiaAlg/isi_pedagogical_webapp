/* ============================================================
   ISI Pedagogical App — Global JS
   ============================================================ */

(function () {
  "use strict";

  /* ── Sidebar toggle (mobile) ─────────────────────────────── */
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  const toggleBtn = document.getElementById("topbar-toggle");

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add("open");
    overlay.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove("open");
    overlay.classList.remove("open");
    document.body.style.overflow = "";
  }

  if (toggleBtn) toggleBtn.addEventListener("click", openSidebar);
  if (overlay) overlay.addEventListener("click", closeSidebar);

  /* ── Flash message auto-dismiss (4500 ms) ────────────────── */
  document.querySelectorAll(".alert[data-auto-dismiss]").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity .4s ease";
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 420);
    }, 4500);
  });

  /* ── Active nav detection ────────────────────────────────── */
  // Mark the correct sidebar link as active based on current path
  const path = window.location.pathname;
  document.querySelectorAll(".nav-item-link[href]").forEach(function (link) {
    const href = link.getAttribute("href");
    if (href && href !== "/" && path.startsWith(href)) {
      link.classList.add("active");
      // Expand any parent collapse
      const parentCollapse = link.closest(".collapse");
      if (parentCollapse) {
        parentCollapse.classList.add("show");
        const trigger = document.querySelector(
          '[data-bs-target="#' + parentCollapse.id + '"]',
        );
        if (trigger) trigger.setAttribute("aria-expanded", "true");
      }
    }
    if (href === "/" && path === "/") {
      link.classList.add("active");
    }
  });
})();
