import type { OptimisedParams } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ParamsViewerProps {
  params: OptimisedParams[];
}

export function ParamsViewer({ params }: ParamsViewerProps) {
  const activeParams = params.filter((p) => p.is_active);

  if (activeParams.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>Active Parameters</CardTitle></CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">Using default parameters</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {activeParams.map((p) => (
        <Card key={p.id}>
          <CardHeader>
            <CardTitle>{p.strategy_name}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1">
              {Object.entries(p.params).map(([key, value]) => (
                <div key={key} className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="font-mono">{String(value)}</span>
                </div>
              ))}
            </div>
            {p.validated_at && (
              <p className="mt-2 text-[10px] text-muted">
                Validated: {new Date(p.validated_at).toLocaleString()}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
