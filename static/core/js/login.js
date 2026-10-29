/* accounts/js/login.js */
(function () {
  "use strict";
  const toggleBtn = document.getElementById("toggle-password");
  const passwordInput = document.getElementById("id_password");
  const eye = document.getElementById("toggle-eye");

  if (toggleBtn && passwordInput) {
    toggleBtn.addEventListener("click", function () {
      const isHidden = passwordInput.type === "password";
      passwordInput.type = isHidden ? "text" : "password";
      eye.className = isHidden ? "bi bi-eye-slash-fill" : "bi bi-eye-fill";
    });
  }
})();
