import { cn } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface HealthCardProps {
  name: string;
  status: string;
}

export function HealthCard({ name, status }: HealthCardProps) {
  const isOk = status === "ok";
  const isDown = status === "unavailable" || status === "stopped";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{name}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "h-3 w-3 rounded-full",
              isOk ? "bg-bull" : isDown ? "bg-bear" : "bg-gold-500",
            )}
          />
          <span
            className={cn(
              "text-sm font-medium",
              isOk ? "text-bull" : isDown ? "text-bear" : "text-gold-400",
            )}
          >
            {status}
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
