/**
 * Členská karta pre prihláseného člena: meno, QR, tlačidlo „Prihlásiť na tréning“, odhlásiť, PWA inštalácia.
 */
import { signOut } from 'firebase/auth';
import { auth } from '../firebase.js';
import { getUserProfile, navigateTo } from '../app.js';
import { STREAMLIT_BASE_URL, getNextTrainingTime } from '../trainingHelpers.js';
import { canInstallPwa, triggerPwaInstall } from '../pwaInstall.js';

function escapeHtml(s) {
  if (s == null) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

function isIos() {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

function buildStreamlitUrl(displayName, membershipType) {
  const time = getNextTrainingTime();
  const params = new URLSearchParams({
    view: 'participant',
    name: displayName || '',
    membership: membershipType || 'Mesačné členstvo',
    time,
    auto: '1'
  });
  // Po úspešnom prihlásení na tréning sa používateľ presmeruje späť do PWA
  const returnUrl = typeof window !== 'undefined' ? window.location.origin : '';
  if (returnUrl) params.set('return_url', returnUrl);
  return `${STREAMLIT_BASE_URL}/?${params.toString()}`;
}

export function renderMemberCard() {
  const el = document.createElement('div');
  el.className = 'view view-card view-member-card';

  const profile = getUserProfile();
  const displayName = (profile?.displayName || '').trim() || 'Člen';
  const membershipType = profile?.membershipType || 'Mesačné členstvo';
  const signInUrl = buildStreamlitUrl(displayName, membershipType);

  el.innerHTML = `
    <main class="card-main">
      <h1>🥊 Giant Gym</h1>
      <p class="card-name">${escapeHtml(displayName)}</p>
      ${membershipType ? `<p class="card-membership">${escapeHtml(membershipType)}</p>` : ''}
      <div class="card-qr-wrap" id="member-card-qr-wrap">
        <canvas id="member-card-qr-canvas" aria-hidden="true"></canvas>
      </div>
      <p class="card-hint">Naskenuj QR alebo stlač tlačidlo</p>
      <button type="button" class="btn btn-primary btn-block card-btn" id="member-card-btn">
        ✅ Prihlásiť na tréning
      </button>
      <div class="member-card-pwa" id="member-card-pwa"></div>
      <button type="button" class="btn btn-secondary btn-block member-card-logout" id="member-card-logout">
        Odhlásiť sa
      </button>
    </main>
  `;

  el.querySelector('#member-card-btn').addEventListener('click', () => {
    window.location.href = signInUrl;
  });

  el.querySelector('#member-card-logout').addEventListener('click', async () => {
    await signOut(auth);
    navigateTo('/');
  });

  const canvas = el.querySelector('#member-card-qr-canvas');
  import('qrcode').then(({ default: QRCode }) => {
    QRCode.toCanvas(canvas, signInUrl, { width: 280, margin: 2 }, (err) => {
      if (err) {
        const wrap = el.querySelector('#member-card-qr-wrap');
        wrap.innerHTML = '<p class="card-error-msg">QR kód sa nepodarilo vygenerovať.</p>';
      }
    });
  }).catch(() => {
    const wrap = el.querySelector('#member-card-qr-wrap');
    wrap.innerHTML = '<p class="card-error-msg">QR kód nie je k dispozícii.</p>';
  });

  const pwaContainer = el.querySelector('#member-card-pwa');
  if (canInstallPwa()) {
    const installBtn = document.createElement('button');
    installBtn.type = 'button';
    installBtn.className = 'btn btn-secondary btn-block member-card-install';
    installBtn.textContent = '📲 Nainštalovať aplikáciu';
    installBtn.addEventListener('click', async () => {
      installBtn.disabled = true;
      await triggerPwaInstall();
      if (!canInstallPwa()) installBtn.remove();
      installBtn.disabled = false;
    });
    pwaContainer.appendChild(installBtn);
  }
  if (isIos()) {
    const iosBlock = document.createElement('details');
    iosBlock.className = 'member-card-ios-install';
    iosBlock.innerHTML = `
      <summary>📱 Pridať na plochu (iPhone)</summary>
      <ol class="member-card-ios-steps">
        <li>Otvor túto stránku v Safari</li>
        <li>Stlač ikonu <strong>Zdieľať</strong> (štvorec so šípkou)</li>
        <li>Zvoľ <strong>Pridať na plochu</strong></li>
        <li>Potvrď názov a <strong>Pridať</strong></li>
      </ol>
    `;
    pwaContainer.appendChild(iosBlock);
  }

  return el;
}
