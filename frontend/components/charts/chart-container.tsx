"use client";

import { useEffect, useRef, useState } from "react";

interface ChartContainerProps {
  className?: string;
  children: (dimensions: { width: number; height: number }) => React.ReactNode;
}

export function ChartContainer({ className, children }: ChartContainerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setDimensions({ width: Math.floor(width), height: Math.floor(height) });
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className={className}>
      {dimensions.width > 0 && dimensions.height > 0 && children(dimensions)}
    </div>
  );
}
