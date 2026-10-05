import FleetConsole from "../../fleet/console";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <FleetConsole
      view="deliveries"
      dispatchView="detail"
      entityId={(await params).id}
    />
  );
}
