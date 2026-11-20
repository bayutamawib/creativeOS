import { BriefPage, type BriefQuery } from "@/components/brief-page";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<BriefQuery>;
}) {
  return <BriefPage query={await searchParams} portal="client" />;
}
