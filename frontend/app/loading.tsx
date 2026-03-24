import { Skeleton } from "@/components/ui/skeleton";

export default function HomeLoading() {
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
      <div className="space-y-4">
        {/* Main chart skeleton */}
        <div className="rounded-lg border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <div className="flex items-center gap-2">
              <Skeleton className="h-5 w-20" />
              <div className="flex gap-1">
                {["15m", "1h", "4h", "1d"].map((tf) => (
                  <Skeleton key={tf} className="h-8 w-10 rounded-md" />
                ))}
              </div>
            </div>
            <Skeleton className="h-4 w-24" />
          </div>
          <Skeleton className="h-[400px] w-full" />
        </div>

        {/* Timeframe panels skeleton */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-lg border border-border bg-surface p-3">
              <Skeleton className="mb-2 h-4 w-12" />
              <Skeleton className="h-[120px] w-full" />
            </div>
          ))}
        </div>
      </div>

      {/* Signal feed skeleton */}
      <div className="h-[calc(100vh-8rem)] rounded-lg border border-border bg-surface">
        <div className="border-b border-border px-4 py-3">
          <Skeleton className="h-5 w-28" />
        </div>
        <div className="space-y-3 p-4">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="rounded-lg border border-border p-3">
              <div className="mb-2 flex items-center justify-between">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-5 w-14 rounded-full" />
              </div>
              <Skeleton className="mb-1 h-3 w-full" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
