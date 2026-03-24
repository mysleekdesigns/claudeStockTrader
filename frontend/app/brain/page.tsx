import {
  getActiveParams,
  getBacktests,
  getDecisions,
  getPnLHistory,
  getRiskState,
  getStrategyPerformance,
} from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StrategyTable } from "@/components/brain/strategy-table";
import { PnLChart } from "@/components/charts/pnl-chart";
import { RiskPanel } from "@/components/brain/risk-panel";
import { DecisionLogView } from "@/components/brain/decision-log";
import { BacktestTable } from "@/components/brain/backtest-table";
import { ABTestPanel } from "@/components/brain/ab-test-panel";
import { ParamsViewer } from "@/components/brain/params-viewer";

export default async function BrainPage() {
  let strategies = [];
  let pnlData = [];
  let risk = null;
  let decisions = [];
  let backtests = [];
  let params = [];

  [strategies, pnlData, risk, decisions, backtests, params] = await Promise.all([
    getStrategyPerformance().catch((e) => { console.error("Failed to fetch strategy performance:", e.message); return []; }),
    getPnLHistory().catch((e) => { console.error("Failed to fetch PnL history:", e.message); return []; }),
    getRiskState().catch((e) => { console.error("Failed to fetch risk state:", e.message); return null; }),
    getDecisions().catch((e) => { console.error("Failed to fetch decisions:", e.message); return []; }),
    getBacktests().catch((e) => { console.error("Failed to fetch backtests:", e.message); return []; }),
    getActiveParams().catch((e) => { console.error("Failed to fetch active params:", e.message); return []; }),
  ]);

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-bold">Brain Dashboard</h1>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Strategy Leaderboard</CardTitle></CardHeader>
            <CardContent>
              <StrategyTable strategies={strategies} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Cumulative P&L</CardTitle></CardHeader>
            <CardContent>
              <PnLChart data={pnlData} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Backtest Results</CardTitle></CardHeader>
            <CardContent>
              <BacktestTable runs={backtests} />
            </CardContent>
          </Card>

          <div>
            <h2 className="mb-3 text-sm font-semibold text-muted-foreground">
              Active Parameters
            </h2>
            <ParamsViewer params={params} />
          </div>
        </div>

        <div className="space-y-4">
          <RiskPanel initialRisk={risk} />
          <ABTestPanel />
          <DecisionLogView initialDecisions={decisions} />
        </div>
      </div>
    </div>
  );
}
