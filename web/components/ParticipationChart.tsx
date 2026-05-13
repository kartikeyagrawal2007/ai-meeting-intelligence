"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import type { ParticipationStats } from "@/lib/types";
import { getSpeakerColor, formatDuration } from "@/lib/utils";

interface Props {
  participation: Record<string, ParticipationStats>;
}

export default function ParticipationChart({ participation }: Props) {
  const entries = Object.entries(participation);

  const data = entries.map(([speaker, stats]) => ({
    name: speaker,
    value: Math.round(stats.speaking_share_percent * 10) / 10,
    time: stats.speaking_time_seconds,
    utterances: stats.utterance_count,
    avgWords: stats.average_words_per_utterance,
  }));

  const COLORS = entries.map(([spk]) => getSpeakerColor(spk).dot);

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: { payload: typeof data[0] }[] }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="px-3 py-2.5 rounded-lg bg-[#1a2234] border border-[#1e293b] text-xs space-y-1 shadow-xl">
        <p className="font-semibold text-white">{d.name}</p>
        <p className="text-slate-400">{d.value}% speaking share</p>
        <p className="text-slate-400">{formatDuration(d.time)} total</p>
        <p className="text-slate-400">{d.utterances} turns · {d.avgWords} words/turn</p>
      </div>
    );
  };

  return (
    <div>
      <ResponsiveContainer width="100%" height={200}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={55}
            outerRadius={85}
            paddingAngle={3}
            dataKey="value"
            stroke="none"
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip />} />
        </PieChart>
      </ResponsiveContainer>

      {/* Legend */}
      <div className="mt-3 space-y-1.5">
        {entries.map(([speaker, stats]) => {
          const color = getSpeakerColor(speaker);
          return (
            <div key={speaker} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color.dot }} />
                <span className="text-slate-300">{speaker}</span>
              </div>
              <div className="flex items-center gap-3 text-slate-500">
                <span>{stats.speaking_share_percent.toFixed(1)}%</span>
                <span>{formatDuration(stats.speaking_time_seconds)}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
