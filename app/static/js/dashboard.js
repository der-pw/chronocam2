// app/static/js/dashboard.js
// Dashboard interactions: SSE with reconnect, status polling and AJAX actions
(function () {
  const root = document.getElementById('dashboard-app');
  if (!root) return;

  const { fetchJson } = window.ChronoCam || {};
  if (!fetchJson) {
    console.warn('ChronoCam helpers not loaded');
    return;
  }

  const qs = (id) => document.getElementById(id);
  const els = {
    latestImg: qs('latest-img'),
    lastTime: qs('last-time'),
    camErr: qs('cam-error'),
    statusText: qs('status-text'),
    time: qs('time'),
    sunrise: qs('sunrise'),
    sunset: qs('sunset'),
    count: qs('count'),
  };

  const messages = {
    lastLabel: root.dataset.lastLabel || 'Last image',
    cameraErrorPrefix: root.dataset.cameraErrorPrefix || 'Camera error',
    cameraErrorSnapshot: root.dataset.cameraErrorSnapshot || 'Snapshot failed',
    statusPaused: root.dataset.statusPaused || 'Recording paused',
    statusRunning: root.dataset.statusRunning || 'Recording running',
    statusWaiting: root.dataset.statusWaiting || 'Waiting for active time window',
    statusConfigReloaded: root.dataset.statusConfigReloaded || 'Configuration reloaded',
    statusCameraError: root.dataset.statusCameraError || 'Camera access error',
    statusLastSuccess: root.dataset.statusLastSuccess || 'Last image captured successfully',
    statusReconnecting: root.dataset.statusReconnecting || 'Reconnecting to live updates …',
    statusFailed: root.dataset.statusFailed || 'Status konnte nicht geladen werden',
    actionError: root.dataset.actionError || 'Action failed',
    actionSuccess: root.dataset.actionSuccess || 'Action completed',
  };

  const EMPTY_TIME = '--:--:--';
  let imageCount = 0;
  let lastSnapshot = null;
  let statusRevertTimer = null;
  let es = null;
  let esRetryDelay = 2000;

  const bust = (u) => `${u}${u.includes('?') ? '&' : '?'}t=${Date.now()}`;

  const formatTimestampTooltip = (value) => {
    if (!value) return '';
    // Accept preformatted DD.MM.YY HH:MM (or similar) as-is.
    if (/^\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}/.test(value)) return value;

    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return value; // Fallback: show raw value
    }

    return parsed.toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const updateLastTime = (timestamp, tooltipValue) => {
    if (!els.lastTime) return;
    els.lastTime.textContent = `${messages.lastLabel}: ${timestamp || EMPTY_TIME}`;
    els.lastTime.style.display = '';
    const tooltip = formatTimestampTooltip(tooltipValue || timestamp);
    if (tooltip) {
      els.lastTime.setAttribute('title', tooltip);
      els.lastTime.setAttribute('data-bs-toggle', 'tooltip');
      els.lastTime.setAttribute('data-bs-placement', 'top');
      if (window.bootstrap && window.bootstrap.Tooltip) {
        window.bootstrap.Tooltip.getOrCreateInstance(els.lastTime, {
          title: tooltip
        });
      }
    } else {
      els.lastTime.removeAttribute('title');
      els.lastTime.removeAttribute('data-bs-toggle');
      els.lastTime.removeAttribute('data-bs-placement');
    }
  };

  function setStatus(message, revertMs) {
    if (!els.statusText) return;
    els.statusText.textContent = message || '';
    if (statusRevertTimer) {
      clearTimeout(statusRevertTimer);
      statusRevertTimer = null;
    }
    if (revertMs) {
      statusRevertTimer = setTimeout(() => {
        fetchStatus();
      }, revertMs);
    }
  }

  function updateCameraError(errorInfo) {
    if (!els.camErr) return;
    if (errorInfo) {
      const detail = (errorInfo.code === 'snapshot_failed' && messages.cameraErrorSnapshot) || errorInfo.message || '';
      const suffix = detail ? `: ${detail}` : '';
      els.camErr.textContent = `${messages.cameraErrorPrefix}${suffix}`;
      els.camErr.style.display = 'block';
    } else {
      els.camErr.textContent = '';
      els.camErr.style.display = 'none';
    }
  }

  function refreshImage() {
    if (!els.latestImg) return;
    els.latestImg.src = bust('/static/img/last.jpg');
    els.latestImg.style.display = '';
  }

  async function fetchStatus({ syncImage = false } = {}) {
    try {
      const { data } = await fetchJson('/status');
      if (!data) throw new Error('Missing status payload');

      if (typeof data.count === 'number') {
        imageCount = data.count;
        if (els.count) els.count.textContent = imageCount;
      }

      const newSnapshot = data.last_snapshot || null;
      const newSnapshotTooltip = data.last_snapshot_tooltip || newSnapshot;
      const snapshotChanged = newSnapshot && newSnapshot !== lastSnapshot;
      lastSnapshot = newSnapshot;

      updateLastTime(newSnapshot, newSnapshotTooltip);

      if (syncImage && snapshotChanged) {
        refreshImage();
      }

      if (els.sunrise) els.sunrise.textContent = data.sunrise || '--:--';
      if (els.sunset) els.sunset.textContent = data.sunset || '--:--';

      if (data.paused === true) {
        setStatus(messages.statusPaused);
      } else if (data.active === true) {
        setStatus(messages.statusRunning);
      } else {
        setStatus(messages.statusWaiting);
      }

      updateCameraError(data.camera_error || null);
    } catch (err) {
      console.warn('Status konnte nicht geladen werden', err);
      setStatus(messages.statusFailed);
    }
  }

  function handleSnapshotUpdate(timestamp, fullTimestamp) {
    imageCount += 1;
    if (els.count) els.count.textContent = imageCount;
    if (timestamp) lastSnapshot = timestamp;
    refreshImage();
    updateLastTime(timestamp, fullTimestamp);
    updateCameraError(null);
    setStatus(messages.statusLastSuccess, 5000);
  }

  function handleStatusUpdate(status) {
    if (!status) return;
    let revert = false;
    if (status === 'paused') {
      setStatus(messages.statusPaused);
    } else if (status === 'running') {
      setStatus(messages.statusRunning);
    } else if (status === 'waiting_window') {
      setStatus(messages.statusWaiting);
    } else if (status === 'config_reloaded') {
      setStatus(messages.statusConfigReloaded);
      revert = true;
    }

    if (revert) {
      statusRevertTimer = setTimeout(() => fetchStatus(), 5000);
    }
  }

  function connectSse() {
    if (es) {
      es.close();
      es = null;
    }

    es = new EventSource('/events');
    esRetryDelay = 2000;

    es.onopen = () => {
      esRetryDelay = 2000;
    };

    es.onerror = () => {
      setStatus(messages.statusReconnecting);
      if (es) {
        es.close();
        es = null;
      }
      setTimeout(connectSse, esRetryDelay);
      esRetryDelay = Math.min(esRetryDelay * 1.5, 30000);
    };

    es.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'snapshot' && payload.filename) {
          handleSnapshotUpdate(payload.timestamp, payload.timestamp_full);
        }

        if (payload.type === 'status') {
          handleStatusUpdate(payload.status);
        }

        if (payload.type === 'camera_error') {
          updateCameraError({ code: payload.code, message: payload.message });
          setStatus(messages.statusCameraError, 8000);
        }
      } catch (err) {
        console.warn('SSE parse error', event.data);
      }
    };
  }

  async function sendAction(path) {
    const btn = path === 'pause' ? qs('btn-pause') : path === 'resume' ? qs('btn-resume') : qs('btn-snapshot');
    if (btn) btn.disabled = true;
    try {
      await fetchJson(`/action/${path}`, { method: 'POST' }, { timeoutMs: 15000 });
      setStatus(messages.actionSuccess, 3000);
    } catch (err) {
      console.warn(`Action ${path} failed`, err);
      setStatus(messages.actionError, 4000);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function bindActions() {
    const pause = qs('btn-pause');
    const resume = qs('btn-resume');
    const snapshot = qs('btn-snapshot');
    if (pause) pause.addEventListener('click', () => sendAction('pause'));
    if (resume) resume.addEventListener('click', () => sendAction('resume'));
    if (snapshot) snapshot.addEventListener('click', () => sendAction('snapshot'));
  }

  function startClock() {
    if (!els.time) return;
    const updateClock = () => {
      const now = new Date();
      els.time.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };
    updateClock();
    setInterval(updateClock, 1000);
  }

  startClock();
  fetchStatus();
  connectSse();
  bindActions();
  setInterval(() => fetchStatus({ syncImage: true }), 30000);
})();
