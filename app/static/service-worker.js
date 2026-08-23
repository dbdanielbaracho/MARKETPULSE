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
  let data={};
  try{data=event.data?event.data.json():{}}catch{data={}}
  const title=String(data.title||'PrediBeacon alert').slice(0,120);
  const body=String(data.body||'A followed market has a new signal.').slice(0,300);
  let target='/alerts';
  try{const parsed=new URL(String(data.url||'/alerts'),self.location.origin);if(parsed.origin===self.location.origin)target=parsed.pathname+parsed.search+parsed.hash}catch{}
  event.waitUntil(self.registration.showNotification(title,{body,icon:'/icons/predibeacon.svg',badge:'/icons/predibeacon.svg',tag:'predibeacon-market-alert',data:{url:target}}));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const target=event.notification?.data?.url||'/alerts';
  event.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(windows=>{
    for(const client of windows){if('focus'in client){client.navigate(target);return client.focus()}}
    return clients.openWindow(target);
  }));
});