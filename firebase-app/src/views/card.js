/**
 * Karta člena – zobrazí sa bez prihlásenia.
 * Parametre z hash: u = zakódovaná Streamlit prihlasovacia URL, name = meno člena.
 * Zobrazí meno, QR kód a tlačidlo "Prihlásiť na tréning" (otvorí Streamlit URL).
 */
export function renderCard() {
  const el = document.createElement('div');
  el.className = 'view view-card';

  const hashPart = window.location.hash.slice(1) || '';
  const queryStart = hashPart.indexOf('?');
  const params = new URLSearchParams(queryStart >= 0 ? hashPart.slice(queryStart + 1) : '');
  const signInUrl = params.get('u') ? decodeURIComponent(params.get('u')) : '';
  const name = params.get('name') ? decodeURIComponent(params.get('name')) : '';

  if (!signInUrl) {
    el.innerHTML = `
      <main class="card-main card-error">
        <h1>🥊 Giant Gym</h1>
        <p>Chýba odkaz na prihlásenie. Otvor kartu cez odkaz z aplikácie (Streamlit).</p>
      </main>
    `;
    return el;
  }

  el.innerHTML = `
    <main class="card-main">
      <h1>🥊 Giant Gym</h1>
      ${name ? `<p class="card-name">${escapeHtml(name)}</p>` : ''}
      <div class="card-qr-wrap" id="card-qr-wrap">
        <canvas id="card-qr-canvas" aria-hidden="true"></canvas>
      </div>
      <p class="card-hint">Naskenuj QR alebo stlač tlačidlo</p>
      <button type="button" class="btn btn-primary btn-block card-btn" id="card-btn">
        ✅ Prihlásiť na tréning
      </button>
    </main>
  `;

  const btn = el.querySelector('#card-btn');
  btn.addEventListener('click', () => {
    window.location.href = signInUrl;
  });

  const canvas = el.querySelector('#card-qr-canvas');
  import('qrcode').then(({ default: QRCode }) => {
    QRCode.toCanvas(canvas, signInUrl, { width: 280, margin: 2 }, (err) => {
      if (err) {
        const wrap = el.querySelector('#card-qr-wrap');
        wrap.innerHTML = '<p class="card-error-msg">QR kód sa nepodarilo vygenerovať.</p>';
      }
    });
  }).catch(() => {
    const wrap = el.querySelector('#card-qr-wrap');
    wrap.innerHTML = '<p class="card-error-msg">QR kód nie je k dispozícii.</p>';
  });

  return el;
}

function escapeHtml(s) {
  if (s == null) return '';
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}
