document.querySelectorAll('.theme-toggle').forEach(button => button.addEventListener('click', () => {
  const theme = document.documentElement.dataset.bsTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.bsTheme = theme;
  try { localStorage.setItem('sfo-theme', theme); } catch (_) {}
}));
document.getElementById('menuToggle')?.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));
let pendingForm;
document.querySelectorAll('form[data-confirm]').forEach(form => {
  form.addEventListener('submit', event => {
    if (form.dataset.confirmed === 'yes') return;
    const message = form.dataset.confirm;
    if (!window.bootstrap) { if (!window.confirm(message)) event.preventDefault(); return; }
    event.preventDefault();
    pendingForm = form;
    document.getElementById('confirmMessage').textContent = message;
    bootstrap.Modal.getOrCreateInstance(document.getElementById('confirmModal')).show();
  });
});
document.getElementById('confirmAction')?.addEventListener('click', () => {
  if (!pendingForm) return;
  pendingForm.dataset.confirmed = 'yes';
  pendingForm.requestSubmit();
  bootstrap.Modal.getInstance(document.getElementById('confirmModal')).hide();
});
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', event => {
  if (event.defaultPrevented || form.method.toLowerCase() !== 'post') return;
  const button = event.submitter;
  if (button) { button.setAttribute('aria-busy', 'true'); button.classList.add('is-loading'); }
}));
