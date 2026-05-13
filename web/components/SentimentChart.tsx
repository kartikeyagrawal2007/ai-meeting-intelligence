"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";
import type { SentimentEntry } from "@/lib/types";
import { getSpeakerColor, formatTime } from "@/lib/utils";

interface Props {
  timeline: SentimentEntry[];
}

export default function SentimentChart({ timeline }: Props) {
  const speakers = [...new Set(timeline.map((t) => t.speaker))];

  // Group by time bucket (30s windows) for smoother lines
  const bucketSize = 30;
  const bucketed: Record<string, Record<string, number[]>> = {};

  for (const entry of timeline) {
    const bucket = Math.floor(entry.start_sec / bucketSize) * bucketSize;
    const key = String(bucket);
    if (!bucketed[key]) bucketed[key] = {};
    if (!bucketed[key][entry.speaker]) bucketed[key][entry.speaker] = [];
    bucketed[key][entry.speaker].push(entry.score);
  }

  const data = Object.entries(bucketed)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([time, spkScores]) => {
      const row: Record<string, number | string> = { time: formatTime(Number(time)) };
      for (const spk of speakers) {
        const scores = spkScores[spk];
        if (scores) {
          row[spk] = Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100) / 100;
        }
      }
      return row;
    });

  const CustomTooltip = ({ active, payload, label }: {
    active?: boolean;
    payload?: { name: string; value: number; color: string }[];
    label?: string;
  }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="px-3 py-2.5 rounded-lg bg-[#1a2234] border border-[#1e293b] text-xs space-y-1 shadow-xl">
        <p className="font-semibold text-white">{label}</p>
        {payload.map((p) => (
          <div key={p.name} className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full" style={{ backgroundColor: p.color }} />
            <span className="text-slate-400">{p.name}:</span>
            <span className="font-mono" style={{ color: p.color }}>
              {p.value > 0 ? "+" : ""}{p.value}
            </span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data} margin={{ top: 5, right: 5, left: -30, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="time"
          tick={{ fontSize: 10, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          domain={[-1, 1]}
          tick={{ fontSize: 10, fill: "#475569" }}
          tickLine={false}
          axisLine={false}
        />
        <ReferenceLine y={0} stroke="#334155" strokeDasharray="4 4" />
        <Tooltip content={<CustomTooltip />} />
        {speakers.map((spk) => (
          <Line
            key={spk}
            type="monotone"
            dataKey={spk}
            stroke={getSpeakerColor(spk).dot}
            strokeWidth={2}
            dot={false}
            connectNulls
            activeDot={{ r: 4 }}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
