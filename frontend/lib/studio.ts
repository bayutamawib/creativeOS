import type { Brief } from "./briefs";
export type Json =
  | string
  | number
  | boolean
  | null
  | Json[]
  | { [key: string]: Json };
export type Job = {
  id: string;
  generation_type: string;
  status: string;
  provider: string;
  model: string;
  prompt_version: string;
  attempt: number;
  output: Record<string, Json> | null;
  error_code: string | null;
  quality_findings: Record<string, Json> | null;
  direction_id: string | null;
  revision_id: string | null;
  parameters: {
    feedback?: string | null;
    target_count: number;
    channels: string[];
  };
};
export type Proposal = {
  id: string;
  decision: string;
  kind: string;
  payload: Record<string, Json>;
};
export type Item = {
  id: string;
  title: string;
  source_proposal_id: string;
  current_revision_id: string;
  revision_number: number;
  content: Record<string, Json>;
};
export type Studio = {
  brief: Brief;
  jobs: Job[];
  proposals: Proposal[];
  items: Item[];
  automation: {
    event: string;
    delivery: string;
    run: string | null;
    execution_id: string | null;
  }[];
  brand: Record<string, Json>;
  provider: string;
};
