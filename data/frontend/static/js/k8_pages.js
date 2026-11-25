/**
 * K8-QUANT page-module registry (CDN Vue 3, no bundler).
 * Each pages/*.js calls K8Pages.register(fn); app.js merges via K8Pages.apply().
 */
(function (global) {
  // 退役模块接口短路：后端契约仍是 410 Gone，但前端不再把请求发出去，
  // 避免控制台被一批 "Failed to load resource: 410" 刷屏。
  (function () {
    const RETIRED = /\/(?:api\/quant\/(?:tda|dtw|transformer|matrix-profile|linear-algebra)|api\/spatial-points)(?:\/|\?|$)/;
    const nativeFetch = global.fetch.bind(global);
    global.fetch = function (input, init) {
      const url = typeof input === 'string' ? input : (input && input.url) || '';
      if (RETIRED.test(url)) {
        return Promise.resolve(new Response(
          JSON.stringify({ status: 'retired', message: '该模块已退役' }),
          { status: 410, headers: { 'Content-Type': 'application/json' } }
        ));
      }
      return nativeFetch(input, init);
    };
  })();

  const K8Pages = {
    mixins: [],
    register(fn) {
      if (typeof fn === 'function') this.mixins.push(fn);
    },
    apply(vueApi, ctx) {
      const extra = {};
      for (const fn of this.mixins) {
        try {
          const part = fn(vueApi, ctx) || {};
          Object.assign(extra, part);
        } catch (err) {
          console.error('[K8Pages] mixin failed:', err);
        }
      }
      return extra;
    }
  };
  global.K8Pages = K8Pages;
})(typeof window !== 'undefined' ? window : globalThis);
