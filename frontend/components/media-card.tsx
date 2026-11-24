"use client";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/button";

export type MediaAsset = { id: string; name: string; mime_type?: string; cover_file_id?: string | null };
export function mediaUrl(
  id: string,
  portal: "agency" | "client",
  kind = "thumbnail",
) {
  return (
    "/api/v1/files/" + encodeURIComponent(id) + "/" + kind + "?portal=" + portal
  );
}

export function MediaCard({
  asset,
  portal,
  caption,
}: {
  asset: MediaAsset;
  portal: "agency" | "client";
  caption?: string;
}) {
  const modal = useRef<HTMLDialogElement>(null);
  const videoPlayer = useRef<HTMLVideoElement>(null);
  const [opened, setOpened] = useState(false);
  const [failed, setFailed] = useState(false);
  const image = ["image/png", "image/jpeg"].includes(asset.mime_type || "");
  const video = asset.mime_type === "video/mp4";
  return (
    <figure className="min-w-0 overflow-hidden rounded-xl border border-border bg-white">
      {image && (
        <button
          type="button"
          className="block w-full bg-slate-100 text-left"
          aria-label={"Preview " + asset.name}
          onClick={() => {
            setOpened(true);
            modal.current?.showModal();
          }}
        >
          {failed ? (
            <span className="flex aspect-[4/3] items-center justify-center p-4">
              Image unavailable
            </span>
          ) : (
            // Authenticated requests must bypass shared image optimization.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              className="aspect-[4/3] w-full object-cover"
              src={mediaUrl(asset.id, portal)}
              alt={asset.name}
              loading="lazy"
              onError={() => setFailed(true)}
            />
          )}
        </button>
      )}
      {video && (
        <button
          type="button"
          className="block w-full bg-slate-950 text-left text-white"
          aria-label={"Play " + asset.name}
          onClick={() => { setOpened(true); modal.current?.showModal(); }}
        >
          {asset.cover_file_id ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={mediaUrl(asset.cover_file_id, portal)} alt="" className="aspect-video w-full object-cover" />
          ) : <span className="flex aspect-video items-center justify-center">▶ Play video</span>}
          <span className="block px-3 py-2 text-sm">▶ Play video</span>
        </button>
      )}
      <figcaption className="space-y-1 p-3">
        <p className="break-words font-medium">{asset.name}</p>
        {caption && <p className="text-sm text-slate-600">{caption}</p>}
        <a
          className="text-sm text-primary underline"
          href={mediaUrl(asset.id, portal, "download")}
        >
          Download {asset.name}
        </a>
      </figcaption>
      {image && (
        <dialog
          ref={modal}
          aria-label={"Image preview " + asset.name}
          onClose={() => setOpened(false)}
          className="fixed inset-0 m-auto max-h-[92dvh] w-[min(64rem,94vw)] overflow-auto rounded-xl border border-border bg-white p-4 shadow-xl backdrop:bg-slate-950/70"
        >
          <header className="mb-3 flex items-start justify-between gap-3">
            <h3 className="break-all">{asset.name}</h3>
            <Button
              autoFocus
              variant="outline"
              onClick={() => modal.current?.close()}
            >
              Close preview
            </Button>
          </header>
          {opened && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={mediaUrl(asset.id, portal, "preview")}
              alt={asset.name}
              className="mx-auto max-h-[70dvh] max-w-full object-contain"
            />
          )}
          {caption && <p className="mt-3 text-sm">{caption}</p>}
        </dialog>
      )}
      {video && (
        <dialog
          ref={modal}
          aria-label={"Video preview " + asset.name}
          onClose={() => setOpened(false)}
          className="fixed inset-0 m-auto max-h-[92dvh] w-[min(64rem,94vw)] overflow-auto rounded-xl border border-border bg-white p-4 shadow-xl backdrop:bg-slate-950/70"
        >
          <header className="mb-3 flex items-start justify-between gap-3">
            <h3 className="break-all">{asset.name}</h3>
            <Button variant="outline" onClick={() => void videoPlayer.current?.requestFullscreen?.()}>Fullscreen</Button>
            <Button autoFocus variant="outline" onClick={() => modal.current?.close()}>Close preview</Button>
          </header>
          {opened && <video
            ref={videoPlayer}
            controls
            playsInline
            preload="metadata"
            aria-label={asset.name}
            className="max-h-[70dvh] w-full bg-black"
            poster={asset.cover_file_id ? mediaUrl(asset.cover_file_id, portal) : undefined}
            src={mediaUrl(asset.id, portal, "stream")}
          />}
          {caption && <p className="mt-3 text-sm">{caption}</p>}
        </dialog>
      )}
    </figure>
  );
}

export function ProjectThumbnail({
  id,
  video = false,
  name,
  portal,
}: {
  id?: string | null;
  video?: boolean;
  name: string;
  portal: "agency" | "client";
}) {
  const [failed, setFailed] = useState(false);
  if (id && !failed)
    return (
      <div className="relative">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={mediaUrl(id, portal)}
        alt={name + (video ? " project video cover" : " project image")}
        loading="lazy"
        className="aspect-[16/9] w-full object-cover"
        onError={() => setFailed(true)}
      />
      {video && <span aria-hidden="true" className="absolute inset-0 flex items-center justify-center"><span className="rounded-full bg-slate-950/75 px-5 py-3 text-xl text-white">▶</span></span>}
      </div>
    );
  return (
    <div
      role="img"
      aria-label={name + " project artwork"}
      className="relative flex aspect-[16/9] items-end overflow-hidden bg-gradient-to-br from-indigo-950 via-indigo-700 to-rose-300 p-5"
    >
      <span
        aria-hidden="true"
        className="absolute -right-6 -top-12 h-52 w-52 rounded-full border-[24px] border-white/15"
      />
      <span aria-hidden="true" className="text-5xl font-semibold text-white/90">
        {name.slice(0, 1).toUpperCase()}
      </span>
      {video && <span aria-hidden="true" className="absolute inset-0 flex items-center justify-center"><span className="rounded-full bg-slate-950/75 px-5 py-3 text-xl text-white">▶</span></span>}
    </div>
  );
}
