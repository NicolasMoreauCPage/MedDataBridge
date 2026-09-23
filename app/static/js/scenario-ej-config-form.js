(() => {
  document.querySelectorAll(".scenario-ej-config .uf-select").forEach((select) => {
    select.addEventListener("focus", () => {
      select.size = Math.min(10, select.options.length);
    });
    select.addEventListener("blur", () => {
      select.size = 1;
    });
    select.addEventListener("change", () => {
      select.size = 1;
      select.blur();
    });
  });
})();
