export async function readiness(): Promise<boolean> {
  try {
    const res = await fetch(
      `${process.env.INTERNAL_API_URL ?? "http://backend:8000"}/health/ready`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(4000),
      },
    );
    return res.ok && (await res.json()).status === "ready";
  } catch {
    return false;
  }
}
