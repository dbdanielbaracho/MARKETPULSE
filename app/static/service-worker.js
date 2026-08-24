const CACHE='predibeacon-v4';
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
self.addEventListener('push',event=>{
  let payload={title:'PrediBeacon market alert',body:'A followed market has a new observable signal.',url:'/alerts'};
  try{if(event.data)payload={...payload,...event.data.json()}}catch{}
  let target='/alerts';
  try{const candidate=new URL(payload.url||'/alerts',self.location.origin);if(candidate.origin===self.location.origin)target=candidate.pathname+candidate.search+candidate.hash}catch{}
  event.waitUntil(self.registration.showNotification(String(payload.title||'PrediBeacon market alert').slice(0,120),{
    body:String(payload.body||'').slice(0,240),
    icon:'/icons/predibeacon.svg',
    badge:'/icons/predibeacon.svg',
    data:{url:target},
    tag:'predibeacon-market-alert'
  }));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const target=event.notification?.data?.url||'/alerts';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{
    const existing=list.find(client=>new URL(client.url).origin===self.location.origin);
    if(existing){existing.navigate(target);return existing.focus()}
    return clients.openWindow(target);
  }));
});
