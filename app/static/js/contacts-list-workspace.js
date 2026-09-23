/* Confirmation et suppression AJAX des contacts patient et venue. */
(function () {
  "use strict";

  const modal = document.getElementById("deleteModal");
  const modalText = document.getElementById("deleteModalText");
  const cancelButton = document.getElementById("cancelDelete");
  const confirmButton = document.getElementById("confirmDelete");
  if (!modal || !modalText || !cancelButton || !confirmButton) return;

  let deleteForm = null;

  function closeModal() {
    modal.classList.add("hidden");
    deleteForm = null;
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest(".delete-btn");
    if (!button) return;
    const form = button.closest("form");
    if (!form) return;
    event.preventDefault();
    const itemName = form.dataset.itemName.trim() || "ce contact";
    modalText.textContent = `Êtes-vous sûr de vouloir supprimer "${itemName}" ?`;
    modal.classList.remove("hidden");
    deleteForm = form;
  });

  cancelButton.addEventListener("click", closeModal);

  confirmButton.addEventListener("click", async () => {
    if (!deleteForm) return;
    const originalText = confirmButton.textContent;
    confirmButton.disabled = true;
    confirmButton.textContent = "Suppression…";
    try {
      const { response } = await window.medbridgeHttp.request(deleteForm.action, {
        method: "POST",
        body: new FormData(deleteForm),
        headers: { "X-Requested-With": "XMLHttpRequest" },
      });
      if (response.redirected) {
        window.location.href = response.url;
        return;
      }
      if (response.ok) {
        window.location.reload();
        return;
      }
      window.toastSystem?.show("Erreur lors de la suppression. Veuillez réessayer.", "error");
    } catch (error) {
      console.error("Erreur de suppression de contact :", error);
      window.toastSystem?.show("Erreur réseau. Veuillez réessayer.", "error");
    } finally {
      confirmButton.disabled = false;
      confirmButton.textContent = originalText;
      closeModal();
    }
  });
})();
