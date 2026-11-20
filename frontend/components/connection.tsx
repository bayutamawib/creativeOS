import { readiness } from "@/lib/readiness";
export async function Connection() {
  const ready = await readiness();
  return (
    <p role="status">Workspace service {ready ? "connected" : "unavailable"}</p>
  );
}
