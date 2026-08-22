const CACHE='predibeacon-v3';
const CORE=['/','/top','/watchlist','/alerts','/methodology','/risk','/privacy','/terms','/manifest.webmanifest','/icons/predibeacon.svg'];
const NEVER_CACHE=['/api/','/admin','/out/','/go/','/articles'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(CORE)).then(()=>self.skipWaiting()));
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE).map(key=>caches.delete(key)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const request=event.request;
  const url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==location.origin||NEVER_CACHE.some(prefix=>url.pathname.startsWith(prefix)))return;
  if(request.mode==='navigate'){
    event.respondWith(fetch(request).then(response=>{
      if(response.ok&&response.type==='basic')caches.open(CACHE).then(cache=>cache.put(request,response.clone()));
      return response;
    }).catch(()=>caches.match(request).then(cached=>cached||caches.match('/'))));
    return;
  }
  if(CORE.includes(url.pathname)){
    event.respondWith(caches.match(request).then(cached=>cached||fetch(request)));
  }
});