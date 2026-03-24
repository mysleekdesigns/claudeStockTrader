import type { BacktestRun } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

interface BacktestTableProps {
  runs: BacktestRun[];
}

export function BacktestTable({ runs }: BacktestTableProps) {
  const resultBadge = (result: string) => {
    switch (result) {
      case "pass":
        return <Badge variant="success">Pass</Badge>;
      case "fail":
        return <Badge variant="destructive">Fail</Badge>;
      case "overfit":
        return <Badge variant="default">Overfit</Badge>;
      default:
        return <Badge variant="outline">{result}</Badge>;
    }
  };

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Type</TableHead>
          <TableHead>Window</TableHead>
          <TableHead>Result</TableHead>
          <TableHead>Metrics</TableHead>
          <TableHead>Date</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell className="font-sans">{run.run_type.replace("_", " ")}</TableCell>
            <TableCell>{run.window_days}d</TableCell>
            <TableCell>{resultBadge(run.result)}</TableCell>
            <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">
              {run.metrics ? JSON.stringify(run.metrics).slice(0, 80) : "-"}
            </TableCell>
            <TableCell className="text-xs text-muted-foreground">
              {new Date(run.created_at).toLocaleDateString()}
            </TableCell>
          </TableRow>
        ))}
        {runs.length === 0 && (
          <TableRow>
            <TableCell colSpan={5} className="text-center text-muted-foreground">
              No backtest runs yet
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
