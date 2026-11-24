import type { TaskStatus } from "@/lib/task-statuses";

export type Project = {
  id: string;
  client_id: string;
  cover_file_id?: string | null;
  cover_video_id?: string | null;
  client_name?: string;
  name: string;
  status: string;
  priority?: string;
  description?: string | null;
  progress?: Progress;
  next_milestone?: string | null;
  service_type: string | null;
  due_date: string | null;
  start_date: string | null;
};
export type Milestone = {
  id: string;
  name: string;
  status: string;
  due_date: string | null;
  description?: string | null;
  client_visible?: boolean;
};
export type Task = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  due_date: string | null;
  start_date: string | null;
  milestone_id: string | null;
  priority: string;
  project_name: string;
  assignee_names: string[];
  assignee_ids: string[];
  updated_at: string;
  is_overdue: boolean;
};
export type Person = { user_id: string; full_name: string };
export type Progress = {
  percent: number;
  completed_milestones: number;
  total_milestones: number;
};
export function canManage(roles: string[]) {
  return roles.some((r) => r === "admin" || r === "agency_manager");
}
