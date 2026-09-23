(() => {
  "use strict";

  document.querySelector("[data-ej-scenarios-filter]")?.addEventListener("change", (event) => {
    if (event.target.matches("[data-auto-submit]")) {
      event.currentTarget.requestSubmit();
    }
  });
})();
