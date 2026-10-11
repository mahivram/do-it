import assert from "node:assert/strict";
import test from "node:test";
import { loadLocalValue, saveLocalValue } from "../src/storage.js";

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("returns the fallback when no local value has been saved", () => {
  const fallback = { provider: "openrouter" };
  assert.equal(loadLocalValue("settings", fallback, createStorage()), fallback);
});

test("saves and restores local values as JSON", () => {
  const storage = createStorage();
  const settings = { provider: "gemini", apiKey: "local-test-key" };

  saveLocalValue("settings", settings, storage);

  assert.deepEqual(loadLocalValue("settings", null, storage), settings);
});

test("surfaces malformed saved data instead of silently replacing it", () => {
  const storage = {
    getItem: () => "{not json",
  };
  assert.throws(() => loadLocalValue("settings", {}, storage), SyntaxError);
});
