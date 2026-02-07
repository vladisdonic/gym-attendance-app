import { onAuthStateChanged } from 'firebase/auth';
import { doc, getDoc } from 'firebase/firestore';
import { auth, db } from './firebase.js';
import { renderApp, setUserProfile } from './app.js';
import { initPwaInstall } from './pwaInstall.js';

initPwaInstall();

onAuthStateChanged(auth, async (user) => {
  if (user) {
    const profileSnap = await getDoc(doc(db, 'profiles', user.uid));
    const profile = profileSnap.exists() ? profileSnap.data() : null;
    setUserProfile(profile);
  } else {
    setUserProfile(null);
  }
  renderApp(user);
});
