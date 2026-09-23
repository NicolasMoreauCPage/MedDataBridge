(() => {
  const modal = document.getElementById("deleteModal");
  const form = document.getElementById("deleteForm");
  if (!modal || !form) return;

  let trigger = null;
  const close = () => {
    modal.classList.add("hidden");
    trigger?.focus();
    trigger = null;
  };

  document.addEventListener("click", (event) => {
    const openButton = event.target.closest("[data-delete-action]");
    if (openButton) {
      trigger = openButton;
      form.action = openButton.dataset.deleteAction;
      modal.classList.remove("hidden");
      form.querySelector("button[type='submit']")?.focus();
      return;
    }
    if (event.target.closest("[data-close-delete-modal]")) close();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.classList.contains("hidden")) close();
  });
})();
