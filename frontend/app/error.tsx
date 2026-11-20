"use client";
import { Button } from "@/components/ui/button";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-xl space-y-5 px-6 py-16">
      <h1 className="text-2xl font-semibold">Workspace unavailable</h1>
      <p>
        We couldn’t load the workspace. Check your connection and try again.
      </p>
      <Button onClick={reset}>Try again</Button>
    </main>
  );
}
