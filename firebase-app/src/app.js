import { auth } from './firebase.js';
import { renderLogin } from './views/login.js';
import { renderRegister } from './views/register.js';
import { renderDashboard } from './views/dashboard.js';
import { renderCheckIn } from './views/checkin.js';
import { renderTrainer } from './views/trainer.js';
import { renderAdmin } from './views/admin.js';
import { renderQr } from './views/qr.js';
import { renderLanding } from './views/landing.js';
import { renderCard } from './views/card.js';

let currentUserProfile = null;

export function setUserProfile(profile) {
  currentUserProfile = profile;
}

export function getUserProfile() {
  return currentUserProfile;
}

export function getRole() {
  return currentUserProfile?.role || 'user';
}

function getRoute() {
  const hash = window.location.hash.slice(1) || '/';
  const path = hash.split('?')[0];
  const params = new URLSearchParams(window.location.hash.split('?')[1] || '');
  return { path: path === '' ? '/' : path, params };
}

function renderApp(user) {
  const app = document.getElementById('app');
  if (!app) return;

  if (!user) {
    const { path } = getRoute();
    if (path === '/register') {
      app.innerHTML = '';
      app.appendChild(renderRegister());
      return;
    }
    if (path === '/login') {
      app.innerHTML = '';
      app.appendChild(renderLogin());
      return;
    }
    if (path === '/card') {
      app.innerHTML = '';
      app.appendChild(renderCard());
      return;
    }
    app.innerHTML = '';
    app.appendChild(renderLanding());
    return;
  }

  const { path, params } = getRoute();
  const role = getRole();

  app.innerHTML = '';

  if (path === '/checkin' || params.get('view') === 'participant') {
    app.appendChild(renderCheckIn());
    return;
  }
  if (path === '/qr') {
    app.appendChild(renderQr());
    return;
  }
  if (path === '/trainer' || params.get('view') === 'trainer') {
    if (role !== 'trainer' && role !== 'admin') {
      app.appendChild(renderDashboard());
      return;
    }
    app.appendChild(renderTrainer());
    return;
  }
  if (path === '/admin') {
    if (role !== 'admin') {
      app.appendChild(renderDashboard());
      return;
    }
    app.appendChild(renderAdmin());
    return;
  }

  app.appendChild(renderDashboard());
}

export function navigateTo(path) {
  window.location.hash = path;
}

window.addEventListener('hashchange', () => {
  renderApp(auth.currentUser);
});

export { renderApp };
