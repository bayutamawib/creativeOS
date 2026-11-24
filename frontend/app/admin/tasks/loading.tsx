export default function Loading() {
  return (
    <section aria-busy="true" aria-label="Loading tasks" className="space-y-5">
      <div className="h-9 w-40 animate-pulse rounded bg-slate-200 motion-reduce:animate-none" />
      <div className="h-40 animate-pulse rounded-xl bg-slate-200 motion-reduce:animate-none" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[1, 2, 3].map((item) => (
          <div key={item} className="h-64 animate-pulse rounded-xl bg-slate-200 motion-reduce:animate-none" />
        ))}
      </div>
      <span className="sr-only">Loading tasks</span>
    </section>
  );
}
