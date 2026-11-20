"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "@/lib/browser-api";
import { Button } from "@/components/ui/button";
export type Delegate = {
  membership_id: string;
  name: string;
  delegated: boolean;
};
export function Delegates({
  projectId,
  members,
}: {
  projectId: string;
  members: Delegate[];
}) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  async function change(member: Delegate) {
    try {
      await mutate(
        "/projects/" +
          projectId +
          "/approval-delegations/" +
          member.membership_id,
        member.delegated ? "DELETE" : "PUT",
      );
      setMessage("Approval authority updated");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Update failed");
    }
    router.refresh();
  }
  return (
    <div className="mt-5">
      <h4 className="font-medium">Project approval delegates</h4>
      {members.map((m) => (
        <div
          key={m.membership_id}
          className="mt-2 flex items-center justify-between gap-3 rounded-lg bg-background p-3"
        >
          <span>{m.name}</span>
          <Button variant="outline" size="sm" onClick={() => change(m)}>
            {m.delegated ? "Revoke authority" : "Grant authority"}
          </Button>
        </div>
      ))}
      {!members.length && <p>No eligible members.</p>}
      <p className="mt-2 text-sm" role="status">
        {message}
      </p>
    </div>
  );
}
