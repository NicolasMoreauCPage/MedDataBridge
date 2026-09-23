/* Interactions de démonstration du styleguide. */
(function () {
  "use strict";

  document.addEventListener("click", (event) => {
    const modalTrigger = event.target.closest("[data-styleguide-modal]");
    if (modalTrigger) document.getElementById(modalTrigger.dataset.styleguideModal)?.classList.add("modal-open");

    const toastTrigger = event.target.closest("[data-styleguide-toast]");
    if (toastTrigger) {
      const duration = toastTrigger.hasAttribute("data-duration")
        ? Number(toastTrigger.dataset.duration)
        : 5000;
      window.toastSystem?.show(
        toastTrigger.dataset.message || "Notification de démonstration",
        toastTrigger.dataset.styleguideToast,
        duration,
      );
    }

    const loadingTrigger = event.target.closest("[data-styleguide-loading]");
    if (loadingTrigger) {
      window.loadingSystem?.showOverlay(loadingTrigger.dataset.styleguideLoading);
      window.setTimeout(() => window.loadingSystem?.hideOverlay(), 3000);
    }
  });
})();
