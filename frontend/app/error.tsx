"use client";
import { Button } from "@/components/ui/button";

export default function PageError({ reset }: { reset: () => void }) {
  return (
    <section
      aria-labelledby="read-error"
      className="mx-auto max-w-xl space-y-4 p-6"
    >
      <h2 id="read-error">This page could not be loaded</h2>
      <p role="alert">Check your connection and try loading the page again.</p>
      <Button onClick={reset}>Reload page</Button>
    </section>
  );
}
