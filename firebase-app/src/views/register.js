import { createUserWithEmailAndPassword } from 'firebase/auth';
import { doc, setDoc } from 'firebase/firestore';
import { auth, db } from '../firebase.js';
import { navigateTo } from '../app.js';

const DEFAULT_ROLE = 'user';

export function renderRegister() {
  const el = document.createElement('div');
  el.className = 'view view-auth';

  el.innerHTML = `
    <header class="auth-header">
      <h1>🥊 Gym Evidencia</h1>
      <p>Registrácia</p>
    </header>
    <form class="auth-form" id="register-form">
      <label for="reg-email">Email</label>
      <input type="email" id="reg-email" name="email" required autocomplete="email" placeholder="vas@email.sk" />
      <label for="reg-password">Heslo (min. 6 znakov)</label>
      <input type="password" id="reg-password" name="password" required minlength="6" autocomplete="new-password" placeholder="••••••••" />
      <label for="reg-name">Meno (pre zobrazenie)</label>
      <input type="text" id="reg-name" name="displayName" required placeholder="Ján Novák" />
      <button type="submit" class="btn btn-primary">Vytvoriť účet</button>
      <p class="auth-error" id="register-error"></p>
      <p class="auth-link">
        Už máte účet? <a href="#">Prihlásiť sa</a>
      </p>
    </form>
  `;

  const form = el.querySelector('#register-form');
  const errorEl = el.querySelector('#register-error');

  el.querySelector('.auth-link a').addEventListener('click', (e) => {
    e.preventDefault();
    navigateTo('/');
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    errorEl.textContent = '';
    const email = form.email.value.trim();
    const password = form.password.value;
    const displayName = form.displayName.value.trim();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Vytváram účet…';
    try {
      const cred = await createUserWithEmailAndPassword(auth, email, password);
      await setDoc(doc(db, 'profiles', cred.user.uid), {
        email,
        displayName,
        role: DEFAULT_ROLE,
        createdAt: new Date().toISOString()
      });
      navigateTo('/');
    } catch (err) {
      if (err.code === 'auth/email-already-in-use') {
        errorEl.textContent = 'Tento email už je registrovaný. Prihláste sa alebo použite iný.';
      } else if (err.code === 'auth/weak-password') {
        errorEl.textContent = 'Heslo musí mať aspoň 6 znakov.';
      } else {
        errorEl.textContent = err.message || 'Registrácia zlyhala.';
      }
    } finally {
      btn.disabled = false;
      btn.textContent = 'Vytvoriť účet';
    }
  });

  return el;
}
