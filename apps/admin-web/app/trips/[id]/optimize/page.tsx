import FleetConsole from "../../../fleet/console";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return (
    <FleetConsole
      view="trips"
      dispatchView="optimization"
      entityId={(await params).id}
    />
  );
}
