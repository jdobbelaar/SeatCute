// Shared timing constants (all easy to tweak, per spec §2.14).
window.SeatCuteConfig = {
  // Base URL of the FastAPI backend (see backend/, openapi.yaml). Change
  // this if the backend runs somewhere other than the default `uv run
  // uvicorn seatcute_backend.main:app` address.
  API_BASE_URL: "http://localhost:8000",
  // How long transient kiosk messages stay on screen before returning to Welcome.
  MESSAGE_DEFAULT_MS: 5000,
  // "Your wait is..." confirmation screen after joining the queue (US-K2).
  WAIT_CONFIRM_MS: 10000,
  // Wait-time preview (Reserve My Spot / Cancel) shown before name/phone.
  WAIT_PREVIEW_TIMEOUT_MS: 15000,
  // Reservation Status screen auto-returns to Welcome if untouched (US-K3).
  RESERVATION_STATUS_TIMEOUT_MS: 15000,
  // "Thank You" screen after Keep My Reservation (US-K3).
  THANK_YOU_MS: 2000,
  // Host/Admin dashboard periodic re-render, so elapsed/free times stay fresh.
  HOST_REFRESH_INTERVAL_MS: 20000,
};
