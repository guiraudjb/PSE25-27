const CACHE_NAME = 'v40-data-jeu';
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
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request).then((fetchResponse) => {
        // Mise en cache dynamique des fichiers chargés (quizz, etc.), uniquement les réponses
        // complètes réussies : une 404 mise en cache (média pas encore publié) masquerait le
        // fichier indéfiniment, et les réponses partielles 206 (lecture audio) ne sont pas cachables.
        if (event.request.method !== 'GET' || fetchResponse.status !== 200) return fetchResponse;
        return caches.open(CACHE_NAME).then((cache) => {
          cache.put(event.request, fetchResponse.clone());
          return fetchResponse;
        });
      });
    }).catch(() => {
        // Fallback si tout échoue (optionnel)
    })
  );
});
