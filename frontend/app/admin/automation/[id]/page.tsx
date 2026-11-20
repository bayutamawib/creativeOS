import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import { canManage } from "@/lib/projects";
import { OperationForm } from "@/components/operation-form";
type Row = Record<string, string | number | boolean | null>;
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const me = await requirePortal("admin");
  if (!canManage(me.agency_roles)) notFound();
  const id = (await params).id;
  const data = await getApi<{
    event: Row;
    runs: Row[];
    jobs: Row[];
    receipts: Row[];
    deliveries: Row[];
  }>("/admin/outbox/" + id);
  if (!data) notFound();
  return (
    <article className="space-y-4">
      <Link href="/admin/automation">Automation activity</Link>
      <h2>{data.event.kind}</h2>
      <p className="break-all">
        Event {id} · {data.event.status}
      </p>
      {data.event.retryable && (
        <OperationForm
          path={"/admin/outbox/" + id + "/retry"}
          label="Queue retry"
        />
      )}
      {(
        [
          ["Workflow attempts", data.runs],
          ["Generation jobs", data.jobs],
          ["Processing receipts", data.receipts],
          ["Delivery attempts", data.deliveries],
        ] as const
      ).map(([name, rows]) => (
        <section key={name}>
          <h3>{name}</h3>
          {rows.length === 0 && <p>No records.</p>}
          {rows.map((r) => (
            <dl
              key={String(r.id)}
              className="my-2 grid gap-2 rounded-lg border p-4 md:grid-cols-3"
            >
              {Object.entries(r)
                .filter(([, v]) => v !== null && typeof v !== "boolean")
                .map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-sm text-slate-600">
                      {k === "execution"
                        ? "n8n execution"
                        : k.replaceAll("_", " ")}
                    </dt>
                    <dd className="break-all">{v}</dd>
                  </div>
                ))}
            </dl>
          ))}
        </section>
      ))}
    </article>
  );
}
