(() => {
  "use strict";

  const button = document.getElementById("copyHl7PayloadBtn");
  const status = document.getElementById("copyHl7PayloadStatus");
  const data = document.getElementById("hl7PayloadData");
  const payload = data ? JSON.parse(data.textContent) : "";

  button?.addEventListener("click", async () => {
    button.disabled = true;
    try {
      await navigator.clipboard.writeText(payload);
      status.textContent = "Message HL7 copié.";
      window.toastSystem?.show("Message HL7 copié.", "success");
    } catch {
      status.textContent = "Copie impossible.";
      window.toastSystem?.show("Copie impossible.", "error");
    } finally {
      button.disabled = false;
    }
  });
})();
