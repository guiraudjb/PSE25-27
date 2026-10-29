const CACHE_NAME = 'v56-webview-sans-voix';
const ASSETS = [
  'index.html',
  'catalogue.json',
  'manifest.json',
  // Ajoute ici d'autres fichiers statiques si nécessaire (ex: icônes)
];

// Installation : Mise en cache des fichiers de base
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

// Activation : Nettoyage des anciens caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
});

// Stratégie : Cache First (Récupère du cache, sinon réseau)
self.addEventListener('fetch', (event) => {
  // Documents sources (PDF de data/source/, parfois lourds) : jamais mis en cache, réseau direct.
  if (event.request.url.includes('/data/source/')) return;
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).then((fetchResponse) => {
        // Mise en cache dynamique des fichiers chargés (quizz, etc.), uniquement les réponses
        // complètes réussies : une 404 mise en cache (média pas encore publié) masquerait le
        // fichier indéfiniment, et les réponses partielles 206 (lecture audio) ne sont pas cachables.
        if (event.request.method !== 'GET' || fetchResponse.status !== 200) return fetchResponse;
        // Mise en cache sans attendre : un cache plein (petite box Android) ne doit jamais faire échouer le chargement
        const copie = fetchResponse.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copie)).catch(() => {});
        return fetchResponse;
      });
    }).catch(() => fetch(event.request))
  );
});
