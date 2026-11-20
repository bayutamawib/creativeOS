"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function RunEvaluation() {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    router = useRouter();
  async function run() {
    setBusy(true);
    setError("");
    try {
      const row = await mutate("/admin/evaluations", "POST");
      router.push("/admin/evaluations/" + row.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Evaluation failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <Button disabled={busy} onClick={run}>
        {busy ? "Evaluating…" : "Run fixture evaluation"}
      </Button>
      <p role="status">{error}</p>
    </div>
  );
}
export type Rubric = Record<string, string | boolean | number>;
const dimensions = [
  "brief_alignment",
  "brand_alignment",
  "creative_usefulness",
  "actionability",
];
export function ReviewOutput({
  path,
  review,
}: {
  path: string;
  review: Rubric | null;
}) {
  const [message, status] = useState(""),
    [busy, setBusy] = useState(false),
    router = useRouter();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fields = new FormData(e.currentTarget);
    const data: Rubric = {};
    for (const k of dimensions) data[k] = Number(fields.get(k));
    for (const k of ["safety", "factual_grounding"])
      data[k] = fields.get(k) === "pass";
    data.disposition = String(fields.get("disposition"));
    setBusy(true);
    try {
      await mutate(path, "PUT", data);
      status("Review saved");
      router.refresh();
    } catch (e) {
      status(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-3">
      <h4>Human review</h4>
      <div className="grid gap-2 md:grid-cols-2">
        {dimensions.map((k) => (
          <label key={k}>
            {k.replaceAll("_", " ")}
            <select required name={k} defaultValue={String(review?.[k] ?? "")}>
              <option value="">Choose a score</option>
              {[
                "Unusable",
                "Major revision",
                "Meaningful revision",
                "Minor edits",
                "Ready after review",
              ].map((v, i) => (
                <option key={v} value={i + 1}>
                  {i + 1} · {v}
                </option>
              ))}
            </select>
          </label>
        ))}
        {["factual_grounding", "safety"].map((k) => (
          <label key={k}>
            {k.replaceAll("_", " ")}
            <select
              required
              name={k}
              defaultValue={review ? (review[k] ? "pass" : "fail") : ""}
            >
              <option value="">Choose a finding</option>
              <option value="pass">Pass</option>
              <option value="fail">Fail</option>
            </select>
          </label>
        ))}
        <label>
          Review decision
          <select
            required
            name="disposition"
            defaultValue={String(review?.disposition ?? "")}
          >
            <option value="">Choose a decision</option>
            <option value="accepted">Accept</option>
            <option value="revision_required">Requires revision</option>
          </select>
        </label>
      </div>
      <Button disabled={busy}>Save human review</Button>
      <p role="status">{message}</p>
    </form>
  );
}
