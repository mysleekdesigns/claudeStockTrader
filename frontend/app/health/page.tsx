import { getHealth } from "@/lib/api";
import { HealthCard } from "@/components/health/health-card";

export default async function HealthPage() {
  let health = null;

  try {
    health = await getHealth();
  } catch {
    // Backend may not be running
  }

  if (!health) {
    return (
      <div className="space-y-4">
        <h1 className="text-lg font-bold">System Health</h1>
        <div className="rounded-lg border border-bear bg-bear/10 p-6 text-center">
          <p className="text-sm font-medium text-bear">Backend Unreachable</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Cannot connect to the API server at localhost:8000
          </p>
        </div>
      </div>
    );
  }

  const services = [
    { name: "Overall", status: health.status },
    { name: "Database", status: health.database },
    { name: "Redis", status: health.redis },
    { name: "Data Feed", status: health.feed },
    { name: "Scheduler", status: health.scheduler },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-bold">System Health</h1>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {services.map((svc) => (
          <HealthCard key={svc.name} name={svc.name} status={svc.status} />
        ))}
      </div>
    </div>
  );
}
