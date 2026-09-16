// jsdom lacks a few browser APIs the chart component touches. Stub them so
// component render tests can run. Real drawing is exercised in the browser.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// jsdom defines getContext but throws "not implemented"; replace it outright.
HTMLCanvasElement.prototype.getContext = (() => null) as never;
