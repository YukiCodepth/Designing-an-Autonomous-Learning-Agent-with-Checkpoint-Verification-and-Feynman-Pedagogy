export const API_BASE_URL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8001";

type FetchOptions = RequestInit & {
  token?: string;
};

export async function apiFetch<T>(
  path: string,
  { token, headers, ...init }: FetchOptions = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export const demoToken = process.env.NEXT_PUBLIC_DEMO_TOKEN;
