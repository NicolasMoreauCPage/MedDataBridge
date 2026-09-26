(() => {
  const modal = document.getElementById('cloneGhtModal');
  const trigger = document.getElementById('clone-ght-button');
  if (!modal || !trigger) return;

  const close = () => {
    modal.classList.remove('modal-open');
    trigger.focus();
  };
  trigger.addEventListener('click', () => {
    const name = trigger.dataset.contextName || '';
    const code = trigger.dataset.contextCode || '';
    document.getElementById('clone_ght_source').value = `${name} (${code})`;
    document.getElementById('clone_ght_name').value = `${name} - Copie`;
    document.getElementById('clone_ght_code').value = `${code}-COPIE`;
    document.getElementById('clone_ght_connected_url').value = '';
    modal.classList.add('modal-open');
    document.getElementById('clone_ght_name').focus();
  });
  modal.addEventListener('click', (event) => {
    if (event.target === modal || event.target.closest('[data-close-ght-clone]')) close();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('modal-open')) close();
  });
})();
