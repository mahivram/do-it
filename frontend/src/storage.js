export function loadLocalValue(key, fallback, storage = window.localStorage) {
  const storedValue = storage.getItem(key);
  return storedValue === null ? fallback : JSON.parse(storedValue);
}

export function saveLocalValue(key, value, storage = window.localStorage) {
  storage.setItem(key, JSON.stringify(value));
}
