export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type PrimitiveBody = string | number | boolean | null;
type JsonBody =
  | PrimitiveBody
  | JsonBody[]
  | { [key: string]: JsonBody | undefined };

type RequestOptions = Omit<RequestInit, "body"> & {
  token?: string | null;
  body?: JsonBody | FormData;
};

function buildHeaders(token?: string | null, headers?: HeadersInit, isFormData?: boolean) {
  const merged = new Headers(headers);
  if (!isFormData && !merged.has("Content-Type")) {
    merged.set("Content-Type", "application/json");
  }
  if (token) {
    merged.set("Authorization", `Bearer ${token}`);
  }
  return merged;
}

export async function apiFetch<T>(
  path: string,
  { token, body, headers, ...init }: RequestOptions = {},
): Promise<T> {
  const isFormData = body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: buildHeaders(token, headers, isFormData),
    body:
      body === undefined
        ? undefined
        : isFormData
          ? body
          : JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    let message = text || `Request failed with ${response.status}`;

    try {
      const parsed = JSON.parse(text) as { detail?: string };
      if (parsed.detail) {
        message = parsed.detail;
      }
    } catch {
      // Fall back to the raw text response.
    }

    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function pollJobUntilSettled<T extends { status: string }>(
  path: string,
  token: string,
  {
    intervalMs = 1500,
    timeoutMs = 90_000,
  }: {
    intervalMs?: number;
    timeoutMs?: number;
  } = {},
): Promise<T> {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    const job = await apiFetch<T>(path, { token });
    if (job.status === "completed" || job.status === "failed") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }

  throw new Error("Timed out while waiting for the background job to finish.");
}

export async function downloadJobArtifact(
  jobId: string,
  token: string,
  suggestedName?: string,
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/artifact`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || "Unable to download the artifact.");
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = suggestedName ?? `artifact-${jobId}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function formatApiError(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}
