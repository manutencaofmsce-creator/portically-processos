/* Cache apenas do aplicativo. Dados de campo permanecem no IndexedDB. */
'use strict';
const CACHE='portically-campo-shell-v1.0.1';
const FILES=['./','./index.html','./style.css','./core.js','./checklist.js','./store.js','./app.js','./manifest.webmanifest','./icon-192.png','./icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('portically-campo-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{if(event.request.method!=='GET'||new URL(event.request.url).origin!==self.location.origin)return;event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request).catch(()=>{if(event.request.mode==='navigate')return caches.match(new URL('./index.html',self.registration.scope));return new Response('Recurso não disponível offline',{status:503,statusText:'Offline'});})));});
