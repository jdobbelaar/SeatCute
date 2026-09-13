// SeatCute backend client — §6/§8 of _docs/specs.md.
//
// Talks to the FastAPI backend in backend/ (see openapi.yaml at the repo
// root for the full contract) over fetch(). This is the single place that
// makes network calls; every screen (Kiosk, Host, Admin) calls through
// window.SeatCuteAPI with the same function names/signatures this module
// had back when it was mockApi.js backed by localStorage, so no other
// frontend file needed to change when this swapped from mock to real HTTP.
window.SeatCuteAPI = (function () {
  class ApiError extends Error {
    constructor(code, message) {
      super(message);
      this.name = 'ApiError';
      this.code = code;
    }
  }

  function baseUrl() {
    return window.SeatCuteConfig.API_BASE_URL;
  }

  function toQueryString(params) {
    const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null);
    if (entries.length === 0) return '';
    return '?' + entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
  }

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(`${baseUrl()}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
      });
    } catch (err) {
      throw new ApiError('NETWORK_ERROR', 'Could not reach the server. Is the backend running?');
    }

    if (response.status === 204) return null;

    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }

    if (!response.ok) {
      throw new ApiError(
        (body && body.code) || 'UNKNOWN_ERROR',
        (body && body.message) || `Request failed with status ${response.status}.`
      );
    }
    return body;
  }

  // 404 on cancel/dismiss means "already gone" -- treat as success so
  // double-clicks or stale ids behave the same as the old idempotent mock.
  async function deleteIgnoringNotFound(path, options) {
    try {
      await request(path, options);
    } catch (err) {
      if (!(err instanceof ApiError) || err.code !== 'NOT_FOUND') throw err;
    }
    return true;
  }

  async function getConfig() {
    return request('/config');
  }

  async function saveConfig(config) {
    return request('/config', { method: 'PUT', body: JSON.stringify(config) });
  }

  async function listTables() {
    return request('/tables');
  }

  // listQueue(size) for one size's queue, or listQueue() for every size.
  async function listQueue(size) {
    return request(`/queue${toQueryString({ size })}`);
  }

  async function getWaitEstimate(partySize) {
    return request(`/queue/wait-estimate${toQueryString({ partySize })}`);
  }

  async function findActiveQueueEntryByPhone(phone) {
    try {
      return await request(`/reservation-status${toQueryString({ phone })}`);
    } catch (err) {
      if (err instanceof ApiError && err.code === 'NOT_FOUND') return null;
      throw err;
    }
  }

  async function joinQueue({ name, phone, partySize }) {
    return request('/queue', {
      method: 'POST',
      body: JSON.stringify({ name, phone, partySize }),
    });
  }

  async function cancelQueueEntry(id) {
    return deleteIgnoringNotFound(`/queue/${encodeURIComponent(id)}`, { method: 'DELETE' });
  }

  async function dismissQueueEntry(id) {
    return deleteIgnoringNotFound(`/queue/${encodeURIComponent(id)}/dismiss`, { method: 'POST' });
  }

  async function seatFromQueue({ tableId, queueEntryId }) {
    return request(`/tables/${encodeURIComponent(tableId)}/seat-from-queue`, {
      method: 'POST',
      body: JSON.stringify({ queueEntryId }),
    });
  }

  async function seatBypass({ tableId }) {
    return request(`/tables/${encodeURIComponent(tableId)}/seat-bypass`, { method: 'POST' });
  }

  async function releaseTable(tableId) {
    await request(`/tables/${encodeURIComponent(tableId)}/release`, { method: 'POST' });
    return true;
  }

  return {
    SIZES: [1, 2, 4, 6],
    ApiError,
    getConfig,
    saveConfig,
    listTables,
    listQueue,
    getWaitEstimate,
    findActiveQueueEntryByPhone,
    joinQueue,
    cancelQueueEntry,
    dismissQueueEntry,
    seatFromQueue,
    seatBypass,
    releaseTable,
  };
})();
