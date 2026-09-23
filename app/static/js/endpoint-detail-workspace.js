(() => {
  const ghtSelect = document.getElementById("ght_select");
  const ejSelect = document.getElementById("ej_select");
  if (!ghtSelect || !ejSelect) return;

  const filterEjs = () => {
    const ght = ghtSelect.value;
    let selectedVisible = false;
    Array.from(ejSelect.options).forEach((option) => {
      if (!option.value) return;
      const visible = !ght || String(option.dataset.ght || "") === String(ght);
      option.hidden = !visible;
      if (!visible && option.selected) option.selected = false;
      if (visible && option.selected) selectedVisible = true;
    });
    if (!selectedVisible && ejSelect.selectedIndex > 0) ejSelect.value = "";
  };
  const syncGhtFromEj = () => {
    if (ghtSelect.value) return;
    const ght = ejSelect.options[ejSelect.selectedIndex]?.dataset.ght;
    if (ght) ghtSelect.value = String(ght);
  };
  ghtSelect.addEventListener("change", filterEjs);
  ejSelect.addEventListener("change", syncGhtFromEj);
  syncGhtFromEj();
  filterEjs();
})();
