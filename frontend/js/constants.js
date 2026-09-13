// Shared timing constants (all easy to tweak, per spec §2.14).
window.SeatCuteConfig = {
  // How long transient kiosk messages stay on screen before returning to Welcome.
  MESSAGE_DEFAULT_MS: 5000,
  // "Your wait is..." confirmation screen after joining the queue (US-K2).
  WAIT_CONFIRM_MS: 10000,
  // Reservation Status screen auto-returns to Welcome if untouched (US-K3).
  RESERVATION_STATUS_TIMEOUT_MS: 15000,
  // "Thank You" screen after Keep My Reservation (US-K3).
  THANK_YOU_MS: 2000,
  // Host/Admin dashboard periodic re-render, so elapsed/free times stay fresh.
  HOST_REFRESH_INTERVAL_MS: 20000,
  // Simulated network latency for the mock backend, so the UI can later
  // tolerate a real async backend without changes.
  MOCK_LATENCY_MS: 150,
};
