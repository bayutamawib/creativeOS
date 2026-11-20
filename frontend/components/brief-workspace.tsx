"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { mutate, csrfHeaders } from "@/lib/browser-api";
import { channels, type Asset, type Brief } from "@/lib/briefs";

type Props = {
  project: string;
  portal: "client" | "agency";
  canSubmit: boolean;
  brief: Brief | null;
  files: Asset[];
};
export function BriefWorkspace({
  project,
  portal,
  canSubmit,
  brief,
  files,
}: Props) {
  const router = useRouter(),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const query = "?portal=" + portal,
    base =
      (portal === "client" ? "/client" : "/admin") +
      "/briefs?project=" +
      project;
  const editable =
    !brief ||
    ["draft", "revision_requested", "approved"].includes(brief.status);
  async function run(job: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await job();
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }
  function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const body = {
      title: d.get("title"),
      objective: d.get("objective"),
      target_audience: d.get("target_audience") || null,
      key_message: d.get("key_message") || null,
      content_type: d.get("content_type") || null,
      tone_of_voice: d.get("tone_of_voice") || null,
      preferred_channels: d.getAll("channel"),
      requested_item_count: Number(d.get("count")),
      target_timeline: d.get("timeline") || null,
      restrictions: d.get("restrictions") || null,
      additional_context: d.get("additional_context") || null,
      references: String(d.get("references") || "")
        .split(/\s+/)
        .filter(Boolean)
        .map((value) => ({ type: "url", value })),
      attachment_ids: d.getAll("attachment"),
    };
    void run(async () => {
      const r = brief
        ? await mutate("/briefs/" + brief.id + query, "PATCH", {
            ...body,
            expected_version: brief.version,
          })
        : await mutate(
            "/projects/" + project + "/briefs" + query,
            "POST",
            body,
          );
      router.push(base + "&brief=" + r.id);
      setMessage("Draft saved");
    });
  }
  function act(action: string, feedback?: string) {
    if (!brief) return;
    void run(async () => {
      await mutate("/briefs/" + brief.id + "/" + action, "POST", {
        expected_version: brief.version,
        feedback: feedback || null,
      });
      setMessage("Review status updated");
    });
  }
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      d = new FormData(form),
      file = d.get("file");
    if (!(file instanceof File)) return;
    await run(async () => {
      const search = new URLSearchParams({
        project_id: project,
        portal,
        file_name: file.name,
        visibility: String(d.get("visibility") || "client_visible"),
        category: String(d.get("category")),
      });
      const res = await fetch("/api/v1/files/upload?" + search, {
        method: "POST",
        headers: {
          ...csrfHeaders(),
          "Content-Type": file.type || "application/octet-stream",
        },
        body: file,
      });
      if (!res.ok)
        throw new Error((await res.json()).error?.message || "Upload failed");
      form.reset();
      setMessage("File uploaded");
    });
  }
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border p-4">
        <h3>Project files</h3>
        <ul>
          {files.map((f) => (
            <li key={f.id}>
              <a
                className="text-primary underline"
                href={"/api/v1/files/" + f.id + "/download" + query}
              >
                {f.file_name}
              </a>{" "}
              · {f.visibility === "internal" ? "Agency only" : "Shared"} ·{" "}
              {Math.ceil(f.file_size / 1024)} KB
            </li>
          ))}
        </ul>
        <details className="mt-3">
          <summary>Upload project file</summary>
          <form onSubmit={upload} className="space-y-3">
            <label>
              File (PNG, JPEG or TXT, up to 5 MiB)
              <input
                type="file"
                required
                name="file"
                accept=".png,.jpg,.jpeg,.txt"
              />
            </label>
            <label>
              Category
              <select name="category">
                {[
                  "brief_attachment",
                  "brand_guideline",
                  "reference",
                  "creative_asset",
                  "other",
                ].map((c) => (
                  <option key={c} value={c}>
                    {c.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            {portal === "agency" && (
              <label>
                Visibility
                <select name="visibility">
                  <option value="internal">Agency only</option>
                  <option value="client_visible">Shared with client</option>
                </select>
              </label>
            )}
            <Button disabled={busy}>Upload file</Button>
          </form>
        </details>
      </section>
      <h3>{brief ? brief.title : "New creative brief"}</h3>
      {brief && (
        <p>
          Version {brief.version} · {brief.status.replaceAll("_", " ")}
          {brief.feedback && " · " + brief.feedback}
        </p>
      )}
      {editable && (
        <form
          onSubmit={save}
          className="space-y-4"
          key={brief?.id + "-" + brief?.version}
        >
          <label>
            Brief title
            <input
              name="title"
              defaultValue={brief?.title}
              required
              maxLength={200}
            />
          </label>
          <label>
            Campaign objective
            <textarea
              name="objective"
              defaultValue={brief?.objective}
              required
              maxLength={5000}
            />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                "target_audience",
                "key_message",
                "content_type",
                "tone_of_voice",
                "restrictions",
                "additional_context",
              ] as const
            ).map((k) => (
              <label key={k}>
                {k.replaceAll("_", " ")}
                <input name={k} defaultValue={brief?.[k] || ""} />
              </label>
            ))}
            <label>
              Requested items
              <input
                type="number"
                name="count"
                min={1}
                max={10}
                required
                defaultValue={brief?.requested_item_count || 3}
              />
            </label>
            <label>
              Target timeline
              <input
                name="timeline"
                defaultValue={brief?.target_timeline || ""}
              />
            </label>
          </div>
          <fieldset>
            <legend>Preferred channels</legend>
            <div className="flex flex-wrap gap-3">
              {channels.map((c) => (
                <label key={c}>
                  <input
                    type="checkbox"
                    name="channel"
                    value={c}
                    defaultChecked={brief?.preferred_channels.includes(c)}
                  />{" "}
                  {c}
                </label>
              ))}
            </div>
          </fieldset>
          <label>
            Reference URLs (one per line)
            <textarea
              name="references"
              defaultValue={brief?.references.map((r) => r.value).join("\n")}
            />
          </label>
          <fieldset>
            <legend>Brief attachments</legend>
            {files
              .filter((f) => f.visibility === "client_visible")
              .map((f) => (
                <label key={f.id}>
                  <input
                    type="checkbox"
                    name="attachment"
                    value={f.id}
                    defaultChecked={brief?.attachment_ids.includes(f.id)}
                  />{" "}
                  {f.file_name}
                </label>
              ))}
          </fieldset>
          <Button disabled={busy}>
            {brief?.status === "approved" ? "Save as new draft" : "Save draft"}
          </Button>
        </form>
      )}
      {brief && !editable && (
        <dl className="grid gap-3 sm:grid-cols-2">
          {Object.entries({
            Objective: brief.objective,
            Audience: brief.target_audience,
            Message: brief.key_message,
            Format: brief.content_type,
            Tone: brief.tone_of_voice,
            Restrictions: brief.restrictions,
            Context: brief.additional_context,
            Channels: brief.preferred_channels.join(", "),
            Items: brief.requested_item_count,
            Timeline: brief.target_timeline,
            References: brief.references.map((r) => r.value).join(", "),
            Attachments: files
              .filter((f) => brief.attachment_ids.includes(f.id))
              .map((f) => f.file_name)
              .join(", "),
          }).map(([k, v]) =>
            v ? (
              <div key={k}>
                <dt className="text-sm text-slate-600">{k}</dt>
                <dd>{v}</dd>
              </div>
            ) : null,
          )}
        </dl>
      )}
      {brief &&
        canSubmit &&
        ["draft", "revision_requested"].includes(brief.status) && (
          <Button disabled={busy} onClick={() => act("submit")}>
            Submit brief
          </Button>
        )}
      {portal === "agency" &&
        brief &&
        ["submitted", "under_review"].includes(brief.status) && (
          <div className="space-y-3">
            {brief.status === "submitted" && (
              <Button disabled={busy} onClick={() => act("start-review")}>
                Start review
              </Button>
            )}{" "}
            <Button disabled={busy} onClick={() => act("approve")}>
              Approve brief
            </Button>
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                const action = (
                  e.nativeEvent as SubmitEvent
                ).submitter?.getAttribute("value");
                act(
                  action || "request-revision",
                  String(new FormData(e.currentTarget).get("feedback")),
                );
              }}
            >
              <label>
                Review feedback
                <textarea name="feedback" required maxLength={5000} />
              </label>
              <Button disabled={busy} value="request-revision">
                Request clarification
              </Button>{" "}
              <Button disabled={busy} value="reject">
                Reject brief
              </Button>
            </form>
          </div>
        )}
      <p role="status">{message}</p>
    </div>
  );
}
