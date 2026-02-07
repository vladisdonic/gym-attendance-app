import { signOut } from 'firebase/auth';
import { collection, getDocs, doc, updateDoc } from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { getUserProfile, navigateTo } from '../app.js';

const ROLES = ['user', 'trainer', 'admin'];

export function renderAdmin() {
  const el = document.createElement('div');
  el.className = 'view view-admin';

  const name = getUserProfile()?.displayName || auth.currentUser?.email || 'Admin';

  el.innerHTML = `
    <header class="app-header">
      <h1>⚙️ Admin</h1>
      <p class="user-name">${escapeHtml(name)}</p>
      <nav class="nav-tabs">
        <a href="#/" class="nav-tab">Prehľad</a>
        <a href="#/trainer" class="nav-tab">Tréner</a>
        <a href="#/admin" class="nav-tab active">Admin</a>
        <button type="button" class="btn-logout" id="btn-logout">Odhlásiť</button>
      </nav>
    </header>
    <main class="admin-main">
      <section class="admin-section">
        <h2>Používatelia a role</h2>
        <p id="admin-loading">Načítavam…</p>
        <div id="admin-users" class="admin-users" hidden></div>
      </section>
    </main>
  `;

  el.querySelector('#btn-logout').addEventListener('click', () => {
    signOut(auth);
    navigateTo('/');
  });

  loadUsers(el);

  return el;
}

async function loadUsers(container) {
  const loading = container.querySelector('#admin-loading');
  const usersEl = container.querySelector('#admin-users');

  try {
    const snap = await getDocs(collection(db, 'profiles'));
    const users = snap.docs.map(d => ({ id: d.id, ...d.data() }));

    usersEl.innerHTML = `
      <table class="users-table">
        <thead>
          <tr><th>Meno</th><th>Email</th><th>Rola</th><th>Akcia</th></tr>
        </thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>${escapeHtml(u.displayName || '—')}</td>
              <td>${escapeHtml(u.email || '—')}</td>
              <td>
                <select class="role-select" data-uid="${escapeHtml(u.id)}">
                  ${ROLES.map(r => `<option value="${r}" ${u.role === r ? 'selected' : ''}>${r}</option>`).join('')}
                </select>
              </td>
              <td><button type="button" class="btn btn-small btn-save-role" data-uid="${escapeHtml(u.id)}">Uložiť</button></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;

    usersEl.querySelectorAll('.btn-save-role').forEach(btn => {
      btn.addEventListener('click', async () => {
        const uid = btn.dataset.uid;
        const row = btn.closest('tr');
        const select = row.querySelector('.role-select');
        const role = select.value;
        try {
          await updateDoc(doc(db, 'profiles', uid), { role });
          btn.textContent = 'Uložené';
          setTimeout(() => { btn.textContent = 'Uložiť'; }, 1500);
        } catch (e) {
          alert('Chyba: ' + e.message);
        }
      });
    });

    usersEl.hidden = false;
    loading.hidden = true;
  } catch (e) {
    loading.textContent = 'Nepodarilo sa načítať používateľov.';
    console.error(e);
  }
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
