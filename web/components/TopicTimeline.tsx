"use client";

import type { TopicSegment } from "@/lib/types";
import { formatTime, formatDuration } from "@/lib/utils";

const SEGMENT_COLORS = [
  "#6366f1", "#8b5cf6", "#06b6d4", "#10b981",
  "#f59e0b", "#f43f5e", "#ec4899", "#14b8a6",
];

interface Props {
  topics: TopicSegment[];
}

export default function TopicTimeline({ topics }: Props) {
  if (!topics.length) return null;

  const totalDuration = topics.reduce((sum, t) => sum + t.duration_sec, 0) || 1;

  return (
    <div className="space-y-4">
      {/* Visual bar */}
      <div className="flex h-8 rounded-lg overflow-hidden gap-0.5">
        {topics.map((topic, i) => (
          <div
            key={topic.segment_id}
            className="flex items-center justify-center text-[10px] font-bold text-white/80 overflow-hidden transition-all"
            style={{
              width: `${(topic.duration_sec / totalDuration) * 100}%`,
              backgroundColor: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
              minWidth: "2%",
            }}
            title={topic.label}
          >
            {(topic.duration_sec / totalDuration) > 0.08 ? i + 1 : ""}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="space-y-2">
        {topics.map((topic, i) => (
          <div key={topic.segment_id} className="flex items-start gap-3">
            <div
              className="w-3 h-3 rounded-sm mt-0.5 flex-shrink-0"
              style={{ backgroundColor: SEGMENT_COLORS[i % SEGMENT_COLORS.length] }}
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-200 truncate">{topic.label}</p>
                <span className="text-xs text-slate-500 flex-shrink-0">
                  {formatTime(topic.start_sec)} · {formatDuration(topic.duration_sec)}
                </span>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {topic.keywords.slice(0, 4).map((kw) => (
                  <span
                    key={kw}
                    className="text-[10px] px-1.5 py-0.5 rounded-full bg-[#1a2234] text-slate-500 border border-[#1e293b]"
                  >
                    {kw}
                  </span>
                ))}
                <span className="text-[10px] text-slate-600">
                  · {topic.utterance_count} turns
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
