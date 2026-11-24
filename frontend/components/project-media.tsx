import Link from "next/link";
import { getApi } from "@/lib/server-api";
import { MediaCard, type MediaAsset } from "@/components/media-card";
import { ProjectMediaUpload } from "@/components/project-media-upload";
type FileRow = { id: string; file_name: string; mime_type: string; cover_file_id?: string | null };
type Release = {
  id: string;
  title: string;
  history: { id: string; number: number; files: MediaAsset[] }[];
};
export async function ProjectMedia({
  project,
  portal,
  page = 1,
}: {
  project: string;
  portal: "agency" | "client";
  page?: number;
}) {
  const query = "?portal=" + portal + "&project_id=" + project;
  const [files, releases] = await Promise.all([
    getApi<FileRow[]>("/files" + query + "&page=" + page),
    getApi<Release[]>("/approvals" + query),
  ]);
  const images = (files || []).filter((f) =>
    ["image/png", "image/jpeg", "video/mp4"].includes(f.mime_type),
  );
  const revisions = (releases || []).flatMap((item) =>
    item.history.flatMap((revision) =>
      revision.files
        .filter((f) => ["image/png", "image/jpeg", "video/mp4"].includes(f.mime_type || ""))
        .map((file) => ({
          file,
          title: item.title,
          number: revision.number,
          revision: revision.id,
        })),
    ),
  );
  return (
    <section
      aria-labelledby="project-media"
      className="space-y-5 border-t border-border pt-6"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 id="project-media">Creative assets</h3>
          <p className="text-sm text-slate-600">
            Project images, videos and deliverable revisions
          </p>
        </div>
        <Link
          className="text-primary underline"
          href={
            (portal === "agency" ? "/admin" : "/client") +
            "/briefs?project=" +
            project
          }
        >
          Manage project files
        </Link>
      </header>
      <ProjectMediaUpload project={project} portal={portal} />
      <h4 className="font-medium">Project media</h4>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {images.map((f) => (
          <MediaCard
            key={f.id}
            asset={{ id: f.id, name: f.file_name, mime_type: f.mime_type, cover_file_id: f.cover_file_id }}
            portal={portal}
          />
        ))}
      </div>
      {!images.length && (
        <p className="text-sm text-slate-600">
          No project media on this page.
        </p>
      )}
      <nav aria-label="Media pages" className="flex gap-4">
        {page > 1 && (
          <Link href={"?media_page=" + (page - 1) + "#project-media"}>
            Previous files
          </Link>
        )}
        {files?.length === 50 && (
          <Link href={"?media_page=" + (page + 1) + "#project-media"}>
            More files
          </Link>
        )}
      </nav>
      <h4 className="font-medium">Deliverable media</h4>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {revisions.map((r) => (
          <MediaCard
            key={r.revision + r.file.id}
            asset={r.file}
            portal={portal}
            caption={r.title + " · Revision " + r.number}
          />
        ))}
      </div>
      {!revisions.length && (
        <p className="text-sm text-slate-600">
          No deliverable media available.
        </p>
      )}
    </section>
  );
}
