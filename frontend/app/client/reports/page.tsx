import { ReportList } from "@/components/reports";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  return (
    <ReportList
      portal="client"
      page={Math.max(1, Number((await searchParams).page) || 1)}
    />
  );
}
