/**
 * Logika časov tréningov ako v pôvodnej Streamlit aplikácii.
 * Časové pásmo: Europe/Bratislava (Slovensko).
 */

export const STREAMLIT_BASE_URL = 'https://giantgym.streamlit.app';

export const MEMBERSHIP_TYPES = [
  'Skúšobný tréning',
  'Mesačné členstvo',
  'Jednorázový vstup',
  'Ročné členstvo'
];

const TRAINING_TIMES_WEEKDAY = ['7:00', '15:30', '17:00', '18:30'];
const TRAINING_TIMES_WEEKEND = ['9:00'];
export const MANUAL_ONLY_TRAINING = '17:30 - ženský tréning s Diankou';
const MANUAL_ONLY_WEEKDAYS = [2, 4]; // Ut=2, Št=4 (getDay(): 0=Ne, 1=Po, ..., 6=So)

function getLocalNow() {
  return new Date();
}

/**
 * Časy tréningov dostupné dnes. Víkend len 9:00, týždeň 7:00, 15:30, 17:00, 18:30.
 */
export function getTrainingTimesForToday() {
  const now = getLocalNow();
  const day = now.getDay();
  if (day === 0 || day === 6) return [...TRAINING_TIMES_WEEKEND];
  return [...TRAINING_TIMES_WEEKDAY];
}

/**
 * Pre trénera: dnešné časy + v Ut a Št ešte "17:30 - ženský tréning s Diankou".
 */
export function getTrainingTimesForManualForm() {
  const times = getTrainingTimesForToday();
  const now = getLocalNow();
  const day = now.getDay();
  if (MANUAL_ONLY_WEEKDAYS.includes(day)) return [...times, MANUAL_ONLY_TRAINING];
  return times;
}

/**
 * Najbližší čas tréningu podľa aktuálneho času (logika ako v Streamlit).
 */
export function getNextTrainingTime() {
  const now = getLocalNow();
  const day = now.getDay();
  const h = now.getHours();
  const m = now.getMinutes();

  if (day === 0 || day === 6) return '9:00';
  if (h < 8) return '7:00';
  if (h < 16 || (h === 16 && m < 30)) return '15:30';
  if (h < 18) return '17:00';
  return '18:30';
}
