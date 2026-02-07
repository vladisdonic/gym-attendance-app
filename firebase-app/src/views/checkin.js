import { signOut } from 'firebase/auth';
import { collection, addDoc } from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { getUserProfile, navigateTo } from '../app.js';
import {
  MEMBERSHIP_TYPES,
  getTrainingTimesForToday,
  getNextTrainingTime
} from '../trainingHelpers.js';

export function renderCheckIn() {
  const el = document.createElement('div');
  el.className = 'view view-checkin';

  const profile = getUserProfile();
  const name = profile?.displayName || auth.currentUser?.email || '';
  const timesToday = getTrainingTimesForToday();
  const nextTime = getNextTrainingTime();
  const hashQuery = (window.location.hash || '').split('?')[1] || '';
  const params = new URLSearchParams(hashQuery);
  const urlName = params.get('name') || '';
  const urlMembership = params.get('membership') || '';
  const urlTime = params.get('time') || '';
  const autoSubmit = params.get('auto') === '1';
  const defaultTime = (urlTime && timesToday.includes(urlTime)) ? urlTime : (timesToday.includes(nextTime) ? nextTime : timesToday[0]);
  let defaultMembershipIndex = MEMBERSHIP_TYPES.indexOf(urlMembership || profile?.membershipType || 'Mesačné členstvo');
  if (defaultMembershipIndex < 0) defaultMembershipIndex = 1;

  el.innerHTML = `
    <header class="app-header">
      <h1>✅ Prihlásenie na tréning</h1>
      <p class="user-name">${escapeHtml(name)}</p>
      <nav class="nav-tabs">
        <a href="#/" class="nav-tab">Prehľad</a>
        <a href="#/checkin" class="nav-tab active">Prihlásiť sa</a>
        <a href="#/qr" class="nav-tab">QR kód</a>
        <button type="button" class="btn-logout" id="btn-logout">Odhlásiť</button>
      </nav>
    </header>
    <main class="checkin-main">
      <p class="nfc-hint">📱 Priložte telefón k NFC tagu alebo vyberte tréning nižšie.</p>
      <form class="checkin-form" id="checkin-form">
        <label for="membership">Typ členstva</label>
        <select id="membership" name="membership" required>
          ${MEMBERSHIP_TYPES.map((t, i) => `<option value="${escapeHtml(t)}" ${i === defaultMembershipIndex ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
        </select>
        <label for="training">Čas tréningu</label>
        <select id="training" name="training" required>
          ${timesToday.map(t => `<option value="${escapeHtml(t)}" ${t === defaultTime ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
        </select>
        <button type="submit" class="btn btn-primary btn-block">Prihlásiť sa na tréning</button>
      </form>
      <p class="checkin-success" id="checkin-success" hidden>✓ Ste prihlásený na tréning.</p>
      <p class="auth-error" id="checkin-error"></p>
    </main>
  `;

  el.querySelector('#btn-logout').addEventListener('click', () => {
    signOut(auth);
    navigateTo('/');
  });

  const form = el.querySelector('#checkin-form');
  const successEl = el.querySelector('#checkin-success');
  const errorEl = el.querySelector('#checkin-error');

  if (autoSubmit && urlName && urlMembership && MEMBERSHIP_TYPES.includes(urlMembership) && timesToday.includes(defaultTime)) {
    setTimeout(() => form.requestSubmit(), 500);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    successEl.hidden = true;
    errorEl.textContent = '';
    const membershipSelect = form.querySelector('#membership');
    const trainingSelect = form.querySelector('#training');
    const membershipType = membershipSelect ? membershipSelect.value : '';
    const trainingTime = trainingSelect ? trainingSelect.value : '';
    const uid = auth.currentUser?.uid;
    const email = auth.currentUser?.email;
    if (!uid) {
      errorEl.textContent = 'Nie ste prihlásený. Obnovte stránku alebo sa znova prihláste.';
      return;
    }
    if (!membershipType || !trainingTime) {
      errorEl.textContent = 'Vyberte typ členstva a čas tréningu.';
      return;
    }
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Ukladám…';
    try {
      await addDoc(collection(db, 'attendance'), {
        userId: uid,
        email: email || '',
        displayName: profile?.displayName || '',
        membershipType,
        trainingType: trainingTime,
        trainingName: trainingTime,
        timestamp: new Date()
      });
      successEl.hidden = false;
      successEl.textContent = '✓ Ste prihlásený na tréning.';
      const next = getNextTrainingTime();
      const times = getTrainingTimesForToday();
      if (trainingSelect) trainingSelect.value = times.includes(next) ? next : times[0];
    } catch (err) {
      const msg = err.code === 'permission-denied'
        ? 'Nemáte oprávnenie zapisovať dochádzku. Skontrolujte Firestore pravidlá.'
        : (err.message || 'Zápis zlyhal.');
      errorEl.textContent = msg;
      console.error('Check-in error:', err);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Prihlásiť sa na tréning';
    }
  });

  return el;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
