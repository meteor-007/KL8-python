// KL8 PWA Service Worker
// v2: 移除不存在的 /static/css/style.css 与 /static/js/app.js 预缓存
//     （static/css/ 为空、static/js/ 只有 sw.js，原先 cache.addAll 404 → SW 安装失败 → 离线功能失效）
// v3: 前端模板曾改动（submitStep1 移除、daily-points 改只读 GET），旧缓存让浏览器持续加载旧页面
//     引发 POST /api/daily-points 405。bump 缓存名以强制淘汰旧页面。
// v4: 前端模板新增批量补跑日期选择器（v3.1），bump 缓存名以淘汰旧页面。
const CACHE_NAME = 'kl8-pwa-v4';
const ASSETS = [
    '/',
    '/manifest.json'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // API请求不走缓存
    if (event.request.url.includes('/api/')) return;
    event.respondWith(
        caches.match(event.request).then((resp) => {
            return resp || fetch(event.request).then((response) => {
                if (response.status === 200) {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                }
                return response;
            });
        }).catch(() => caches.match('/'))
    );
});
