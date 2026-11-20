import { getApi, requirePortal } from "@/lib/server-api";
import { ReviewQueue, type ReviewItem } from "@/components/review-queue";
export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ item?: string }>;
}) {
  await requirePortal("client");
  const { item } = await searchParams;
  const items = await getApi<ReviewItem[]>("/approvals?portal=client");
  return (
    <ReviewQueue key={item} selected={item} items={items ?? []} client={true} />
  );
}
