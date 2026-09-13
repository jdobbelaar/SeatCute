// Shared display-formatting helpers used by both the Kiosk and Host/Admin pages.
window.SeatCuteFormat = (function () {
  function clockTime(timestampMs) {
    return new Date(timestampMs).toLocaleTimeString([], {
      hour: 'numeric',
      minute: '2-digit',
    });
  }

  function minutes(ms) {
    return Math.max(0, Math.round(ms / 60000));
  }

  function durationWords(ms) {
    const total = minutes(ms);
    if (total <= 0) return 'less than a minute';
    if (total === 1) return '1 minute';
    return `${total} minutes`;
  }

  function phoneDisplay(phone) {
    const digits = String(phone).replace(/\D/g, '');
    if (digits.length === 10) {
      return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
    }
    return phone;
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  return { clockTime, minutes, durationWords, phoneDisplay, escapeHtml };
})();
