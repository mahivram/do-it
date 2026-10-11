import assert from "node:assert/strict";
import test from "node:test";
import {
  answerConfirmation,
  answerUserInput,
  getAgentJob,
  startAgentJob,
} from "../src/agentApi.js";

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

test("starts a local Python agent job with prompt and selected provider settings", async () => {
  let requestUrl;
  let requestOptions;
  const result = await startAgentJob(
    "Open Notepad",
    "gemini",
    { apiKey: "local-key", model: "gemini-test" },
    async (url, options) => {
      requestUrl = url;
      requestOptions = options;
      return jsonResponse(202, { id: "job-1", status: "queued" });
    },
  );

  assert.equal(requestUrl, "/api/jobs");
  assert.equal(requestOptions.method, "POST");
  assert.deepEqual(JSON.parse(requestOptions.body), {
    prompt: "Open Notepad",
    provider: "gemini",
    config: { apiKey: "local-key", model: "gemini-test" },
  });
  assert.equal(result.id, "job-1");
});

test("polls the local agent for tool activity and completion", async () => {
  let requestUrl;
  const result = await getAgentJob(
    "job with/slash",
    async (url) => {
      requestUrl = url;
      return jsonResponse(200, {
        id: "job with/slash",
        status: "completed",
        tools: [{ name: "open_window", status: "completed" }],
      });
    },
  );

  assert.equal(requestUrl, "/api/jobs/job%20with%2Fslash");
  assert.equal(result.tools[0].name, "open_window");
});

test("posts explicit confirmation decisions to the local agent", async () => {
  let requestOptions;
  await answerConfirmation(
    "job-1",
    "confirm-1",
    false,
    async (_url, options) => {
      requestOptions = options;
      return jsonResponse(200, { status: "decision_received" });
    },
  );

  assert.equal(requestOptions.method, "POST");
  assert.deepEqual(JSON.parse(requestOptions.body), {
    confirmationId: "confirm-1",
    approved: false,
  });
});

test("posts the user's answer to a pending agent question", async () => {
  let requestUrl;
  let requestOptions;
  await answerUserInput(
    "job-1",
    "interaction-1",
    "Personal account",
    async (url, options) => {
      requestUrl = url;
      requestOptions = options;
      return jsonResponse(200, { status: "answer_received" });
    },
  );

  assert.equal(requestUrl, "/api/jobs/job-1/input");
  assert.equal(requestOptions.method, "POST");
  assert.deepEqual(JSON.parse(requestOptions.body), {
    interactionId: "interaction-1",
    answer: "Personal account",
  });
});

test("surfaces errors returned by the Python API", async () => {
  await assert.rejects(
    startAgentJob("prompt", "openrouter", {}, async () => (
      jsonResponse(400, { error: "Add an API key in Settings." })
    )),
    /Add an API key in Settings/,
  );
});

test("reports malformed responses from the Python API", async () => {
  await assert.rejects(
    getAgentJob("job-1", async () => ({
      ok: true,
      status: 200,
      json: async () => { throw new SyntaxError("bad JSON"); },
    })),
    /invalid response/,
  );
});
