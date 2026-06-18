const CACHE_NAME = 'v37-cache-v2';
const ASSETS = [
  'index.html',
  'modules.json',
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
        // Optionnel : Mettre en cache dynamiquement les nouveaux fichiers chargés (quizz, etc.)
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
