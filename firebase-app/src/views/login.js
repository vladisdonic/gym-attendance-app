import { signInWithEmailAndPassword } from 'firebase/auth';
import { auth } from '../firebase.js';
import { navigateTo } from '../app.js';

export function renderLogin() {
  const el = document.createElement('div');
  el.className = 'view view-auth';

  el.innerHTML = `
    <header class="auth-header">
      <h1>🥊 Gym Evidencia</h1>
      <p>Prihlásenie</p>
    </header>
    <form class="auth-form" id="login-form">
      <label for="email">Email</label>
      <input type="email" id="email" name="email" required autocomplete="email" placeholder="vas@email.sk" />
      <label for="password">Heslo</label>
      <input type="password" id="password" name="password" required autocomplete="current-password" placeholder="••••••••" />
      <button type="submit" class="btn btn-primary">Prihlásiť sa</button>
      <p class="auth-error" id="login-error"></p>
      <p class="auth-link">
        Nemáte účet? <a href="#/register">Registrovať sa</a><br />
        <a href="#">Späť na úvod</a>
      </p>
    </form>
  `;

  const form = el.querySelector('#login-form');
  const errorEl = el.querySelector('#login-error');

  el.querySelector('.auth-link a[href="#"]')?.addEventListener('click', (e) => {
    e.preventDefault();
    navigateTo('/');
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.textContent = '';
    const email = form.email.value.trim();
    const password = form.password.value;
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Prihlasujem…';
    try {
      await signInWithEmailAndPassword(auth, email, password);
      navigateTo('/');
    } catch (err) {
      if (err.code === 'auth/invalid-credential' || err.code === 'auth/wrong-password' || err.code === 'auth/user-not-found') {
        errorEl.textContent = 'Nesprávny email alebo heslo.';
      } else {
        errorEl.textContent = err.message || 'Prihlásenie zlyhalo.';
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Prihlásiť sa';
    }
  });

  return el;
}
