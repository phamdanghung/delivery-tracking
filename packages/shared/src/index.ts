/** Operations endpoints only; business API contracts remain in openapi/openapi.yaml. */
export { designTokens } from "./design-tokens";
export type HealthResponse = {status: "ok"};
export type ReadinessResponse = {
  status: "ready" | "not_ready";
  checks: Record<"database" | "redis" | "storage" | "traccar", boolean>;
};
