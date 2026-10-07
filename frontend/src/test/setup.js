import "@testing-library/jest-dom/vitest";

// Recharts' ResponsiveContainer needs a ResizeObserver to measure its box.
// jsdom has none, so without this every chart-mounted test would throw.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    constructor(callback) {
      this.callback = callback;
    }

    observe(element) {
      const width = element?.clientWidth || 800;
      const height = element?.clientHeight || 300;
      this.callback([{ contentRect: { width, height } }]);
    }

    unobserve() {}

    disconnect() {}
  };
}