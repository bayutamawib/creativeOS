import Link from "next/link";
import { notFound } from "next/navigation";
import { getApi, requirePortal } from "@/lib/server-api";
import {
  canManage,
  type Person,
  type Project,
  type Milestone,
  type Task,
  type Progress,
} from "@/lib/projects";
import {
  ProjectFields,
  MilestoneFields,
  TaskFields,
  TaskCard,
} from "@/components/project-controls";
import { OperationForm } from "@/components/operation-form";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const me = await requirePortal("admin"),
    manager = canManage(me.agency_roles),
    id = encodeURIComponent((await params).id),
    path = "/projects/" + id;
  const project = await getApi<Project>(path + "?portal=agency");
  if (!project) notFound();
  const [stages, tasks, members, progress, staff] = await Promise.all([
    getApi<Milestone[]>(path + "/milestones?portal=agency"),
    getApi<Task[]>(path + "/tasks"),
    getApi<Person[]>(path + "/members"),
    getApi<Progress>(path + "/progress?portal=agency"),
    manager
      ? getApi<
          {
            id: string;
            full_name: string;
            is_active: boolean;
            roles: { is_active: boolean }[];
          }[]
        >("/agency/members")
      : null,
  ]);
  const available =
    staff?.filter(
      (s) =>
        s.is_active &&
        s.roles.some((r) => r.is_active) &&
        !members?.some((m) => s.id === m.user_id),
    ) || [];
  return (
    <div className="space-y-7">
      <Link href="/admin/projects">All projects</Link>
      <header>
        <h2>{project.name}</h2>
        <p>
          {project.status.replaceAll("_", " ")} ·{" "}
          {project.due_date || "No deadline"}
        </p>
        <p>{project.description}</p>
      </header>
      {manager && (
        <details>
          <summary>Project settings</summary>
          <OperationForm path={path} method="PATCH" label="Save project">
            <ProjectFields project={project} />
          </OperationForm>
          <div className="mt-4">
            <OperationForm
              path={path + "/archive"}
              after="archive"
              label="Archive project"
            />
          </div>
        </details>
      )}
      <section>
        <h3>Project team</h3>
        <ul className="space-y-2">
          {members?.map((m) => (
            <li key={m.user_id}>
              {manager ? (
                <OperationForm
                  path={path + "/members/" + m.user_id}
                  method="DELETE"
                  label={"Remove " + m.full_name}
                />
              ) : (
                m.full_name
              )}
            </li>
          ))}
        </ul>
        {manager && !!available.length && (
          <OperationForm path={path + "/members"} label="Add project member">
            <label>
              Agency member
              <select name="user_id">
                {available.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
              </select>
            </label>
          </OperationForm>
        )}
      </section>
      <section className="space-y-3">
        <h3>Milestones</h3>
        <p>
          {progress?.completed_milestones} of {progress?.total_milestones}{" "}
          complete · {progress?.percent}%
        </p>
        {stages?.map((s) => (
          <div key={s.id}>
            <strong>{s.name}</strong> · {s.status} ·{" "}
            {s.client_visible ? "Released" : "Internal"}
            {manager && (
              <details>
                <summary>Edit milestone</summary>
                <OperationForm
                  path={"/milestones/" + s.id}
                  method="PATCH"
                  label="Save milestone"
                >
                  <MilestoneFields stage={s} />
                </OperationForm>
              </details>
            )}
          </div>
        ))}
        {manager && (
          <details>
            <summary>Add milestone</summary>
            <OperationForm path={path + "/milestones"} label="Create milestone">
              <MilestoneFields />
            </OperationForm>
          </details>
        )}
      </section>
      <section className="space-y-4">
        <h3>Tasks</h3>
        {manager && (
          <details>
            <summary>Add task</summary>
            <OperationForm path={path + "/tasks"} label="Create task">
              <TaskFields stages={stages || []} />
            </OperationForm>
          </details>
        )}
        {tasks?.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            manager={manager}
            members={members || []}
            stages={stages || []}
          />
        ))}
      </section>
    </div>
  );
}
