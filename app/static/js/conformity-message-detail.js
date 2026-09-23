(() => {
  "use strict";

  const button = document.getElementById("copyRawMessageBtn");
  const status = document.getElementById("copyRawMessageStatus");
  const message = document.getElementById("rawMessage");

  button?.addEventListener("click", async () => {
    if (!message) return;
    button.disabled = true;
    try {
      await navigator.clipboard.writeText(message.innerText);
      const confirmation = "Message copié dans le presse-papier.";
      status.textContent = confirmation;
      window.toastSystem?.show(confirmation, "success");
    } catch {
      const error = "Copie impossible : sélectionnez le message puis copiez-le manuellement.";
      status.textContent = error;
      window.toastSystem?.show(error, "error");
    } finally {
      button.disabled = false;
    }
  });
})();
