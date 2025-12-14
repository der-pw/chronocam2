// app/static/js/settings.js
// Progressive enhancement for the settings form
(function () {
  const form = document.getElementById('settings-form');
  if (!form) return;

  const statusBox = document.getElementById('settings-status');
  const { fetchJson, showAlert } = window.ChronoCam || {};

  const successMsg = form.dataset.saveSuccess || 'Einstellungen gespeichert';
  const errorMsg = form.dataset.saveError || 'Speichern fehlgeschlagen';

  const dismissExistingAlert = () => {
    const alert = document.getElementById('save-alert');
    if (alert) {
      setTimeout(() => alert.remove(), 3000);
    }
  };

  async function handleSubmit(event) {
    event.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    try {
      await fetchJson('/update', { method: 'POST', body: new FormData(form) }, { timeoutMs: 15000 });
      showAlert(statusBox, { message: successMsg, type: 'success', dismissMs: 5000 });
    } catch (err) {
      console.warn('Saving settings failed', err);
      showAlert(statusBox, { message: errorMsg, type: 'danger', dismissMs: 6000 });
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  form.addEventListener('submit', handleSubmit);
  dismissExistingAlert();
})();
