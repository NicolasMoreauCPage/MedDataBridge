/* Shared progressive-enhancement controls for the server-rendered UI. */
(function () {
  "use strict";

  let triggerElement = null;

  function elements() {
    return {
      dialog: document.getElementById("confirm-dialog"),
      title: document.getElementById("confirm-dialog-title"),
      message: document.getElementById("confirm-dialog-message"),
      accept: document.getElementById("confirm-dialog-accept"),
    };
  }

  function openConfirmation(options) {
    const { dialog, title, message, accept } = elements();
    if (!dialog || !title || !message || !accept) {
      window.toastSystem?.show?.("Le dialogue de confirmation n’est pas disponible.", "error");
      return Promise.resolve(false);
    }

    title.textContent = options.title || "Confirmer l’action";
    message.textContent = options.message || "Souhaitez-vous continuer ?";
    accept.textContent = options.acceptLabel || "Confirmer";
    accept.classList.toggle("bg-red-600", options.variant === "danger");
    accept.classList.toggle("hover:bg-red-700", options.variant === "danger");
    accept.classList.toggle("bg-blue-600", options.variant !== "danger");
    accept.classList.toggle("hover:bg-blue-700", options.variant !== "danger");

    return new Promise((resolve) => {
      const close = () => {
        dialog.removeEventListener("close", onClose);
        accept.removeEventListener("click", onAccept);
        resolve(dialog.returnValue === "confirm");
      };
      const onClose = close;
      const onAccept = () => dialog.close("confirm");
      dialog.addEventListener("close", onClose, { once: true });
      accept.addEventListener("click", onAccept, { once: true });
      dialog.showModal();
    });
  }

  document.addEventListener("submit", async (event) => {
    const form = event.target instanceof HTMLFormElement ? event.target : null;
    if (!form || !form.dataset.confirm || form.dataset.confirmBypass === "true") {
      if (form) delete form.dataset.confirmBypass;
      return;
    }
    event.preventDefault();
    triggerElement = document.activeElement;
    const confirmed = await openConfirmation({
      title: form.dataset.confirmTitle,
      message: form.dataset.confirm,
      acceptLabel: form.dataset.confirmAccept,
      variant: form.dataset.confirmVariant || "danger",
    });
    if (confirmed) {
      form.dataset.confirmBypass = "true";
      form.requestSubmit(event.submitter || undefined);
    } else if (triggerElement instanceof HTMLElement) {
      triggerElement.focus();
    }
  });

  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-dismiss-alert]");
    if (trigger) trigger.closest("[role='alert']")?.remove();
  });

  window.PameliaUi = window.PameliaUi || {};
  window.PameliaUi.confirm = openConfirmation;
})();
