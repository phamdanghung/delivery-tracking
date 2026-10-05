import FleetConsole from "../../../fleet/console";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <FleetConsole
      view="deliveries"
      dispatchView="form"
      entityId={(await params).id}
    />
  );
}
