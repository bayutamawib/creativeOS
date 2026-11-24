"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { csrfHeaders } from "@/lib/browser-api";
import { Button } from "@/components/ui/button";

export function ProjectMediaUpload({
  project,
  portal,
}: {
  project: string;
  portal: "agency" | "client";
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const router = useRouter();
  async function uploadVideo(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const values = new FormData(form);
    const video = values.get("video");
    const cover = values.get("cover");
    if (!(video instanceof File)) return;
    const hasCover = cover instanceof File && cover.size > 0;
    if (video.type !== "video/mp4" || !video.name.toLowerCase().endsWith(".mp4") || !video.size || (hasCover && (!(["image/png", "image/jpeg"].includes(cover.type)) || cover.size > 5 * 1024 * 1024))) {
      setMessage("Choose an MP4 and an optional PNG or JPEG cover up to 5 MiB.");
      return;
    }
    setBusy(true);
    setMessage("");
    const visibility = String(values.get("visibility") || "client_visible");
    async function send(file: File) {
      const query = new URLSearchParams({ project_id: project, portal, file_name: file.name, category: "creative_asset", visibility });
      const response = await fetch("/api/v1/files/upload?" + query, { method: "POST", headers: { ...csrfHeaders(), "Content-Type": file.type }, body: file });
      const payload = await response.json();
      if (!response.ok) throw Error(payload.error?.message || "Upload failed");
      return payload.data.id as string;
    }
    try {
      const videoId = await send(video);
      if (hasCover) {
        const coverId = await send(cover);
        const response = await fetch("/api/v1/files/" + videoId + "/cover?portal=" + portal, {
          method: "PUT", headers: { ...csrfHeaders(), "Content-Type": "application/json" }, body: JSON.stringify({ cover_file_id: coverId }),
        });
        if (!response.ok) throw Error((await response.json()).error?.message || "Unable to assign cover");
      }
      form.reset();
      setMessage(hasCover ? "Video and cover uploaded" : "Video uploaded");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget,
      values = new FormData(form),
      file = values.get("image");
    if (!(file instanceof File) || !file.size) return;
    if (
      !["image/png", "image/jpeg"].includes(file.type) ||
      file.size > 5 * 1024 * 1024
    ) {
      setMessage("Choose a PNG or JPEG up to 5 MiB.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const query = new URLSearchParams({
        project_id: project,
        portal,
        file_name: file.name,
        category: "creative_asset",
        visibility: String(values.get("visibility") || "client_visible"),
      });
      const response = await fetch("/api/v1/files/upload?" + query, {
        method: "POST",
        headers: { ...csrfHeaders(), "Content-Type": file.type },
        body: file,
      });
      if (!response.ok)
        throw Error((await response.json()).error?.message || "Upload failed");
      form.reset();
      setMessage("Image uploaded");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3">
    <details>
      <summary>Upload project image</summary>
      <form onSubmit={upload} className="mt-3 max-w-md space-y-3">
        <label>
          Project image
          <input
            name="image"
            type="file"
            accept="image/png,image/jpeg"
            required
          />
        </label>
        {portal === "agency" && (
          <label>
            Image visibility
            <select name="visibility" defaultValue="internal">
              <option value="internal">Agency only</option>
              <option value="client_visible">Shared with client</option>
            </select>
          </label>
        )}
        <p className="text-sm text-slate-600">
          PNG or JPEG, up to 5 MiB. The newest image you can access appears on
          the project card.
        </p>
        <Button disabled={busy}>{busy ? "Uploading…" : "Upload image"}</Button>
        <p role="status">{message}</p>
      </form>
    </details>
    <details>
      <summary>Upload project video</summary>
      <form onSubmit={uploadVideo} className="mt-3 max-w-md space-y-3">
        <label>MP4 video<input name="video" type="file" accept="video/mp4,.mp4" required /></label>
        <label>Manual cover image (optional)<input name="cover" type="file" accept="image/png,image/jpeg" /></label>
        {portal === "agency" && <label>Video visibility<select name="visibility" defaultValue="internal"><option value="internal">Agency only</option><option value="client_visible">Shared with client</option></select></label>}
        <p className="text-sm text-slate-600">The server controls the MP4 size limit (50 MiB by default). Add a PNG or JPEG cover up to 5 MiB, or use the built-in artwork. Browser playback depends on the video codec.</p>
        <Button disabled={busy}>{busy ? "Uploading…" : "Upload video"}</Button>
        <p role="status">{message}</p>
      </form>
    </details>
    </div>
  );
}
