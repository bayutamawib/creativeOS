"use client";
import { useRef, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
type Asset = { id: string; name: string };
type Revision = {
  files: Asset[];
  id: string;
  number: number;
  content: Record<string, unknown>;
};
export type ReviewItem = {
  available_files: Asset[];
  id: string;
  title: string;
  status: string;
  revision_id: string;
  revision_number: number;
  history: Revision[];
  actions: string[];
  feedback: { revision_id: string; message: string; visibility: string }[];
};
const labels: Record<string, string> = {
  "submit-for-internal-review": "Submit for Internal Review",
  "approve-and-release": "Approve & Release to Client",
  "request-internal-changes": "Request Internal Changes",
  "client-approval": "Approve revision",
  "request-revision": "Request revision",
};
export function ReviewQueue({
  items,
  selected,
  client,
}: {
  items: ReviewItem[];
  selected?: string;
  client: boolean;
}) {
  const item =
    items.find((i) => i.id === selected) ?? (!selected ? items[0] : undefined);
  const [status, setStatus] = useState("all"),
    [msg, setMsg] = useState(""),
    [feedback, setFeedback] = useState(""),
    [busy, setBusy] = useState(false);
  const [refreshing, startTransition] = useTransition();
  const dialog = useRef<HTMLDialogElement>(null),
    router = useRouter();
  const [confirm, setConfirm] = useState<{
    id: string;
    revision: string;
    title: string;
    number: number;
  } | null>(null);
  async function post(
    action: string,
    fields: object,
    target = item?.id,
    rid = item?.revision_id,
  ) {
    if (!target || !rid) return;
    setBusy(true);
    setMsg("");
    try {
      await mutate(
        "/content-items/" +
          target +
          "/" +
          action +
          "?portal=" +
          (client ? "client" : "agency"),
        "POST",
        { revision_id: rid, ...fields },
      );
      setFeedback("");
      setMsg("Saved");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Unable to save");
    } finally {
      setBusy(false);
      startTransition(() => router.refresh());
    }
  }
  const disabled = busy || refreshing;
  return (
    <div className="space-y-5">
      <h2>{client ? "Client approvals" : "Content approvals"}</h2>
      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <aside className="space-y-3">
          <label>
            Filter reviews
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All statuses</option>
              {[...new Set(items.map((i) => i.status))].map((s) => (
                <option key={s} value={s}>
                  {s.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          <ul>
            {items
              .filter((i) => status === "all" || i.status === status)
              .map((i) => (
                <li className="py-2 border-b border-border" key={i.id}>
                  <Link href={"?item=" + i.id}>{i.title}</Link>
                  <p className="text-xs">{i.status.replaceAll("_", " ")}</p>
                </li>
              ))}
          </ul>
        </aside>
        {item ? (
          <article className="space-y-4">
            <header>
              <h3>{item.title}</h3>
              <p>
                Revision {item.revision_number} ·{" "}
                {item.status.replaceAll("_", " ")}
              </p>
            </header>
            {item.history.map((r, index) => (
              <details key={r.id} open={index === 0}>
                <summary>Revision {r.number}</summary>
                <dl className="p-3 space-y-2">
                  {Object.entries(r.content).map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs uppercase">
                        {k.replaceAll("_", " ")}
                      </dt>
                      <dd>{Array.isArray(v) ? v.join(", ") : String(v)}</dd>
                    </div>
                  ))}
                </dl>
                {r.files.map((f) => (
                  <p key={f.id}>
                    <a
                      href={
                        "/api/v1/files/" +
                        f.id +
                        "/download?portal=" +
                        (client ? "client" : "agency")
                      }
                    >
                      {f.name}
                    </a>
                  </p>
                ))}
              </details>
            ))}
            {!client && (
              <details>
                <summary>Edit draft</summary>
                <form
                  key={item.revision_id}
                  className="space-y-3"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void post("revisions", {
                      headline: f.get("headline"),
                      caption: f.get("caption"),
                      attachment_ids: f.getAll("file"),
                    });
                  }}
                >
                  <label>
                    Headline
                    <input
                      name="headline"
                      required
                      maxLength={200}
                      defaultValue={String(
                        item.history[0].content.headline ?? item.title,
                      )}
                    />
                  </label>
                  <label>
                    Caption
                    <textarea
                      name="caption"
                      required
                      maxLength={5000}
                      defaultValue={String(
                        item.history[0].content.caption ??
                          item.history[0].content.draft_caption ??
                          "",
                      )}
                    />
                  </label>
                  {item.available_files.map((f) => (
                    <label key={f.id}>
                      <input
                        name="file"
                        value={f.id}
                        type="checkbox"
                        defaultChecked={item.history[0].files.some(
                          (a) => a.id === f.id,
                        )}
                      />
                      {f.name}
                    </label>
                  ))}
                  <Button disabled={disabled}>Save new revision</Button>
                </form>
              </details>
            )}
            <h4>Feedback</h4>
            {item.feedback.map((f, i) => (
              <p key={i}>
                Revision{" "}
                {item.history.find((r) => r.id === f.revision_id)?.number} ·{" "}
                {f.visibility.replaceAll("_", " ")} · {f.message}
              </p>
            ))}
            <label>
              {client ? "Client feedback" : "Internal notes"}
              <textarea
                value={feedback}
                maxLength={5000}
                onChange={(e) => setFeedback(e.target.value)}
              />
            </label>
            <div className="flex flex-wrap gap-2">
              <Button
                disabled={disabled || !feedback.trim()}
                onClick={() =>
                  void post("feedback", {
                    message: feedback,
                    visibility: client ? "client_visible" : "internal",
                  })
                }
              >
                Add feedback
              </Button>
              {item.actions.map((a) => (
                <Button
                  key={a}
                  disabled={
                    disabled || (a.startsWith("request-") && !feedback.trim())
                  }
                  onClick={() => {
                    if (a === "approve-and-release") {
                      setConfirm({
                        id: item.id,
                        revision: item.revision_id,
                        title: item.title,
                        number: item.revision_number,
                      });
                      dialog.current?.showModal();
                    } else void post(a, { comments: feedback || null });
                  }}
                >
                  {labels[a]}
                </Button>
              ))}
            </div>
          </article>
        ) : (
          <p>No deliverable available.</p>
        )}
      </div>
      <dialog
        ref={dialog}
        aria-labelledby="release-title"
        className="m-auto max-w-md rounded-lg p-6 shadow-lg backdrop:bg-black/40"
      >
        <h3 id="release-title">Approve &amp; Release to Client</h3>
        <p>
          {confirm?.title} · Revision {confirm?.number}
        </p>
        <p className="my-4">
          This exact revision will become visible to the client.
        </p>
        <div className="flex gap-3">
          <Button autoFocus onClick={() => dialog.current?.close()}>
            Cancel
          </Button>
          <Button
            onClick={() => {
              dialog.current?.close();
              if (confirm)
                void post(
                  "approve-and-release",
                  { comments: feedback || null },
                  confirm.id,
                  confirm.revision,
                );
            }}
          >
            Confirm &amp; Release
          </Button>
        </div>
      </dialog>
      <p role="status">{msg}</p>
    </div>
  );
}
