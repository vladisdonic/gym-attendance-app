import { signInWithEmailAndPassword } from 'firebase/auth';
import { collection, addDoc } from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { navigateTo } from '../app.js';
import {
  MEMBERSHIP_TYPES,
  getTrainingTimesForToday,
  getNextTrainingTime
} from '../trainingHelpers.js';

/**
 * Úvodná stránka pre neprihlásených: formulár na prihlásenie na tréning (bez účtu) + odkaz na prihlásenie/registráciu.
 */
export function renderLanding() {
  const el = document.createElement('div');
  el.className = 'view view-landing';

  const timesToday = getTrainingTimesForToday();
  const nextTime = getNextTrainingTime();
  const defaultTime = timesToday.includes(nextTime) ? nextTime : timesToday[0];

  el.innerHTML = `
    <header class="auth-header">
      <h1>🥊 Gym Evidencia</h1>
      <p>Prihlásenie na tréning</p>
    </header>

    <section class="landing-checkin">
      <h2>Prihlásiť sa na tréning (bez účtu)</h2>
      <form class="checkin-form" id="guest-checkin-form">
        <label for="guest-name">Meno a priezvisko *</label>
        <input type="text" id="guest-name" name="name" required placeholder="Ján Novák" />
        <label for="guest-membership">Typ členstva</label>
        <select id="guest-membership" name="membership" required>
          ${MEMBERSHIP_TYPES.map((t, i) => `<option value="${escapeHtml(t)}" ${i === 1 ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
        </select>
        <label for="guest-training">Čas tréningu</label>
        <select id="guest-training" name="training" required>
          ${timesToday.map(t => `<option value="${escapeHtml(t)}" ${t === defaultTime ? 'selected' : ''}>${escapeHtml(t)}</option>`).join('')}
        </select>
        <button type="submit" class="btn btn-primary btn-block">Prihlásiť sa na tréning</button>
      </form>
      <p class="checkin-success" id="guest-success" hidden>✓ Ste prihlásený na tréning.</p>
      <p class="auth-error" id="guest-error"></p>
    </section>

    <section class="landing-auth">
      <h2>Mám účet</h2>
      <p class="landing-auth-links">
        <a href="#" id="link-login">Prihlásiť sa</a>
        &nbsp;·&nbsp;
        <a href="#/register" id="link-register">Registrovať sa</a>
      </p>
      <div id="login-inline" class="login-inline" hidden>
        <form class="auth-form" id="login-form-inline">
          <label for="inline-email">Email</label>
          <input type="email" id="inline-email" required autocomplete="email" placeholder="vas@email.sk" />
          <label for="inline-password">Heslo</label>
          <input type="password" id="inline-password" required autocomplete="current-password" placeholder="••••••••" />
          <button type="submit" class="btn btn-primary">Prihlásiť sa</button>
          <p class="auth-error" id="inline-login-error"></p>
        </form>
      </div>
    </section>
  `;

  const guestForm = el.querySelector('#guest-checkin-form');
  const successEl = el.querySelector('#guest-success');
  const errorEl = el.querySelector('#guest-error');
  const linkLogin = el.querySelector('#link-login');
  const linkRegister = el.querySelector('#link-register');
  const loginInline = el.querySelector('#login-inline');
  const loginFormInline = el.querySelector('#login-form-inline');
  const inlineLoginError = el.querySelector('#inline-login-error');

  linkLogin.addEventListener('click', (e) => {
    e.preventDefault();
    loginInline.hidden = !loginInline.hidden;
  });

  guestForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    successEl.hidden = true;
    errorEl.textContent = '';
    const nameInput = guestForm.querySelector('#guest-name');
    const membershipSelect = guestForm.querySelector('#guest-membership');
    const trainingSelect = guestForm.querySelector('#guest-training');
    const displayName = (nameInput && nameInput.value) ? nameInput.value.trim() : '';
    const membershipType = membershipSelect ? membershipSelect.value : '';
    const trainingTime = trainingSelect ? trainingSelect.value : '';
    if (!displayName) {
      errorEl.textContent = 'Zadajte meno.';
      return;
    }
    const btn = guestForm.querySelector('button[type="submit"]');
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
        guestEntry: true,
        timestamp: new Date()
      });
      successEl.hidden = false;
      successEl.textContent = '✓ Ste prihlásený na tréning.';
      if (nameInput) nameInput.value = '';
      const next = getNextTrainingTime();
      const times = getTrainingTimesForToday();
      if (trainingSelect) trainingSelect.value = times.includes(next) ? next : times[0];
    } catch (err) {
      const msg = err.code === 'permission-denied'
        ? 'Zápis nie je povolený. Skontrolujte Firestore pravidlá (guest záznamy).'
        : (err.message || 'Zápis zlyhal.');
      errorEl.textContent = msg;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Prihlásiť sa na tréning';
    }
  });

  if (loginFormInline) {
    loginFormInline.addEventListener('submit', async (e) => {
      e.preventDefault();
      inlineLoginError.textContent = '';
      const email = loginFormInline.querySelector('#inline-email').value.trim();
      const password = loginFormInline.querySelector('#inline-password').value;
      const btn = loginFormInline.querySelector('button[type="submit"]');
      btn.disabled = true;
      try {
        await signInWithEmailAndPassword(auth, email, password);
        navigateTo('/');
      } catch (err) {
        inlineLoginError.textContent = err.code === 'auth/invalid-credential' || err.code === 'auth/user-not-found' ? 'Nesprávny email alebo heslo.' : (err.message || 'Prihlásenie zlyhalo.');
      } finally {
        btn.disabled = false;
      }
    });
  }

  return el;
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
