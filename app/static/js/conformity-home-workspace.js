/* Bascule asynchrone du mode strict PAM FR par entité juridique. */
(function () {
  "use strict";

  function updateStrictModeUI(form, isStrict) {
    const badge = form.parentElement.querySelector("span");
    const button = form.querySelector("button");
    const toggle = button?.querySelector("span");
    if (!badge || !button || !toggle) return;
    badge.className = isStrict
      ? "inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-purple-100 text-purple-800"
      : "inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-600";
    badge.textContent = `${isStrict ? "🔒" : "🔓"} Mode strict PAM FR`;
    button.className = isStrict
      ? "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 bg-purple-600"
      : "relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 bg-slate-200";
    toggle.className = isStrict
      ? "inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-6"
      : "inline-block h-4 w-4 transform rounded-full bg-white transition-transform translate-x-1";
  }

  document.querySelectorAll('form[id^="strict-form-"]').forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button");
      const hiddenInput = form.querySelector('input[name="strict_pam_fr"]');
      if (!button || !hiddenInput) return;
      button.disabled = true;
      button.style.opacity = "0.6";
      try {
        const { data } = await window.medbridgeHttp.request(form.action, {
          method: "POST", body: new FormData(form), headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        updateStrictModeUI(form, data.strict_pam_fr);
        hiddenInput.value = data.strict_pam_fr ? "false" : "true";
      } catch (error) {
        console.error("Erreur de bascule du mode strict :", error);
        window.location.reload();
      } finally {
        button.disabled = false;
        button.style.opacity = "1";
      }
    });
  });
})();
