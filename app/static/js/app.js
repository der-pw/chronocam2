// app/static/js/app.js
// Shared helpers for ChronoCam frontends
(function () {
  const ChronoCam = {};

  ChronoCam.fetchJson = async function fetchJson(url, options = {}, { timeoutMs = 10000 } = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
        headers: {
          Accept: 'application/json, text/plain, */*',
          ...(options.headers || {}),
        },
      });
      clearTimeout(timer);

      const contentType = response.headers.get('content-type') || '';
      let data = null;
      if (contentType.includes('application/json')) {
        data = await response.json();
      } else if (contentType.startsWith('text/')) {
        data = await response.text();
      }

      if (!response.ok) {
        const error = new Error(`Request failed with status ${response.status}`);
        error.response = response;
        error.data = data;
        throw error;
      }

      return { data, response };
    } catch (err) {
      clearTimeout(timer);
      throw err;
    }
  };

  ChronoCam.showAlert = function showAlert(target, { message, type = 'info', dismissMs = 4000 }) {
    if (!target) return null;
    target.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.className = `alert alert-${type} alert-dismissible fade show`;
    wrapper.role = 'alert';
    wrapper.textContent = message;

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'btn-close';
    close.dataset.bsDismiss = 'alert';
    wrapper.appendChild(close);

    target.appendChild(wrapper);

    if (dismissMs) {
      setTimeout(() => wrapper.remove(), dismissMs);
    }
    return wrapper;
  };

  window.ChronoCam = ChronoCam;
})();
