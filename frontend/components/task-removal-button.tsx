"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";

export function TaskRemovalButton({
  id,
  title,
  updatedAt,
}: {
  id: string;
  title: string;
  updatedAt: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  async function remove() {
    if (!window.confirm(`Remove “${title}” from the plan? Its activity history will remain.`)) return;
    setPending(true);
    setMessage("");
    try {
      await mutate(`/tasks/${id}`, "PATCH", {
        status: "cancelled",
        expected_updated_at: updatedAt,
      });
      setMessage("Removed from plan; history preserved");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Task could not be removed");
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button type="button" variant="outline" disabled={pending} onClick={remove}>
        Remove from plan
      </Button>
      <span role="status" className="text-sm">{message}</span>
    </div>
  );
}
