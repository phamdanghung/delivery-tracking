import type { Metadata } from "next";
import CustomerTracking from "../../tracking/customer";

export const metadata: Metadata = {
  title: "Theo dõi giao hàng",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};
export const dynamic = "force-dynamic";
export default async function Page({
  params,
}: {
  params: Promise<{ trackingToken: string }>;
}) {
  const { trackingToken } = await params;
  return <CustomerTracking token={trackingToken} />;
}
