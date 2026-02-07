import { navigateTo } from '../app.js';

/**
 * Úvodná stránka pre neprihlásených: len odkaz na prihlásenie a registráciu.
 */
export function renderLanding() {
  const el = document.createElement('div');
  el.className = 'view view-landing';

  el.innerHTML = `
    <header class="auth-header">
      <h1>🥊 Giant Gym</h1>
      <p>Členská karta a prihlásenie na tréning</p>
    </header>

    <section class="landing-auth">
      <p class="landing-auth-links">
        <a href="#/login" class="btn btn-primary btn-block">Prihlásiť sa</a>
        <a href="#/register" class="btn btn-secondary btn-block">Registrovať sa</a>
      </p>
    </section>
  `;

  return el;
}
