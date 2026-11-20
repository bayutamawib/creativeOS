import { ReportDetail } from "@/components/reports";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <ReportDetail portal="admin" id={(await params).id} />;
}
