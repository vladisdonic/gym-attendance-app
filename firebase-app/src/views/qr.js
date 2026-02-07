import { signOut } from 'firebase/auth';
import { auth } from '../firebase.js';
import { getUserProfile, navigateTo } from '../app.js';
import { MEMBERSHIP_TYPES, getTrainingTimesForToday, getNextTrainingTime } from '../trainingHelpers.js';

export function renderQr() {
  const el = document.createElement('div');
  el.className = 'view view-qr';

  const profile = getUserProfile();
  const name = profile?.displayName || auth.currentUser?.email || '';
  const timesToday = getTrainingTimesForToday();
  const nextTime = getNextTrainingTime();
  const defaultTimeIndex = timesToday.indexOf(nextTime) >= 0 ? timesToday.indexOf(nextTime) : 0;

  el.innerHTML = `
    <header class="app-header">
      <h1>🖼️ Generovať QR kód</h1>
      <p class="user-name">${escapeHtml(name)}</p>
      <nav class="nav-tabs">
        <a href="#/" class="nav-tab">Prehľad</a>
        <a href="#/checkin" class="nav-tab">Prihlásiť sa</a>
        <a href="#/qr" class="nav-tab active">QR kód</a>
        <button type="button" class="btn-logout" id="btn-logout">Odhlásiť</button>
      </nav>
    </header>
    <main class="qr-main">
      <p class="qr-desc">Vygeneruj QR kód s odkazom na prihlásenie na tréning. Naskenovaním sa otvorí aplikácia s vyplnenými údajmi.</p>
      <form class="qr-form" id="qr-form">
        <label for="qr-name">Meno a priezvisko</label>
        <input type="text" id="qr-name" name="name" value="${escapeHtml(name)}" placeholder="Ján Novák" required />
        <label for="qr-membership">Typ členstva</label>
        <select id="qr-membership" name="membership" required>
          ${MEMBERSHIP_TYPES.map(t => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`).join('')}
        </select>
        <label for="qr-time">Čas tréningu (predvolený pri naskenovaní)</label>
        <select id="qr-time" name="time">
          ${timesToday.map((t, i) => `<option value="${escapeHtml(t)}" ${i === defaultTimeIndex ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
        </select>
        <label class="qr-checkbox">
          <input type="checkbox" id="qr-auto" name="auto" checked /> Automatické odoslanie pri otvorení (odporúčané)
        </label>
        <button type="submit" class="btn btn-primary btn-block">🖼️ Generovať QR kód</button>
      </form>
      <div class="qr-result" id="qr-result" hidden>
        <h3>✅ QR kód pripravený</h3>
        <div class="qr-image-wrap"><img id="qr-image" alt="QR kód" /></div>
        <p class="qr-url" id="qr-url"></p>
        <a id="qr-download" class="btn btn-primary" download="giantgym_qr.png">📥 Stiahnuť QR kód (.png)</a>
      </div>
    </main>
  `;

  el.querySelector('#btn-logout').addEventListener('click', () => {
    signOut(auth);
    navigateTo('/');
  });

  const form = el.querySelector('#qr-form');
  const resultEl = el.querySelector('#qr-result');
  const imgEl = el.querySelector('#qr-image');
  const urlEl = el.querySelector('#qr-url');
  const downloadEl = el.querySelector('#qr-download');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const nameVal = form.name.value.trim();
    const membership = form.membership.value;
    const time = form.time.value;
    const auto = form.auto.checked;
    const baseUrl = window.location.origin + window.location.pathname + '#/checkin';
    const params = new URLSearchParams();
    params.set('name', nameVal);
    params.set('membership', membership);
    params.set('time', time);
    if (auto) params.set('auto', '1');
    const url = `${baseUrl}?${params.toString()}`;

    try {
      const QRCode = (await import('qrcode')).default;
      const dataUrl = await QRCode.toDataURL(url, { width: 400, margin: 2 });
      imgEl.src = dataUrl;
      urlEl.textContent = url;
      downloadEl.href = dataUrl;
      downloadEl.download = `giantgym_${nameVal.replace(/\s+/g, '_')}.png`;
      resultEl.hidden = false;
    } catch (err) {
      console.error(err);
      urlEl.textContent = 'Chyba pri generovaní: ' + err.message;
      resultEl.hidden = false;
    }
  });

  return el;
}

function escapeHtml(s) {
  if (s == null) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
