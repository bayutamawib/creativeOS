"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { mutate } from "@/lib/browser-api";
export function SessionActions() {
  const [message, setMessage] = useState("");
  async function action(logout: boolean) {
    try {
      await mutate(logout ? "/auth/logout" : "/auth/refresh", "POST");
      if (logout) window.location.replace("/login");
      else setMessage("Session renewed");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Session request failed");
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="ghost" onClick={() => action(false)}>
        Renew session
      </Button>
      <Button variant="outline" onClick={() => action(true)}>
        Sign out
      </Button>
      <span role="status" className="text-sm">
        {message}
      </span>
    </div>
  );
}
