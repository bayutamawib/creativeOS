export function csrfHeaders(): Record<string, string> {
  const token = document.cookie
    .split("; ")
    .find((s) => s.startsWith("__Host-creative_csrf="))
    ?.split("=")[1];
  return token ? { "X-CSRF-Token": token } : {};
}
export async function mutate(
  path: string,
  method: string,
  payload?: unknown,
  additionalHeaders?: Record<string, string>,
) {
  const res = await fetch("/api/v1" + path, {
    method,
    cache: "no-store",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...csrfHeaders(),
      ...additionalHeaders,
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (!res.ok) {
    if (res.status === 401 && path !== "/auth/login")
      window.location.replace("/login");
    const error = await res.json().catch(() => null);
    throw new Error(error?.error?.message ?? "Unable to complete the request");
  }
  return res.status === 204 ? undefined : (await res.json()).data;
}
