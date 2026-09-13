/* Actualisation discrète des jeux de scénario encore en cours. */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", () => {
    const workspace = document.querySelector("[data-scenario-play-workspace][data-auto-refresh='true']");
    if (!workspace) return;
    const status = document.getElementById("scenario-play-refresh-status");
    let remaining = 5;
    const timer = window.setInterval(() => {
      remaining -= 1;
      if (status) status.textContent = "Actualisation automatique dans " + remaining + " seconde" + (remaining > 1 ? "s" : "") + "…";
      if (remaining <= 0) {
        window.clearInterval(timer);
        window.location.reload();
      }
    }, 1000);
  });
})();
