/* ISI PedagoApp — Base JS */

(function () {
  "use strict";

  /* ── Sidebar toggle (mobile) ──────────────────────────── */
  const sidebar  = document.getElementById("sidebar");
  const overlay  = document.getElementById("sidebar-overlay");
  const toggleBtn = document.getElementById("sidebarToggle");

  function openSidebar() {
    sidebar.classList.add("sidebar-open");
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";
  }

  function closeSidebar() {
    sidebar.classList.remove("sidebar-open");
    overlay.classList.remove("active");
    document.body.style.overflow = "";
  }

  if (toggleBtn) {
    toggleBtn.addEventListener("click", function () {
      sidebar.classList.contains("sidebar-open") ? closeSidebar() : openSidebar();
    });
  }

  if (overlay) {
    overlay.addEventListener("click", closeSidebar);
  }

  /* ── Flash message auto-dismiss (4500 ms) ─────────────── */
  const flashMessages = document.querySelectorAll(".flash-msg");
  flashMessages.forEach(function (msg) {
    setTimeout(function () {
      msg.style.transition = "opacity 0.4s ease";
      msg.style.opacity = "0";
      setTimeout(function () {
        msg.remove();
      }, 420);
    }, 4500);
  });

  /* ── Active nav highlighting ──────────────────────────── */
  const currentPath = window.location.pathname;
  const navLinks = document.querySelectorAll(".nav-item-link[data-path]");
  navLinks.forEach(function (link) {
    const linkPath = link.getAttribute("data-path");
    if (linkPath && currentPath.startsWith(linkPath) && linkPath !== "/") {
      link.classList.add("active");
      // Expand parent collapse if any
      const parent = link.closest(".collapse");
      if (parent) {
        parent.classList.add("show");
        const trigger = document.querySelector('[data-bs-target="#' + parent.id + '"]');
        if (trigger) trigger.setAttribute("aria-expanded", "true");
      }
    }
  });
  // Dashboard exact match
  const dashLink = document.querySelector(".nav-item-link[data-path='/']");
  if (dashLink && currentPath === "/") {
    dashLink.classList.add("active");
  }
})();
