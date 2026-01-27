// app/static/js/settings.js
// Progressive enhancement for the settings form
(function () {
  const form = document.getElementById('settings-form');
  if (!form) return;

  const statusBox = document.getElementById('settings-status');
  const { fetchJson, showAlert } = window.ChronoCam || {};

  const successMsg = form.dataset.saveSuccess || 'Einstellungen gespeichert';
  const errorMsg = form.dataset.saveError || 'Speichern fehlgeschlagen';
  const geoSuccessMsg = form.dataset.geoSuccess || 'Koordinaten aus Browserstandort übernommen';
  const geoUnsupportedMsg = form.dataset.geoUnsupported || 'Browser-Geolokalisierung wird nicht unterstützt';
  const geoDeniedMsg = form.dataset.geoDenied || 'Standortfreigabe verweigert';
  const geoErrorMsg = form.dataset.geoError || 'Standort konnte nicht ermittelt werden';

  const latInput = form.querySelector('input[name="CITY_LAT"]');
  const lonInput = form.querySelector('input[name="CITY_LON"]');
  const tzInput = form.querySelector('input[name="CITY_TZ"]');
  const geoBtn = document.getElementById('geo-browser-btn');

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

  function setTimezoneFromBrowser() {
    if (!tzInput) return;
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz) {
        tzInput.value = tz;
      }
    } catch (err) {
      console.warn('Could not resolve browser timezone', err);
    }
  }

  function handleGeoError(err) {
    if (!showAlert) return;
    if (err && err.code === 1) {
      showAlert(statusBox, { message: geoDeniedMsg, type: 'warning', dismissMs: 6000 });
      return;
    }
    showAlert(statusBox, { message: geoErrorMsg, type: 'danger', dismissMs: 6000 });
  }

  function handleGeoSuccess(position) {
    if (!latInput || !lonInput) return;
    const { latitude, longitude } = position.coords || {};
    if (typeof latitude === 'number') latInput.value = latitude.toFixed(6);
    if (typeof longitude === 'number') lonInput.value = longitude.toFixed(6);
    setTimezoneFromBrowser();
    if (showAlert) {
      showAlert(statusBox, { message: geoSuccessMsg, type: 'success', dismissMs: 5000 });
    }
  }

  function handleGeoClick() {
    if (!navigator.geolocation) {
      if (showAlert) {
        showAlert(statusBox, { message: geoUnsupportedMsg, type: 'warning', dismissMs: 6000 });
      }
      return;
    }
    if (geoBtn) geoBtn.disabled = true;
    navigator.geolocation.getCurrentPosition(handleGeoSuccess, handleGeoError, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 300000,
    });
    setTimeout(() => {
      if (geoBtn) geoBtn.disabled = false;
    }, 2000);
  }

  form.addEventListener('submit', handleSubmit);
  if (geoBtn && latInput && lonInput) {
    geoBtn.addEventListener('click', handleGeoClick);
  }
  dismissExistingAlert();
})();
