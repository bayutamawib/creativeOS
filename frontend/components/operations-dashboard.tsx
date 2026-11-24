import Link from "next/link";

export type AgencyDashboardData = {
  active_projects: number;
  open_tasks: number;
  overdue_tasks: number;
  task_completion_rate: number;
  workload: { assignee: string; open_tasks: number; overdue_tasks: number }[];
  projects: { id: string; name: string; status: string; progress: number }[];
};

export type ClientDashboardData = {
  projects: {
    id: string;
    name: string;
    status: string;
    progress: { percent: number; completed_milestones: number; total_milestones: number };
    next_milestone: string | null;
  }[];
  briefs: { id: string; project_id: string; title: string; status: string }[];
  milestones: { project_id: string; name: string; status: string; due_date: string | null }[];
  pending_approvals: { id: string; project_id: string; title: string }[];
};

function Kpi({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-white p-4 shadow-sm">
      <p className="text-sm text-slate-600">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-slate-900">{value}</p>
    </div>
  );
}

export function AgencyOperationsDashboard({ data }: { data: AgencyDashboardData }) {
  return (
    <section aria-labelledby="operations-title" className="space-y-6">
      <div>
        <h2 id="operations-title">Operations overview</h2>
        <p className="mt-1 text-sm text-slate-600">Current workload within your authorized project scope.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Active projects" value={data.active_projects} />
        <Kpi label="Open tasks" value={data.open_tasks} />
        <Kpi label="Overdue tasks" value={data.overdue_tasks} />
        <Kpi label="Task completion rate" value={`${data.task_completion_rate}%`} />
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <section className="overflow-hidden rounded-xl border border-border bg-white">
          <h3 className="p-4">Team workload</h3>
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-100"><tr><th className="px-4 py-3">Assignee</th><th className="px-4 py-3">Open</th><th className="px-4 py-3">Overdue</th></tr></thead>
            <tbody>{data.workload.map((row) => <tr key={row.assignee} className="border-t border-border"><th className="px-4 py-3 font-medium">{row.assignee}</th><td className="px-4 py-3">{row.open_tasks}</td><td className="px-4 py-3">{row.overdue_tasks}</td></tr>)}</tbody>
          </table>
          {!data.workload.length && <p className="p-4 text-sm text-slate-600">No open assigned work.</p>}
        </section>
        <section className="rounded-xl border border-border bg-white p-4">
          <h3>Project progress</h3>
          <ul className="mt-3 max-h-[28rem] space-y-4 overflow-y-auto pr-2">{data.projects.map((project) => <li key={project.id}><div className="flex min-w-0 items-start justify-between gap-3"><Link className="min-w-0 font-medium [overflow-wrap:anywhere]" href={`/admin/projects/${project.id}`}>{project.name}</Link><span className="shrink-0 whitespace-nowrap text-sm tabular-nums">{project.progress}% milestones</span></div><progress className="mt-2 w-full" value={project.progress} max={100} aria-label={`${project.name} milestone progress`} /><p className="text-xs text-slate-500">Project lifecycle: {project.status.replaceAll("_", " ")}</p></li>)}</ul>
          {!data.projects.length && <p className="mt-3 text-sm text-slate-600">No active projects.</p>}
        </section>
      </div>
    </section>
  );
}

export function ClientOperationsDashboard({ data }: { data: ClientDashboardData }) {
  return (
    <section aria-labelledby="client-operations-title" className="space-y-6">
      <div>
        <h3 id="client-operations-title">Project overview</h3>
        <p className="mt-1 text-sm text-slate-600">Shared progress, requirements, and decisions for your organization.</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {data.projects.map((project) => (
          <article key={project.id} className="rounded-xl border border-border bg-white p-4">
            <div className="flex min-w-0 items-start justify-between gap-3"><Link className="min-w-0 font-semibold [overflow-wrap:anywhere]" href={`/client/projects/${project.id}`}>{project.name}</Link><span className="shrink-0 whitespace-nowrap tabular-nums">{project.progress.percent}% milestones</span></div>
            <progress className="mt-3 w-full" value={project.progress.percent} max={100} aria-label={`${project.name} progress`} />
            <p className="mt-2 text-sm text-slate-600">{project.progress.completed_milestones} of {project.progress.total_milestones} milestones complete</p>
            <p className="text-sm text-slate-600">Project lifecycle: {project.status.replaceAll("_", " ")}</p>
            <p className="text-sm text-slate-600">Next: {project.next_milestone ?? "No upcoming milestone"}</p>
          </article>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <section><h3>Brief requirements</h3><ul className="mt-3 space-y-2">{data.briefs.map((brief) => <li key={brief.id} className="rounded-lg border border-border p-3"><Link href={`/client/briefs?project=${brief.project_id}&brief=${brief.id}`}>{brief.title}</Link><p className="text-sm text-slate-600">{brief.status.replaceAll("_", " ")}</p></li>)}</ul>{!data.briefs.length && <p className="mt-3 text-sm text-slate-600">No briefs yet.</p>}</section>
        <section><h3>Shared milestones</h3><ul className="mt-3 space-y-2">{data.milestones.map((milestone, index) => <li key={`${milestone.project_id}-${milestone.name}-${index}`} className="rounded-lg border border-border p-3"><p className="font-medium">{milestone.name}</p><p className="text-sm text-slate-600">{milestone.status.replaceAll("_", " ")} · {milestone.due_date ?? "No date"}</p></li>)}</ul>{!data.milestones.length && <p className="mt-3 text-sm text-slate-600">No milestones shared.</p>}</section>
        <section><h3>Pending approvals</h3><ul className="mt-3 space-y-2">{data.pending_approvals.map((approval) => <li key={approval.id} className="rounded-lg border border-border p-3"><Link href={`/client/approvals?item=${approval.id}`}>{approval.title}</Link></li>)}</ul>{!data.pending_approvals.length && <p className="mt-3 text-sm text-slate-600">No decisions awaiting you.</p>}</section>
      </div>
    </section>
  );
}
