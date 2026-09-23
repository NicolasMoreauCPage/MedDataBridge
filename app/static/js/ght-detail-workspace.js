(() => {
  const modal = document.getElementById("cloneModal");
  const form = document.getElementById("cloneForm");
  if (!modal || !form || !modal.dataset.cloneBase) return;

  let trigger = null;
  const close = () => {
    modal.classList.remove("modal-open");
    trigger?.focus();
    trigger = null;
  };
  document.addEventListener("click", (event) => {
    const button = event.target.closest(".clone-btn");
    if (button) {
      trigger = button;
      document.getElementById("clone_original_name").value = `${button.dataset.ejName} (FINESS: ${button.dataset.ejFiness})`;
      document.getElementById("new_name").value = `${button.dataset.ejName} - Copie`;
      document.getElementById("new_finess_ej").value = "";
      form.action = `${modal.dataset.cloneBase}/${encodeURIComponent(button.dataset.ejId)}/clone`;
      modal.classList.add("modal-open");
      document.getElementById("new_name").focus();
      return;
    }
    if (event.target.closest("[data-close-clone-modal]") || event.target === modal) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("modal-open")) close();
  });
})();
