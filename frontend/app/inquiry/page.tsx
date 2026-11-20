import Link from "next/link";
import { Inquiry } from "@/components/inquiry";
export default function Page() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/login">Workspace sign in</Link>
      <h1 className="my-6 text-4xl font-semibold">Start a project</h1>
      <section className="rounded-xl border border-border bg-white p-6">
        <Inquiry />
      </section>
    </main>
  );
}
