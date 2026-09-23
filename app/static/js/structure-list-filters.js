(() => {
  const workspace = document.querySelector("[data-structure-list]");
  if (!workspace?.dataset.filterBase) return;

  const applyFilters = () => {
    const params = new URLSearchParams();
    workspace.querySelectorAll("[data-filter-param]").forEach((control) => {
      const value = control.value.trim();
      if (value) params.set(control.dataset.filterParam, value);
    });
    const query = params.toString();
    window.location.assign(query ? `${workspace.dataset.filterBase}?${query}` : workspace.dataset.filterBase);
  };

  workspace.addEventListener("change", (event) => {
    if (event.target.matches("select[data-filter-param]")) applyFilters();
  });
  workspace.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || !event.target.matches("input[data-filter-param]")) return;
    event.preventDefault();
    applyFilters();
  });
})();
