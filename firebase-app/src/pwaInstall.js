const DISMISS_KEY = 'gym-pwa-install-dismissed';

export function initPwaInstall() {
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (localStorage.getItem(DISMISS_KEY)) return;
    showBanner();
  });

  window.addEventListener('appinstalled', () => {
    deferredPrompt = null;
    hideBanner();
  });

  function showBanner() {
    if (document.getElementById('pwa-install-banner')) return;
    const banner = document.createElement('div');
    banner.id = 'pwa-install-banner';
    banner.className = 'pwa-install-banner';
    banner.innerHTML = `
      <span class="pwa-install-text">📲 Nainštaluj aplikáciu na telefón – rýchlejší prístup a prihlásenie cez NFC.</span>
      <div class="pwa-install-buttons">
        <button type="button" class="btn btn-primary btn-small" id="pwa-install-btn">Stiahnuť aplikáciu</button>
        <button type="button" class="btn btn-small btn-dismiss" id="pwa-dismiss-btn">Neskôr</button>
      </div>
    `;
    document.body.appendChild(banner);

    document.getElementById('pwa-install-btn').addEventListener('click', async () => {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') hideBanner();
      deferredPrompt = null;
    });

    document.getElementById('pwa-dismiss-btn').addEventListener('click', () => {
      localStorage.setItem(DISMISS_KEY, '1');
      hideBanner();
    });
  }

  function hideBanner() {
    const b = document.getElementById('pwa-install-banner');
    if (b) b.remove();
  }
}
