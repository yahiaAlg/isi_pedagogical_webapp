/* Bell dropdown: toggle, mark-all-read, and polling of the unread feed. */
(function () {
  "use strict";
  var bell = document.getElementById("bell");
  if (!bell) return;

  var btn = document.getElementById("bellBtn");
  var panel = document.getElementById("bellPanel");
  var list = document.getElementById("bellList");
  var badge = document.getElementById("bellBadge");
  var readAll = document.getElementById("bellReadAll");
  var feedUrl = bell.dataset.feedUrl;
  var readAllUrl = bell.dataset.readAllUrl;
  var POLL_MS = 45000;
  var baseTitle = document.title;
  var lastCount = parseInt((badge.textContent || "0").replace("+", ""), 10) || 0;

  function csrf() {
    var el = bell.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function render(data, allowRing) {
    list.innerHTML = data.html;
    var n = data.count;
    badge.textContent = n > 99 ? "99+" : String(n);
    badge.hidden = n === 0;
    document.title = n > 0 ? "(" + n + ") " + baseTitle : baseTitle;
    if (allowRing && n > lastCount) {
      btn.classList.add("ring");
      setTimeout(function () { btn.classList.remove("ring"); }, 2200);
    }
    lastCount = n;
  }

  function refresh(allowRing) {
    return fetch(feedUrl, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) render(data, allowRing); })
      .catch(function () { /* offline: keep what we have */ });
  }

  function setOpen(open) {
    panel.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) refresh(false);
  }

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(panel.hidden);
  });
  document.addEventListener("click", function (e) {
    if (!panel.hidden && !bell.contains(e.target)) setOpen(false);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !panel.hidden) { setOpen(false); btn.focus(); }
  });

  readAll.addEventListener("click", function () {
    var body = new URLSearchParams({ csrfmiddlewaretoken: csrf() });
    fetch(readAllUrl, {
      method: "POST", credentials: "same-origin", body: body,
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) { if (data) render(data, false); });
  });

  // Poll only while the tab is visible; catch up immediately when it returns.
  var timer = setInterval(function () { if (!document.hidden) refresh(true); }, POLL_MS);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) refresh(true); });
  window.addEventListener("beforeunload", function () { clearInterval(timer); });
})();
