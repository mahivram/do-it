async function readJson(response) {
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The local agent returned an invalid response (${response.status}).`);
  }
  if (!response.ok) {
    throw new Error(data?.error || `The local agent request failed (${response.status}).`);
  }
  return data;
}

export async function startAgentJob(prompt, provider, config, fetchImpl = fetch) {
  const response = await fetchImpl("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, provider, config }),
  });
  return readJson(response);
}

export async function getAgentJob(jobId, fetchImpl = fetch) {
  const response = await fetchImpl(`/api/jobs/${encodeURIComponent(jobId)}`);
  return readJson(response);
}

export async function cancelAgentJob(jobId, fetchImpl = fetch) {
  const response = await fetchImpl(
    `/api/jobs/${encodeURIComponent(jobId)}/cancel`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    },
  );
  return readJson(response);
}

export async function answerConfirmation(
  jobId,
  confirmationId,
  approved,
  fetchImpl = fetch,
) {
  const response = await fetchImpl(
    `/api/jobs/${encodeURIComponent(jobId)}/confirmation`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmationId, approved }),
    },
  );
  return readJson(response);
}

export async function answerUserInput(
  jobId,
  interactionId,
  answer,
  fetchImpl = fetch,
) {
  const response = await fetchImpl(
    `/api/jobs/${encodeURIComponent(jobId)}/input`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ interactionId, answer }),
    },
  );
  return readJson(response);
}
