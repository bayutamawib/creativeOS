export type Asset = {
  id: string;
  file_name: string;
  visibility: string;
  category: string;
  file_size: number;
};
export type Brief = {
  id: string;
  project_id: string;
  title: string;
  objective: string;
  status: string;
  version: number;
  feedback: string | null;
  snapshot_id: string | null;
  target_audience: string | null;
  key_message: string | null;
  content_type: string | null;
  tone_of_voice: string | null;
  references: { type: string; value: string }[];
  restrictions: string | null;
  additional_context: string | null;
  preferred_channels: string[];
  requested_item_count: number;
  target_timeline: string | null;
  attachment_ids: string[];
};
export const channels = [
  "Instagram",
  "TikTok",
  "Facebook",
  "LinkedIn",
  "YouTube",
  "Website",
  "Email",
  "X",
];
