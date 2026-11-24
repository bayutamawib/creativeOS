import Link from "next/link";

export type ProjectActivity = {
  id: string;
  type: string;
  occurred_at: string;
  actor: string;
  description: string;
};

export type ProjectActivityPage = {
  items: ProjectActivity[];
  page: number;
  has_more: boolean;
  timezone: string;
};

function href(page: number, mediaPage?: string) {
  const query = new URLSearchParams({ activity_page: String(page), timeline: "history" });
  if (mediaPage) query.set("media_page", mediaPage);
  return `?${query}#project-activity`;
}

export function ProjectActivityTimeline({
  activity,
  mediaPage,
}: {
  activity: ProjectActivityPage;
  mediaPage?: string;
}) {
  const formatter = new Intl.DateTimeFormat("en", {
    timeZone: activity.timezone,
    dateStyle: "medium",
    timeStyle: "short",
  });
  return (
    <section id="project-activity" aria-labelledby="project-activity-title" className="space-y-4">
      <div>
        <h3 id="project-activity-title">Activity timeline</h3>
        <p className="mt-1 text-sm text-slate-600">Newest project activity appears first.</p>
      </div>
      {!activity.items.length && (
        <p className="rounded-lg border border-dashed border-border p-6 text-sm text-slate-600">
          No activity is available for this project.
        </p>
      )}
      {!!activity.items.length && (
        <ol className="relative ml-2 border-l border-slate-300">
          {activity.items.map((event) => (
            <li key={event.id} className="relative pb-6 pl-6 last:pb-0">
              <span
                aria-hidden="true"
                className="absolute -left-1.5 top-1.5 h-3 w-3 rounded-full border-2 border-white bg-primary"
              />
              <p className="font-medium text-slate-900">{event.description}</p>
              <p className="mt-1 text-sm text-slate-600">
                {event.actor} ·{" "}
                <time dateTime={event.occurred_at}>
                  {formatter.format(new Date(event.occurred_at))}
                </time>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {event.type.replaceAll("_", " ").replaceAll(".", " · ")}
              </p>
            </li>
          ))}
        </ol>
      )}
      <nav aria-label="Activity pages" className="flex gap-4 text-sm">
        {activity.page > 1 && (
          <Link href={href(activity.page - 1, mediaPage)}>Newer activity</Link>
        )}
        {activity.has_more && (
          <Link href={href(activity.page + 1, mediaPage)}>Older activity</Link>
        )}
      </nav>
    </section>
  );
}
