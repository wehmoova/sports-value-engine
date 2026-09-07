import "server-only";

const baseUrl = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === "production" ? undefined : "http://localhost:8000");

export async function apiFetch<T>(path: string): Promise<T> {
  if (!baseUrl) throw new Error("Backend URL is not configured (INTERNAL_API_URL).");
  const response = await fetch(`${baseUrl}/api/v1${path}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status})`);
  }
  return (await response.json()) as T;
}
