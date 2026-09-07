export function clientApiUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL ||
    (process.env.NODE_ENV === "production" ? undefined : "http://localhost:8000");
  if (!url) throw new Error("NEXT_PUBLIC_API_URL is not configured.");
  return url;
}
