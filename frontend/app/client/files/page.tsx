import Link from "next/link";
import { getApi, requirePortal } from "@/lib/server-api";
import type { Asset } from "@/lib/briefs";
type FileRow = Asset & {
  project_id: string;
  project_name: string;
  created_at: string;
  mime_type: string;
};
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  await requirePortal("client");
  const page = Math.max(1, Number((await searchParams).page) || 1);
  const files = await getApi<FileRow[]>("/files?portal=client&page=" + page);
  return (
    <div className="space-y-4">
      <h2>Project files</h2>
      <ul className="divide-y divide-border">
        {files?.map((f) => (
          <li key={f.id} className="py-3">
            <a
              className="font-semibold text-primary underline"
              href={"/api/v1/files/" + f.id + "/download?portal=client"}
            >
              {f.file_name}
            </a>
            <p>
              <Link href={"/client/briefs?project=" + f.project_id}>
                {f.project_name}
              </Link>{" "}
              · {f.category.replaceAll("_", " ")}
            </p>
            <p className="text-sm text-slate-600">
              {f.mime_type} · {Math.ceil(f.file_size / 1024)} KB · Uploaded{" "}
              {f.created_at.slice(0, 10)}
            </p>
          </li>
        ))}
      </ul>
      {!files?.length && <p>No shared files on this page.</p>}
      <nav className="flex gap-4">
        {page > 1 && <Link href={"?page=" + (page - 1)}>Previous</Link>}
        {files?.length === 50 && <Link href={"?page=" + (page + 1)}>Next</Link>}
      </nav>
    </div>
  );
}
