// SeatCute mock "backend" — §6 of _docs/specs.md.
//
// This is the single place that reads/writes localStorage and applies the
// business rules in §4. Every screen (Kiosk, Host, Admin) calls through
// window.SeatCuteAPI instead of touching storage directly, so swapping this
// module for real fetch() calls to a future FastAPI backend should require
// no changes anywhere else.
//
// All functions are async (return Promises) and mirror the endpoint names
// listed in §6, so the call signatures already match what the real backend
// will expose.
window.SeatCuteAPI = (function () {
  const STORAGE_KEYS = {
    config: 'seatcute_config',
    tables: 'seatcute_tables',
    queue: 'seatcute_queue',
    counters: 'seatcute_counters',
  };

  const SIZES = [1, 2, 4, 6];

  const DEFAULT_CONFIG = {
    sizes: SIZES,
    counts: { 1: 2, 2: 4, 4: 3, 6: 1 },
    turnover: { 1: 30, 2: 45, 4: 60, 6: 90 },
  };

  class ApiError extends Error {
    constructor(code, message) {
      super(message);
      this.name = 'ApiError';
      this.code = code;
    }
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function readJSON(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (raw === null) return fallback;
      return JSON.parse(raw);
    } catch {
      return fallback;
    }
  }

  function writeJSON(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function uid(prefix) {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  function delay(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms ?? window.SeatCuteConfig.MOCK_LATENCY_MS));
  }

  function normalizePhone(phone) {
    return String(phone).replace(/\D/g, '');
  }

  function parseLabelIndex(label) {
    const match = /#(\d+)$/.exec(label);
    return match ? Number(match[1]) : 0;
  }

  function makeTable(size, index) {
    return {
      id: `t_${size}_${index}`,
      size,
      label: `${size}-Seat #${index}`,
      status: 'available',
      occupiedAt: null,
      party: null,
      pendingRemoval: false,
    };
  }

  // ---- one-time / lazy initialization ---------------------------------

  function ensureInitialized() {
    let config = readJSON(STORAGE_KEYS.config, null);
    if (!config) {
      config = clone(DEFAULT_CONFIG);
      writeJSON(STORAGE_KEYS.config, config);
    }

    let tables = readJSON(STORAGE_KEYS.tables, null);
    let counters = readJSON(STORAGE_KEYS.counters, null);

    if (!tables) {
      tables = [];
      counters = {};
      for (const size of SIZES) {
        counters[size] = 1;
        for (let i = 0; i < config.counts[size]; i++) {
          tables.push(makeTable(size, counters[size]++));
        }
      }
      writeJSON(STORAGE_KEYS.tables, tables);
      writeJSON(STORAGE_KEYS.counters, counters);
    } else if (!counters) {
      counters = {};
      for (const size of SIZES) {
        const maxIdx = tables
          .filter((t) => t.size === size)
          .reduce((m, t) => Math.max(m, parseLabelIndex(t.label)), 0);
        counters[size] = maxIdx + 1;
      }
      writeJSON(STORAGE_KEYS.counters, counters);
    }

    if (!readJSON(STORAGE_KEYS.queue, null)) {
      writeJSON(STORAGE_KEYS.queue, []);
    }
  }

  // ---- §4 core business logic ------------------------------------------

  function mapPartySizeToQueueSize(partySize) {
    const fits = SIZES.filter((s) => s >= partySize);
    return fits.length ? Math.min(...fits) : null;
  }

  // Free-times for every long-lived table of a size (pendingRemoval tables
  // are excluded entirely — they'll never seat anyone again).
  function freeTimesForSize(size, tables, config) {
    const turnoverMs = config.turnover[size] * 60000;
    const now = Date.now();
    return tables
      .filter((t) => t.size === size && !t.pendingRemoval)
      .map((t) => (t.status === 'available' ? now : t.occupiedAt + turnoverMs))
      .sort((a, b) => a - b);
  }

  function isImmediateSeatAvailable(size, tables, queue) {
    const hasAvailable = tables.some((t) => t.size === size && t.status === 'available');
    const queueEmpty = queue.filter((q) => q.queueSize === size).length === 0;
    return hasAvailable && queueEmpty;
  }

  function applyTableCountChange(tables, counters, size, targetCount) {
    const current = tables.filter((t) => t.size === size);
    const currentCount = current.length;

    if (targetCount > currentCount) {
      let remaining = targetCount - currentCount;

      const pending = current
        .filter((t) => t.pendingRemoval)
        .sort((a, b) => parseLabelIndex(a.label) - parseLabelIndex(b.label));
      for (const t of pending) {
        if (remaining <= 0) break;
        t.pendingRemoval = false;
        remaining--;
      }

      for (let i = 0; i < remaining; i++) {
        const idx = counters[size]++;
        tables.push(makeTable(size, idx));
      }
    } else if (targetCount < currentCount) {
      let deficit = currentCount - targetCount;

      const availableSorted = tables
        .filter((t) => t.size === size && t.status === 'available')
        .sort((a, b) => parseLabelIndex(b.label) - parseLabelIndex(a.label));
      for (const t of availableSorted) {
        if (deficit <= 0) break;
        const idx = tables.indexOf(t);
        tables.splice(idx, 1);
        deficit--;
      }

      if (deficit > 0) {
        const occupiedSorted = tables
          .filter((t) => t.size === size && t.status === 'occupied' && !t.pendingRemoval)
          .sort((a, b) => parseLabelIndex(b.label) - parseLabelIndex(a.label));
        for (const t of occupiedSorted) {
          if (deficit <= 0) break;
          t.pendingRemoval = true;
          deficit--;
        }
      }
    }
  }

  // ---- public API (names/signatures mirror the future FastAPI routes) --

  async function getConfig() {
    await delay();
    ensureInitialized();
    return clone(readJSON(STORAGE_KEYS.config, DEFAULT_CONFIG));
  }

  async function saveConfig(newConfig) {
    await delay();
    ensureInitialized();
    const config = readJSON(STORAGE_KEYS.config, DEFAULT_CONFIG);
    const tables = readJSON(STORAGE_KEYS.tables, []);
    const counters = readJSON(STORAGE_KEYS.counters, {});

    for (const size of SIZES) {
      const targetCount = Math.max(0, Math.floor(Number(newConfig.counts[size])));
      applyTableCountChange(tables, counters, size, targetCount);
      config.counts[size] = targetCount;
      config.turnover[size] = Math.max(1, Math.floor(Number(newConfig.turnover[size])));
    }

    writeJSON(STORAGE_KEYS.config, config);
    writeJSON(STORAGE_KEYS.tables, tables);
    writeJSON(STORAGE_KEYS.counters, counters);
    return clone(config);
  }

  async function listTables() {
    await delay();
    ensureInitialized();
    const config = readJSON(STORAGE_KEYS.config, DEFAULT_CONFIG);
    const tables = readJSON(STORAGE_KEYS.tables, []);
    const now = Date.now();

    return tables
      .slice()
      .sort((a, b) => a.size - b.size || parseLabelIndex(a.label) - parseLabelIndex(b.label))
      .map((t) => {
        const turnoverMs = config.turnover[t.size] * 60000;
        const freeAt = t.status === 'occupied' ? t.occupiedAt + turnoverMs : now;
        const elapsedMinutes = t.status === 'occupied' ? Math.floor((now - t.occupiedAt) / 60000) : null;
        return { ...t, elapsedMinutes, freeAt };
      });
  }

  // listQueue(size) for one size's queue, or listQueue() for every size.
  async function listQueue(size) {
    await delay();
    ensureInitialized();
    const config = readJSON(STORAGE_KEYS.config, DEFAULT_CONFIG);
    const tables = readJSON(STORAGE_KEYS.tables, []);
    const queue = readJSON(STORAGE_KEYS.queue, []);
    const now = Date.now();

    const sizes = size ? [size] : SIZES;
    const freeTimesBySize = {};
    for (const s of sizes) freeTimesBySize[s] = freeTimesForSize(s, tables, config);

    const filtered = (size ? queue.filter((q) => q.queueSize === size) : queue.slice()).sort(
      (a, b) => a.joinedAt - b.joinedAt
    );

    const positionCounters = {};
    return filtered.map((q) => {
      positionCounters[q.queueSize] = (positionCounters[q.queueSize] || 0) + 1;
      const position = positionCounters[q.queueSize];
      const freeTimes = freeTimesBySize[q.queueSize] || freeTimesForSize(q.queueSize, tables, config);
      const projectedAt = freeTimes.length >= position ? freeTimes[position - 1] : null;
      const waitMs = projectedAt !== null ? Math.max(0, projectedAt - now) : null;
      return {
        ...q,
        position,
        projectedAt: projectedAt !== null ? Math.max(now, projectedAt) : null,
        projectedWaitMs: waitMs,
      };
    });
  }

  // Kiosk decision helper for US-K1: maps a party size to its queue size and
  // reports whether it can be seated immediately with no queue entry (§4).
  async function checkImmediateSeat(partySize) {
    await delay();
    ensureInitialized();
    const queueSize = mapPartySizeToQueueSize(partySize);
    if (queueSize === null) return { queueSize: null, immediate: false };
    const tables = readJSON(STORAGE_KEYS.tables, []);
    const queue = readJSON(STORAGE_KEYS.queue, []);
    return { queueSize, immediate: isImmediateSeatAvailable(queueSize, tables, queue) };
  }

  async function findActiveQueueEntryByPhone(phone) {
    await delay();
    ensureInitialized();
    const queue = readJSON(STORAGE_KEYS.queue, []);
    const target = normalizePhone(phone);
    const entry = queue.find((q) => normalizePhone(q.phone) === target);
    return entry ? clone(entry) : null;
  }

  async function joinQueue({ name, phone, partySize }) {
    await delay();
    ensureInitialized();

    const queueSize = mapPartySizeToQueueSize(partySize);
    if (queueSize === null) {
      throw new ApiError('PARTY_TOO_LARGE', 'Party size exceeds the largest table.');
    }

    const queue = readJSON(STORAGE_KEYS.queue, []);
    const target = normalizePhone(phone);
    if (queue.some((q) => normalizePhone(q.phone) === target)) {
      throw new ApiError('DUPLICATE_PHONE', 'This phone number already has an active reservation.');
    }

    const entry = {
      id: uid('q'),
      name: String(name).trim(),
      phone: String(phone).trim(),
      partySize: Number(partySize),
      queueSize,
      joinedAt: Date.now(),
    };
    queue.push(entry);
    writeJSON(STORAGE_KEYS.queue, queue);
    return clone(entry);
  }

  async function cancelQueueEntry(id) {
    await delay();
    ensureInitialized();
    const queue = readJSON(STORAGE_KEYS.queue, []);
    writeJSON(STORAGE_KEYS.queue, queue.filter((q) => q.id !== id));
    return true;
  }

  async function dismissQueueEntry(id) {
    // Same effect as cancelQueueEntry, kept as a distinct endpoint since it's
    // a separate Host action (no-show) rather than a customer action.
    await delay();
    ensureInitialized();
    const queue = readJSON(STORAGE_KEYS.queue, []);
    writeJSON(STORAGE_KEYS.queue, queue.filter((q) => q.id !== id));
    return true;
  }

  async function seatFromQueue({ tableId, queueEntryId }) {
    await delay();
    ensureInitialized();
    const tables = readJSON(STORAGE_KEYS.tables, []);
    const queue = readJSON(STORAGE_KEYS.queue, []);

    const table = tables.find((t) => t.id === tableId);
    if (!table) throw new ApiError('NOT_FOUND', 'Table not found.');
    if (table.status !== 'available') throw new ApiError('TABLE_UNAVAILABLE', 'Table is not available.');

    const entryIdx = queue.findIndex((q) => q.id === queueEntryId);
    if (entryIdx === -1) throw new ApiError('NOT_FOUND', 'Queue entry not found.');

    const [entry] = queue.splice(entryIdx, 1);
    table.status = 'occupied';
    table.occupiedAt = Date.now();
    table.party = { name: entry.name, phone: entry.phone };

    writeJSON(STORAGE_KEYS.tables, tables);
    writeJSON(STORAGE_KEYS.queue, queue);
    return clone(table);
  }

  async function seatBypass({ tableId }) {
    await delay();
    ensureInitialized();
    const tables = readJSON(STORAGE_KEYS.tables, []);

    const table = tables.find((t) => t.id === tableId);
    if (!table) throw new ApiError('NOT_FOUND', 'Table not found.');
    if (table.status !== 'available') throw new ApiError('TABLE_UNAVAILABLE', 'Table is not available.');

    table.status = 'occupied';
    table.occupiedAt = Date.now();
    table.party = null;

    writeJSON(STORAGE_KEYS.tables, tables);
    return clone(table);
  }

  async function releaseTable(tableId) {
    await delay();
    ensureInitialized();
    let tables = readJSON(STORAGE_KEYS.tables, []);

    const table = tables.find((t) => t.id === tableId);
    if (!table) throw new ApiError('NOT_FOUND', 'Table not found.');

    if (table.pendingRemoval) {
      tables = tables.filter((t) => t.id !== tableId);
    } else {
      table.status = 'available';
      table.occupiedAt = null;
      table.party = null;
    }

    writeJSON(STORAGE_KEYS.tables, tables);
    return true;
  }

  return {
    SIZES,
    ApiError,
    getConfig,
    saveConfig,
    listTables,
    listQueue,
    checkImmediateSeat,
    findActiveQueueEntryByPhone,
    joinQueue,
    cancelQueueEntry,
    dismissQueueEntry,
    seatFromQueue,
    seatBypass,
    releaseTable,
  };
})();
