import {
  ListFilters,
  listParams,
  type ListQuery,
} from "@/components/list-filters";
import { getApi, requirePortal } from "@/lib/server-api";
import { ProjectList } from "@/components/project-list";
import { ProjectFields } from "@/components/project-controls";
import { OperationForm } from "@/components/operation-form";
import { canManage, type Project } from "@/lib/projects";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<ListQuery>;
}) {
  const query = await searchParams,
    filters = listParams(query).toString();
  const me = await requirePortal("admin"),
    page = Math.max(1, Number(query.page) || 1);
  const rows = await getApi<Project[]>(
    "/projects?portal=agency&page=" + page + "&" + filters,
  );
  const clients = canManage(me.agency_roles)
    ? await getApi<{ id: string; company_name: string }[]>("/clients")
    : null;
  return (
    <div className="space-y-6">
      <h2>Agency projects</h2>
      {clients && (
        <details>
          <summary>Create project</summary>
          <OperationForm
            path="/projects"
            label="Create project"
            after="created-project"
          >
            <label>
              Client organization
              <select required name="client_id">
                {clients.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.company_name}
                  </option>
                ))}
              </select>
            </label>
            <ProjectFields />
          </OperationForm>
        </details>
      )}
      <ListFilters
        label="Find projects"
        query={query}
        statuses={[
          "draft",
          "planning",
          "in_progress",
          "in_review",
          "completed",
          "on_hold",
          "cancelled",
        ]}
      />
      <ProjectList
        filters={filters}
        portal="admin"
        page={page}
        rows={rows || []}
      />
    </div>
  );
}
