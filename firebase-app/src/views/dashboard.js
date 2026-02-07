import { signOut } from 'firebase/auth';
import { collection, query, where, orderBy, getDocs } from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { getUserProfile, getRole, navigateTo } from '../app.js';

export function renderDashboard() {
  const el = document.createElement('div');
  el.className = 'view view-dashboard';

  const profile = getUserProfile();
  const name = profile?.displayName || auth.currentUser?.email || 'Používateľ';
  const role = getRole();

  el.innerHTML = `
    <header class="app-header">
      <h1>🥊 Môj prehľad</h1>
      <p class="user-name">${escapeHtml(name)}</p>
      <nav class="nav-tabs">
        <a href="#/" class="nav-tab active">Štatistiky</a>
        <a href="#/checkin" class="nav-tab">Prihlásiť na tréning</a>
        <a href="#/qr" class="nav-tab">QR kód</a>
        ${role === 'trainer' || role === 'admin' ? '<a href="#/trainer" class="nav-tab">Tréner</a>' : ''}
        ${role === 'admin' ? '<a href="#/admin" class="nav-tab">Admin</a>' : ''}
        <button type="button" class="nav-tab btn-logout" id="btn-logout">Odhlásiť</button>
      </nav>
    </header>
    <main class="dashboard-main">
      <section class="stats-card">
        <h2>Moja štatistika</h2>
        <p id="stats-loading">Načítavam…</p>
        <div id="stats-content" class="stats-content" hidden></div>
      </section>
    </main>
  `;

  el.querySelector('#btn-logout').addEventListener('click', () => {
    signOut(auth);
    navigateTo('/');
  });

  loadUserStats(el);

  return el;
}

async function loadUserStats(container) {
  const loading = container.querySelector('#stats-loading');
  const content = container.querySelector('#stats-content');
  const uid = auth.currentUser?.uid;
  if (!uid) return;

  try {
    const q = query(
      collection(db, 'attendance'),
      where('userId', '==', uid),
      orderBy('timestamp', 'desc')
    );
    const snap = await getDocs(q);
    const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));

    const byMonth = {};
    const byTraining = {};
    list.forEach(({ trainingType, trainingName, timestamp }) => {
      const t = timestamp?.toDate ? timestamp.toDate() : new Date(timestamp);
      const monthKey = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}`;
      byMonth[monthKey] = (byMonth[monthKey] || 0) + 1;
      const key = trainingName || trainingType || 'Tréning';
      byTraining[key] = (byTraining[key] || 0) + 1;
    });

    const total = list.length;
    const thisMonth = new Date().toISOString().slice(0, 7);
    const thisMonthCount = byMonth[thisMonth] || 0;

    content.innerHTML = `
      <div class="stat-row">
        <span>Celkom tréningov</span>
        <strong>${total}</strong>
      </div>
      <div class="stat-row">
        <span>Tento mesiac</span>
        <strong>${thisMonthCount}</strong>
      </div>
      <div class="stat-list">
        <h3>Podľa typu</h3>
        ${Object.entries(byTraining).length ? Object.entries(byTraining)
          .sort((a, b) => b[1] - a[1])
          .map(([name, count]) => `<div class="stat-row"><span>${escapeHtml(name)}</span><strong>${count}</strong></div>`)
          .join('') : '<p>Zatiaľ žiadne záznamy.</p>'}
      </div>
    `;
    content.hidden = false;
    loading.hidden = true;
  } catch (e) {
    loading.textContent = 'Nepodarilo sa načítať štatistiky.';
    console.error(e);
  }
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
