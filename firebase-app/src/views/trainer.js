import { signOut } from 'firebase/auth';
import {
  collection,
  query,
  orderBy,
  limit,
  getDocs,
  addDoc,
  doc,
  deleteDoc,
  getDoc
} from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { getUserProfile, getRole, navigateTo } from '../app.js';
import {
  MEMBERSHIP_TYPES,
  getTrainingTimesForManualForm,
  getNextTrainingTime
} from '../trainingHelpers.js';

export function renderTrainer() {
  const el = document.createElement('div');
  el.className = 'view view-trainer';

  const name = getUserProfile()?.displayName || auth.currentUser?.email || 'Tréner';
  const manualTimes = getTrainingTimesForManualForm();
  const nextT = getNextTrainingTime();
  const defaultTimeIndex = manualTimes.indexOf(nextT) >= 0 ? manualTimes.indexOf(nextT) : 0;

  el.innerHTML = `
    <header class="app-header">
      <h1>📋 Prehľad trénera</h1>
      <p class="user-name">${escapeHtml(name)}</p>
      <nav class="nav-tabs">
        <a href="#/" class="nav-tab">Prehľad</a>
        <a href="#/checkin" class="nav-tab">Prihlásiť sa</a>
        <a href="#/qr" class="nav-tab">QR kód</a>
        <a href="#/trainer" class="nav-tab active">Tréner</a>
        ${getRole() === 'admin' ? '<a href="#/admin" class="nav-tab">Admin</a>' : ''}
        <button type="button" class="btn-logout" id="btn-logout">Odhlásiť</button>
      </nav>
    </header>
    <main class="trainer-main">
      <section class="trainer-stats">
        <h2>Dnešné prihlásenia</h2>
        <p id="trainer-loading">Načítavam…</p>
        <div id="trainer-list" class="trainer-list" hidden></div>
      </section>
      <section class="trainer-manual">
        <h2>✍️ Manuálne prihlásenie</h2>
        <p class="trainer-caption">Ak QR skener nefunguje, prihlás člena manuálne.</p>
        <form class="manual-form" id="manual-form">
          <label for="manual-name">Používateľ (alebo meno)</label>
          <input type="text" id="manual-name" name="manualName" placeholder="Meno člena alebo vyber zoznam..." list="user-list" />
          <datalist id="user-list"></datalist>
          <label for="manual-membership">Typ členstva</label>
          <select id="manual-membership" name="manualMembership">
            ${MEMBERSHIP_TYPES.map((t, i) => `<option value="${escapeHtml(t)}" ${i === 1 ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
          </select>
          <label for="manual-time">Čas tréningu</label>
          <select id="manual-time" name="manualTime">
            ${manualTimes.map((t, i) => `<option value="${escapeHtml(t)}" ${i === defaultTimeIndex ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
          </select>
          <label for="manual-note">Poznámka</label>
          <input type="text" id="manual-note" name="manualNote" placeholder="Voliteľná poznámka" />
          <button type="submit" class="btn btn-primary">✅ Prihlásiť člena</button>
          <p class="auth-error" id="manual-error"></p>
          <p class="checkin-success" id="manual-success" hidden>✓ Člen prihlásený.</p>
        </form>
      </section>
    </main>
  `;

  el.querySelector('#btn-logout').addEventListener('click', () => {
    signOut(auth);
    navigateTo('/');
  });

  loadTodayAttendance(el);
  loadUserDatalist(el);
  setupManualForm(el);

  return el;
}

function todayStart() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

async function loadUserDatalist(container) {
  const list = container.querySelector('#user-list');
  try {
    const snap = await getDocs(collection(db, 'profiles'));
    snap.docs.forEach(d => {
      const data = d.data();
      const opt = document.createElement('option');
      opt.value = data.displayName || data.email || d.id;
      list.appendChild(opt);
    });
  } catch (e) {
    console.error(e);
  }
}

async function loadTodayAttendance(container) {
  const loading = container.querySelector('#trainer-loading');
  const listEl = container.querySelector('#trainer-list');
  const start = todayStart();

  try {
    const q = query(
      collection(db, 'attendance'),
      orderBy('timestamp', 'desc'),
      limit(300)
    );
    const snap = await getDocs(q);
    const all = snap.docs.map(d => ({ id: d.id, ...d.data() }));
    const today = all.filter(item => {
      const t = item.timestamp?.toDate ? item.timestamp.toDate() : new Date(item.timestamp);
      return t >= start;
    });

    const manualTimes = getTrainingTimesForManualForm();
    const byTime = {};
    manualTimes.forEach(t => { byTime[t] = []; });
    today.forEach(item => {
      const slot = item.trainingName || item.trainingType || '';
      if (!byTime[slot]) byTime[slot] = [];
      byTime[slot].push(item);
    });

    listEl.innerHTML = `
      <p class="trainer-count">Počet dnes: <strong>${today.length}</strong></p>
      ${manualTimes.map(time => {
        const items = byTime[time] || [];
        return `
          <div class="trainer-group">
            <h3>🕐 ${escapeHtml(time)} – ${items.length} prihlásených</h3>
            <ul class="attendance-list">
              ${items.length ? items.map(item => {
                const t = item.timestamp?.toDate ? item.timestamp.toDate() : new Date(item.timestamp);
                const timeStr = t.toLocaleTimeString('sk-SK', { hour: '2-digit', minute: '2-digit' });
                const membership = item.membershipType || item.membership || '—';
                return `<li>
                  <span class="time">${timeStr}</span>
                  <span class="name">${escapeHtml(item.displayName || item.email || '—')}</span>
                  <span class="membership">${escapeHtml(membership)}</span>
                  <button type="button" class="btn btn-small btn-delete" data-id="${escapeHtml(item.id)}" title="Vymazať">🗑️</button>
                </li>`;
              }).join('') : '<li class="empty">Zatiaľ nikto.</li>'}
            </ul>
          </div>
        `;
      }).join('')}
    `;

    listEl.querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Naozaj vymazať tento záznam?')) return;
        try {
          await deleteDoc(doc(db, 'attendance', btn.dataset.id));
          loadTodayAttendance(container);
        } catch (e) {
          alert('Chyba: ' + e.message);
        }
      });
    });

    listEl.hidden = false;
    loading.hidden = true;
  } catch (e) {
    loading.textContent = 'Nepodarilo sa načítať záznamy.';
    console.error(e);
  }
}

function setupManualForm(container) {
  const form = container.querySelector('#manual-form');
  const errorEl = container.querySelector('#manual-error');
  const successEl = container.querySelector('#manual-success');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    successEl.hidden = true;
    errorEl.textContent = '';
    const nameInput = form.querySelector('#manual-name');
    const membershipSelect = form.querySelector('#manual-membership');
    const timeSelect = form.querySelector('#manual-time');
    const noteInput = form.querySelector('#manual-note');
    const displayName = (nameInput && nameInput.value) ? nameInput.value.trim() : '';
    const membershipType = membershipSelect ? membershipSelect.value : '';
    const trainingTime = timeSelect ? timeSelect.value : '';
    const note = (noteInput && noteInput.value) ? noteInput.value.trim() : '';
    if (!displayName) {
      errorEl.textContent = 'Zadajte meno člena.';
      return;
    }
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Ukladám…';
    try {
      await addDoc(collection(db, 'attendance'), {
        userId: null,
        email: '',
        displayName,
        membershipType,
        trainingType: trainingTime,
        trainingName: trainingTime,
        note,
        manualEntry: true,
        timestamp: new Date()
      });
      successEl.hidden = false;
      if (nameInput) nameInput.value = '';
      if (noteInput) noteInput.value = '';
      btn.textContent = '✅ Prihlásiť člena';
      loadTodayAttendance(container);
    } catch (err) {
      const msg = err.code === 'permission-denied'
        ? 'Nemáte oprávnenie (iba tréner/admin). Skontrolujte rolu vo Firestore.'
        : (err.message || 'Zápis zlyhal.');
      errorEl.textContent = msg;
      console.error('Manual check-in error:', err);
    } finally {
      btn.disabled = false;
      if (btn.textContent === 'Ukladám…') btn.textContent = '✅ Prihlásiť člena';
    }
  });
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
