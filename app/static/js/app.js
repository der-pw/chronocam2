// app/static/js/app.js
// ---------------------------------------
// ChronoCam Frontend Script
// (wird automatisch in base.html geladen)

console.log("ChronoCam app.js geladen");

// Beispiel: automatisch aktualisiere Uhrzeit alle 5s
function updateClock() {
  const el = document.getElementById("clock");
  if (el) {
    const now = new Date();
    el.textContent = now.toLocaleTimeString();
  }
}
setInterval(updateClock, 5000);
updateClock();

// Du kannst hier später auch:
// - SSE-Verbindung zu /events herstellen
// - Statusanzeigen aktualisieren
// - Snapshot-Buttons triggern
// - Toasts oder modale Fenster steuern
