import "@testing-library/jest-dom";

// Vitest 4.x / jsdom does not automatically expose window.localStorage as a
// bare global on Node's globalThis. Provide a persistent in-memory mock so
// tests can call `localStorage.*` without additional per-file setup.
// Each test file that mutates storage calls `localStorage.clear()` in
// beforeEach to guarantee isolation between cases.
class LocalStorageMock implements Storage {
  private store = new Map<string, string>();
  get length() { return this.store.size; }
  clear() { this.store.clear(); }
  getItem(key: string) { return this.store.get(key) ?? null; }
  setItem(key: string, value: string) { this.store.set(key, value); }
  removeItem(key: string) { this.store.delete(key); }
  key(index: number) { return [...this.store.keys()][index] ?? null; }
}

Object.defineProperty(globalThis, "localStorage", {
  value: new LocalStorageMock(),
  writable: true,
  configurable: true,
});
