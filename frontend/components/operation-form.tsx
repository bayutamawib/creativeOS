"use client";
import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function OperationForm({
  path,
  method = "POST",
  label,
  after,
  children,
}: {
  path: string;
  method?: string;
  label: string;
  after?: "created-project" | "archive";
  children?: ReactNode;
}) {
  const [message, setMessage] = useState(""),
    [pending, setPending] = useState(false);
  const router = useRouter();
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data: Record<string, FormDataEntryValue | boolean | null> =
      Object.fromEntries(new FormData(form));
    for (const input of Array.from(form.elements)) {
      if (
        input instanceof HTMLInputElement &&
        input.type === "checkbox" &&
        input.name
      )
        data[input.name] = input.checked;
    }
    for (const key of Object.keys(data)) if (data[key] === "") data[key] = null;
    setPending(true);
    setMessage("");
    try {
      const result = await mutate(
        path,
        method,
        Object.keys(data).length ? data : undefined,
      );
      if (after === "created-project")
        router.push("/admin/projects/" + result.id);
      else if (after === "archive") router.push("/admin/projects");
      else {
        if (method === "POST") form.reset();
        setMessage("Saved");
      }
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Could not save changes");
    } finally {
      setPending(false);
    }
  }
  return (
    <form method="post" onSubmit={submit} className="space-y-3">
      {children}
      <div className="flex items-center gap-3">
        <Button disabled={pending}>{label}</Button>
        <span className="text-sm" role="status">
          {message}
        </span>
      </div>
    </form>
  );
}
