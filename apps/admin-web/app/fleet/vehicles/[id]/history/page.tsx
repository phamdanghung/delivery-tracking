import FleetConsole from "../../../console";
export default async function History({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <FleetConsole view="history" vehicleId={(await params).id} />;
}
