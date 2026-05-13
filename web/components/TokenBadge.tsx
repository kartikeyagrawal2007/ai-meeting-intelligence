"use client";

import { useEffect, useState } from "react";
import { getTokenUsage } from "@/lib/api";
import type { TokenUsage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Zap } from "lucide-react";

export default function TokenBadge() {
  const [usage, setUsage] = useState<TokenUsage | null>(null);

  useEffect(() => {
    getTokenUsage()
      .then((d) => setUsage(d.today))
      .catch(() => null);

    const id = setInterval(() => {
      getTokenUsage()
        .then((d) => setUsage(d.today))
        .catch(() => null);
    }, 30_000);

    return () => clearInterval(id);
  }, []);

  if (!usage) {
    return (
      <div className="rounded-lg bg-[#111827] border border-[#1e293b] p-3 shimmer h-16" />
    );
  }

  const barColor =
    usage.status === "critical"
      ? "bg-rose-500"
      : usage.status === "warning"
      ? "bg-amber-500"
      : "bg-indigo-500";

  const textColor =
    usage.status === "critical"
      ? "text-rose-400"
      : usage.status === "warning"
      ? "text-amber-400"
      : "text-slate-400";

  return (
    <div className="rounded-lg bg-[#111827] border border-[#1e293b] p-3 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Zap className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-xs font-medium text-slate-300">Daily Tokens</span>
        </div>
        <span className={cn("text-xs font-mono", textColor)}>
          {usage.percent_used}%
        </span>
      </div>

      {/* Bar */}
      <div className="h-1.5 rounded-full bg-[#1e293b] overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all duration-500", barColor)}
          style={{ width: `${Math.min(usage.percent_used, 100)}%` }}
        />
      </div>

      <div className="flex justify-between text-[10px] text-slate-600">
        <span>{(usage.tokens_used / 1000).toFixed(1)}k used</span>
        <span>{(usage.remaining / 1000).toFixed(1)}k left</span>
      </div>
    </div>
  );
}
