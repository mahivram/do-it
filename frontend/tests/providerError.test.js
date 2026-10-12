import assert from "node:assert/strict";
import test from "node:test";
import {
  describeProviderError,
  isProviderConnectionError,
} from "../src/providerError.js";

test("recognizes provider connection failures", () => {
  assert.equal(isProviderConnectionError("Connection error."), true);
  assert.equal(isProviderConnectionError("actively refused the connection"), true);
  assert.equal(isProviderConnectionError("Invalid API key"), false);
});

test("explains that the FreeLLMAPI router must be running", () => {
  assert.equal(
    describeProviderError("Connection error.", "freellm", "http://127.0.0.1:31415/v1"),
    "Could not connect to FreeLLMAPI at http://127.0.0.1:31415/v1. "
      + "Start the FreeLLMAPI router and verify its API base URL in Settings.",
  );
});

test("uses the FreeLLMAPI default URL when no URL is configured", () => {
  assert.match(
    describeProviderError("Connection error.", "freellm", ""),
    /http:\/\/127\.0\.0\.1:31415\/v1/,
  );
});

test("keeps non-connection errors intact", () => {
  assert.equal(
    describeProviderError("Invalid API key", "freellm", ""),
    "Invalid API key",
  );
});

test("provides a generic connectivity hint for other providers", () => {
  assert.match(
    describeProviderError("Connection error.", "gemini", ""),
    /Google Gemini/,
  );
});
