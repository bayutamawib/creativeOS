import { Button } from "@/components/ui/button";
export type ListQuery = { page?: string; q?: string; status?: string };
export function listParams(query: ListQuery) {
  const params = new URLSearchParams();
  if (query.q) params.set("q", query.q);
  if (query.status) params.set("status", query.status);
  return params;
}
export function ListFilters({
  query,
  statuses,
  label,
}: {
  query: ListQuery;
  statuses: string[];
  label: string;
}) {
  return (
    <form
      method="get"
      className="my-4 grid items-end gap-3 sm:grid-cols-[2fr_1fr_auto]"
    >
      <label>
        {label}
        <input type="search" name="q" maxLength={200} defaultValue={query.q} />
      </label>
      <label>
        Status
        <select name="status" defaultValue={query.status}>
          <option value="">All statuses</option>
          {statuses.map((s) => (
            <option key={s} value={s}>
              {s.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      <Button>Apply filters</Button>
    </form>
  );
}
