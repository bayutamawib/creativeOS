import Link from "next/link";
import { LoginForm } from "@/components/login-form";
export default function Login() {
  return (
    <main className="mx-auto grid min-h-[75vh] max-w-6xl content-center gap-12 px-6 py-16 md:grid-cols-2 md:items-center">
      <div className="border-l-4 border-primary pl-6">
        <p className="text-sm font-medium text-primary">Creative operations</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-6xl">
          Workspace
          <br />
          sign in
        </h1>
        <p className="mt-5 max-w-xs leading-relaxed text-slate-600">
          Use your agency or client account to open your workspace.
        </p>
        <Link
          className="mt-4 inline-block text-primary underline"
          href="/inquiry"
        >
          Submit a project inquiry
        </Link>
      </div>
      <LoginForm />
    </main>
  );
}
