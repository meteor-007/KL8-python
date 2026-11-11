/**
 * K8-QUANT page-module registry (CDN Vue 3, no bundler).
 * Each pages/*.js calls K8Pages.register(fn); app.js merges via K8Pages.apply().
 */
(function (global) {
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
