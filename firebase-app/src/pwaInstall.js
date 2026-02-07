const DISMISS_KEY = 'gym-pwa-install-dismissed';
let deferredPrompt = null;

function onBeforeInstall(e) {
  e.preventDefault();
  deferredPrompt = e;
  if (typeof window.showBanner === 'function' && !localStorage.getItem(DISMISS_KEY)) window.showBanner();
}
function onAppInstalled() {
  deferredPrompt = null;
}
window.addEventListener('beforeinstallprompt', onBeforeInstall);
window.addEventListener('appinstalled', onAppInstalled);

/** Android: či je k dispozícii inštalačný prompt (PWA ešte nie je nainštalovaná). */
export function canInstallPwa() {
  return !!deferredPrompt;
}

/** Android: zobrazenie natívneho dialógu „Pridať na plochu“. Vráti Promise<{outcome}> */
export async function triggerPwaInstall() {
  if (!deferredPrompt) return { outcome: 'dismissed' };
  deferredPrompt.prompt();
  const result = await deferredPrompt.userChoice;
  deferredPrompt = null;
  return result;
}

export function initPwaInstall() {
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
      const result = await triggerPwaInstall();
      if (result.outcome === 'accepted') hideBanner();
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

  window.showBanner = showBanner;
}
