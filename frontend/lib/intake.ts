export type Lead = {
  created_at: string;
  id: string;
  company_name: string;
  contact_name: string;
  email: string;
  status: string;
  service_interest: string | null;
  industry: string | null;
  phone: string | null;
  inquiry_message: string | null;
  notes: string | null;
  converted_client_id: string | null;
  assigned_to: string | null;
  source: string;
};
