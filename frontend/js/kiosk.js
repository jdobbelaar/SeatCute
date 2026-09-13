(function () {
  const API = window.SeatCuteAPI;
  const FMT = window.SeatCuteFormat;
  const CFG = window.SeatCuteConfig;

  const screens = {
    welcome: document.getElementById('screen-welcome'),
    waitPreview: document.getElementById('screen-wait-preview'),
    namePhone: document.getElementById('screen-name-phone'),
    message: document.getElementById('screen-message'),
    waitConfirm: document.getElementById('screen-wait-confirm'),
    statusPhone: document.getElementById('screen-status-phone'),
    statusResult: document.getElementById('screen-status-result'),
  };

  let pendingPartySize = null;
  let pendingQueueEntryId = null;
  let returnTimer = null;

  function clearReturnTimer() {
    if (returnTimer) {
      clearTimeout(returnTimer);
      returnTimer = null;
    }
  }

  function showScreen(name) {
    clearReturnTimer();
    for (const el of Object.values(screens)) el.classList.remove('active');
    screens[name].classList.add('active');
  }

  function goWelcome() {
    document.getElementById('input-party-size').value = '';
    document.getElementById('welcome-error').textContent = '';
    showScreen('welcome');
  }

  function showMessage(text, ms) {
    document.getElementById('message-text').textContent = text;
    showScreen('message');
    returnTimer = setTimeout(goWelcome, ms ?? CFG.MESSAGE_DEFAULT_MS);
  }

  // ---------------- Welcome: party size (US-K1) ----------------

  const partySizeInput = document.getElementById('input-party-size');
  const welcomeError = document.getElementById('welcome-error');
  const btnGetInLine = document.getElementById('btn-get-in-line');
  const btnReservationStatus = document.getElementById('btn-reservation-status');

  btnGetInLine.addEventListener('click', handlePartySizeSubmit);
  partySizeInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handlePartySizeSubmit();
  });

  async function handlePartySizeSubmit() {
    const raw = partySizeInput.value.trim();
    const partySize = Number(raw);
    if (!raw || !Number.isInteger(partySize) || partySize < 1) {
      welcomeError.textContent = 'Please enter a valid party size.';
      return;
    }
    welcomeError.textContent = '';
    btnGetInLine.disabled = true;

    try {
      const estimate = await API.getWaitEstimate(partySize);
      if (estimate.queueSize === null) {
        showMessage('Please speak with our host directly for large parties.', CFG.MESSAGE_DEFAULT_MS);
        return;
      }
      if (estimate.immediate) {
        showMessage('A table is available — please wait for your host.', CFG.MESSAGE_DEFAULT_MS);
        return;
      }
      pendingPartySize = partySize;
      showWaitPreview(estimate);
    } catch (err) {
      showMessage('Something went wrong. Please see the host for help.', CFG.MESSAGE_DEFAULT_MS);
    } finally {
      btnGetInLine.disabled = false;
    }
  }

  function showWaitPreview(estimate) {
    const big = document.getElementById('preview-wait-big');
    const sub = document.getElementById('preview-wait-sub');
    if (estimate.projectedAt !== null) {
      big.textContent = `~${FMT.durationWords(estimate.projectedWaitMs)}`;
      sub.textContent = `Estimated seating time: ${FMT.clockTime(estimate.projectedAt)}`;
    } else {
      big.textContent = 'Wait time unavailable';
      sub.textContent = 'We\'ll seat you as soon as a table is ready.';
    }
    showScreen('waitPreview');
    returnTimer = setTimeout(goWelcome, CFG.WAIT_PREVIEW_TIMEOUT_MS);
  }

  document.getElementById('btn-cancel-preview').addEventListener('click', goWelcome);
  document.getElementById('btn-reserve-spot').addEventListener('click', () => {
    document.getElementById('input-name').value = '';
    document.getElementById('input-phone').value = '';
    document.getElementById('name-phone-error').textContent = '';
    showScreen('namePhone');
  });

  // ---------------- Name / phone (US-K2) ----------------

  const nameInput = document.getElementById('input-name');
  const phoneInput = document.getElementById('input-phone');
  const namePhoneError = document.getElementById('name-phone-error');
  const btnJoinLine = document.getElementById('btn-join-line');
  const btnNamePhoneBack = document.getElementById('btn-name-phone-back');

  btnNamePhoneBack.addEventListener('click', goWelcome);
  btnJoinLine.addEventListener('click', handleJoinLine);

  async function handleJoinLine() {
    const name = nameInput.value.trim();
    const phone = phoneInput.value.trim();
    if (!name) {
      namePhoneError.textContent = 'Please enter your name.';
      return;
    }
    if (phone.replace(/\D/g, '').length < 7) {
      namePhoneError.textContent = 'Please enter a valid phone number.';
      return;
    }
    namePhoneError.textContent = '';
    btnJoinLine.disabled = true;

    try {
      const entry = await API.joinQueue({ name, phone, partySize: pendingPartySize });
      const queue = await API.listQueue(entry.queueSize);
      const withWait = queue.find((q) => q.id === entry.id);
      showWaitConfirm(withWait);
    } catch (err) {
      if (err && err.code === 'DUPLICATE_PHONE') {
        showMessage('This phone number already has an active reservation.', CFG.MESSAGE_DEFAULT_MS);
      } else {
        showMessage('Something went wrong. Please see the host for help.', CFG.MESSAGE_DEFAULT_MS);
      }
    } finally {
      btnJoinLine.disabled = false;
    }
  }

  function showWaitConfirm(entryWithWait) {
    const big = document.getElementById('wait-big');
    const sub = document.getElementById('wait-sub');
    if (entryWithWait && entryWithWait.projectedAt !== null) {
      big.textContent = `~${FMT.durationWords(entryWithWait.projectedWaitMs)}`;
      sub.textContent = `Estimated seating time: ${FMT.clockTime(entryWithWait.projectedAt)}`;
    } else {
      big.textContent = 'You\'re in line';
      sub.textContent = 'We\'ll seat you as soon as a table is ready.';
    }
    showScreen('waitConfirm');
    returnTimer = setTimeout(goWelcome, CFG.WAIT_CONFIRM_MS);
  }

  // ---------------- Reservation status (US-K3) ----------------

  const statusPhoneInput = document.getElementById('input-status-phone');
  const statusPhoneError = document.getElementById('status-phone-error');
  const btnCheckStatus = document.getElementById('btn-check-status');
  const btnStatusPhoneBack = document.getElementById('btn-status-phone-back');
  const btnKeep = document.getElementById('btn-keep');
  const btnCancelReservation = document.getElementById('btn-cancel-reservation');

  btnReservationStatus.addEventListener('click', () => {
    statusPhoneInput.value = '';
    statusPhoneError.textContent = '';
    showScreen('statusPhone');
  });
  btnStatusPhoneBack.addEventListener('click', goWelcome);
  btnCheckStatus.addEventListener('click', handleCheckStatus);
  statusPhoneInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') handleCheckStatus();
  });

  async function handleCheckStatus() {
    const phone = statusPhoneInput.value.trim();
    if (phone.replace(/\D/g, '').length < 7) {
      statusPhoneError.textContent = 'Please enter a valid phone number.';
      return;
    }
    statusPhoneError.textContent = '';
    btnCheckStatus.disabled = true;

    try {
      const entry = await API.findActiveQueueEntryByPhone(phone);
      if (!entry) {
        showMessage('No reservation found for this number.', CFG.MESSAGE_DEFAULT_MS);
        return;
      }
      const queue = await API.listQueue(entry.queueSize);
      const withWait = queue.find((q) => q.id === entry.id);
      showStatusResult(withWait || entry);
    } catch (err) {
      showMessage('Something went wrong. Please see the host for help.', CFG.MESSAGE_DEFAULT_MS);
    } finally {
      btnCheckStatus.disabled = false;
    }
  }

  function showStatusResult(entryWithWait) {
    pendingQueueEntryId = entryWithWait.id;
    const big = document.getElementById('status-wait-big');
    const sub = document.getElementById('status-wait-sub');
    if (entryWithWait.projectedAt != null) {
      big.textContent = `~${FMT.durationWords(entryWithWait.projectedWaitMs)}`;
      sub.textContent = `Estimated seating time: ${FMT.clockTime(entryWithWait.projectedAt)}`;
    } else {
      big.textContent = '0 minutes';
      sub.textContent = 'Estimated seating time: now';
    }
    showScreen('statusResult');
    returnTimer = setTimeout(goWelcome, CFG.RESERVATION_STATUS_TIMEOUT_MS);
  }

  btnKeep.addEventListener('click', () => {
    showMessage('Thank You', CFG.THANK_YOU_MS);
  });

  btnCancelReservation.addEventListener('click', async () => {
    btnCancelReservation.disabled = true;
    try {
      await API.cancelQueueEntry(pendingQueueEntryId);
      showMessage('Thank you for letting us know. We hope to see you again soon.', CFG.MESSAGE_DEFAULT_MS);
    } finally {
      btnCancelReservation.disabled = false;
    }
  });

  // ---------------- boot ----------------

  goWelcome();
})();
