"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";

export type TaskTemplate = {
  key: string;
  name: string;
  description: string;
  steps: { title: string; description: string; offset_days: number }[];
};

export function TaskTemplateApplication({
  project,
  templates,
  defaultStart,
}: {
  project: string;
  templates: TaskTemplate[];
  defaultStart?: string | null;
}) {
  const router = useRouter();
  const [selected, setSelected] = useState(templates[0]?.key ?? "");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const template = templates.find((row) => row.key === selected);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!template) return;
    const data = new FormData(event.currentTarget);
    if (
      !window.confirm(
        `Create ${template.steps.length} independent planned tasks from ${template.name}?`,
      )
    ) return;
    setPending(true);
    setMessage("");
    try {
      await mutate(`/projects/${project}/task-templates/apply`, "POST", {
        template: template.key,
        planning_start: data.get("planning_start"),
        confirmed: true,
      });
      setMessage(`${template.steps.length} planned tasks created`);
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Template could not be applied");
    } finally {
      setPending(false);
    }
  }

  if (!templates.length) return null;
  return (
    <details className="rounded-lg border border-border p-4">
      <summary>Apply task template</summary>
      <form onSubmit={submit} className="space-y-3">
        <label>
          Task template
          <select value={selected} onChange={(event) => setSelected(event.target.value)}>
            {templates.map((row) => <option key={row.key} value={row.key}>{row.name}</option>)}
          </select>
        </label>
        {template && (
          <div className="rounded-lg bg-slate-50 p-3 text-sm">
            <p>{template.description}</p>
            <ol className="mt-2 list-decimal space-y-1 pl-5">
              {template.steps.map((step) => (
                <li key={step.title}>{step.title} · day +{step.offset_days}</li>
              ))}
            </ol>
          </div>
        )}
        <label>
          Planning start date
          <input type="date" name="planning_start" required defaultValue={defaultStart ?? ""} />
        </label>
        <Button disabled={pending}>Apply template</Button>
        <p role="status" className="text-sm">{message}</p>
      </form>
    </details>
  );
}
