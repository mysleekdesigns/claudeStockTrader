import type { StrategyPerformance } from "@/lib/types";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatPct } from "@/lib/utils";

interface StrategyTableProps {
  strategies: StrategyPerformance[];
}

export function StrategyTable({ strategies }: StrategyTableProps) {
  const sorted = [...strategies].sort((a, b) => b.sharpe_ratio - a.sharpe_ratio);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>#</TableHead>
          <TableHead>Strategy</TableHead>
          <TableHead>Win Rate</TableHead>
          <TableHead>Signals</TableHead>
          <TableHead>Avg RR</TableHead>
          <TableHead>Sharpe</TableHead>
          <TableHead>Max DD</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((s, i) => {
          const wrColor =
            s.win_rate > 0.55 ? "text-bull" : s.win_rate < 0.45 ? "text-bear" : "";
          return (
            <TableRow key={s.id}>
              <TableCell>{i + 1}</TableCell>
              <TableCell className="font-sans font-medium">{s.strategy_name}</TableCell>
              <TableCell className={wrColor}>{formatPct(s.win_rate)}</TableCell>
              <TableCell>{s.total_signals}</TableCell>
              <TableCell>{s.avg_rr.toFixed(2)}</TableCell>
              <TableCell className="text-gold-400">{s.sharpe_ratio.toFixed(2)}</TableCell>
              <TableCell className="text-bear">{formatPct(s.max_drawdown)}</TableCell>
            </TableRow>
          );
        })}
        {sorted.length === 0 && (
          <TableRow>
            <TableCell colSpan={7} className="text-center text-muted-foreground">
              No strategy data yet
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}
