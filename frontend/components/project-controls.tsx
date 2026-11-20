import { OperationForm } from "@/components/operation-form";
import type { Project, Milestone, Person, Task } from "@/lib/projects";
export function Choices({
  name,
  label,
  values,
  value,
}: {
  name: string;
  label: string;
  values: string[];
  value?: string;
}) {
  return (
    <label>
      {label}
      <select name={name} defaultValue={value}>
        {values.map((s) => (
          <option key={s} value={s}>
            {s.replaceAll("_", " ")}
          </option>
        ))}
      </select>
    </label>
  );
}
export function ProjectFields({ project }: { project?: Project }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label>
        Project name
        <input
          name="name"
          required
          maxLength={200}
          defaultValue={project?.name}
        />
      </label>
      <label>
        Service type
        <input
          name="service_type"
          maxLength={100}
          defaultValue={project?.service_type || ""}
        />
      </label>
      <Choices
        name="status"
        label="Project status"
        values={[
          "draft",
          "planning",
          "in_progress",
          "in_review",
          "completed",
          "on_hold",
          "cancelled",
        ]}
        value={project?.status}
      />
      <Choices
        name="priority"
        label="Priority"
        values={["low", "medium", "high", "urgent"]}
        value={project?.priority || "medium"}
      />
      <label>
        Start date
        <input
          name="start_date"
          type="date"
          defaultValue={project?.start_date || ""}
        />
      </label>
      <label>
        Due date
        <input
          name="due_date"
          type="date"
          defaultValue={project?.due_date || ""}
        />
      </label>
      <label className="sm:col-span-2">
        Internal project description
        <textarea
          name="description"
          maxLength={5000}
          defaultValue={project?.description || ""}
        />
      </label>
    </div>
  );
}
export function MilestoneFields({ stage }: { stage?: Milestone }) {
  return (
    <>
      <label>
        Milestone name
        <input
          name="name"
          required
          maxLength={200}
          defaultValue={stage?.name}
        />
      </label>
      <label>
        Milestone due date
        <input
          type="date"
          name="due_date"
          defaultValue={stage?.due_date || ""}
        />
      </label>
      <Choices
        name="status"
        label="Milestone status"
        values={["pending", "in_progress", "blocked", "completed"]}
        value={stage?.status}
      />
      <label>
        <input
          className="mr-2 w-auto"
          type="checkbox"
          name="client_visible"
          defaultChecked={stage?.client_visible}
        />
        Release milestone to client
      </label>
    </>
  );
}
export function TaskFields({
  task,
  stages,
}: {
  task?: Task;
  stages: Milestone[];
}) {
  return (
    <>
      <label>
        Task title
        <input
          name="title"
          maxLength={200}
          required
          defaultValue={task?.title}
        />
      </label>
      <label>
        Internal task details
        <textarea
          name="description"
          maxLength={5000}
          defaultValue={task?.description || ""}
        />
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label>
          Task start date
          <input
            type="date"
            name="start_date"
            defaultValue={task?.start_date || ""}
          />
        </label>
        <label>
          Task deadline
          <input
            type="date"
            name="due_date"
            defaultValue={task?.due_date || ""}
          />
        </label>
        <Choices
          name="priority"
          label="Task priority"
          values={["low", "medium", "high", "urgent"]}
          value={task?.priority || "medium"}
        />
        <label>
          Related milestone
          <select name="milestone_id" defaultValue={task?.milestone_id || ""}>
            <option value="">None</option>
            {stages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
      </div>
    </>
  );
}
export function TaskCard({
  task,
  stages,
  members,
  manager,
}: {
  task: Task;
  stages: Milestone[];
  members: Person[];
  manager: boolean;
}) {
  const path = "/tasks/" + task.id;
  const available = members.filter(
    (p) => !task.assignee_ids.includes(p.user_id),
  );
  const closed = ["cancelled", "completed"].includes(task.status);
  const statuses = closed
    ? manager
      ? [task.status, "todo"]
      : [task.status]
    : [
        "todo",
        "in_progress",
        "in_review",
        "blocked",
        "completed",
        ...(manager ? ["cancelled"] : []),
      ];
  return (
    <article className="space-y-3 rounded-lg border border-border p-4">
      <h3>{task.title}</h3>
      <p>
        {task.status.replaceAll("_", " ")} · {task.due_date || "No deadline"}
      </p>
      <p>{task.description}</p>
      <OperationForm path={path} method="PATCH" label="Update task status">
        <Choices
          name="status"
          label="Task status"
          values={statuses}
          value={task.status}
        />
      </OperationForm>
      {manager && (
        <>
          <details>
            <summary>Edit task</summary>
            <OperationForm path={path} method="PATCH" label="Save task">
              <TaskFields task={task} stages={stages} />
            </OperationForm>
          </details>
          <ul>
            {members
              .filter((p) => task.assignee_ids.includes(p.user_id))
              .map((p) => (
                <li key={p.user_id}>
                  <OperationForm
                    path={path + "/assignees/" + p.user_id}
                    method="DELETE"
                    label={"Unassign " + p.full_name}
                  />
                </li>
              ))}
          </ul>
          {!!available.length && !closed && (
            <OperationForm path={path + "/assign"} label="Assign task">
              <label>
                Task assignee
                <select required name="user_id">
                  {available.map((p) => (
                    <option key={p.user_id} value={p.user_id}>
                      {p.full_name}
                    </option>
                  ))}
                </select>
              </label>
            </OperationForm>
          )}
        </>
      )}
    </article>
  );
}
