"use client";

import { useEffect, useState } from "react";

interface ABVariantSummary {
  variant_name: string;
  total_cycles: number;
  total_signals: number;
  total_won: number;
  total_lost: number;
  win_rate: number;
  is_significant: boolean;
  p_value: number | null;
}

interface ABTestResults {
  variants: ABVariantSummary[];
  significant: boolean;
  p_value: number | null;
  recommendation: string;
}

export function ABTestPanel() {
  const [results, setResults] = useState<ABTestResults | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/ab-tests")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch");
        return res.json();
      })
      .then((data: ABTestResults) => setResults(data))
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold">A/B Test Results</h3>
        <p className="mt-2 text-xs text-muted-foreground">
          Unable to load A/B test data
        </p>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="rounded-lg border border-border bg-surface p-4">
        <h3 className="text-sm font-semibold">A/B Test Results</h3>
        <p className="mt-2 text-xs text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-sm font-semibold">A/B Test Results</h3>
        {results.significant ? (
          <span className="rounded-full bg-bull/20 px-2 py-0.5 text-[10px] font-medium text-bull">
            Significant
          </span>
        ) : (
          <span className="rounded-full bg-muted/20 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
            Not significant
          </span>
        )}
      </div>

      <div className="p-4">
        {results.variants.length === 0 ? (
          <p className="py-4 text-center text-xs text-muted-foreground">
            No A/B test data yet. Enable AB_TESTING_ENABLED to start.
          </p>
        ) : (
          <div className="space-y-3">
            {results.variants.map((v) => (
              <div
                key={v.variant_name}
                className="rounded-md border border-border bg-surface-raised p-3"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium">{v.variant_name}</span>
                  <span className="font-mono text-xs text-gold-400">
                    {(v.win_rate * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-[10px] text-muted-foreground">
                  <div>
                    <span className="block text-muted">Cycles</span>
                    {v.total_cycles}
                  </div>
                  <div>
                    <span className="block text-muted">Won</span>
                    <span className="text-bull">{v.total_won}</span>
                  </div>
                  <div>
                    <span className="block text-muted">Lost</span>
                    <span className="text-bear">{v.total_lost}</span>
                  </div>
                </div>
              </div>
            ))}

            {results.p_value !== null && (
              <p className="text-[10px] text-muted-foreground">
                p-value: {results.p_value.toFixed(4)}
              </p>
            )}

            <p className="text-xs leading-relaxed text-muted-foreground">
              {results.recommendation}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
