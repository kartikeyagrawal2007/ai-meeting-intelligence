// lib/utils.ts — shared utilities

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Speaker label → consistent color index (0-7) */
export function speakerColorIndex(speaker: string): number {
  const code = speaker.charCodeAt(speaker.length - 1);
  return code % 8;
}

export const SPEAKER_COLORS = [
  { bg: "bg-blue-500/20",   border: "border-blue-500",   text: "text-blue-400",   dot: "#3b82f6" },
  { bg: "bg-emerald-500/20", border: "border-emerald-500", text: "text-emerald-400", dot: "#10b981" },
  { bg: "bg-violet-500/20", border: "border-violet-500", text: "text-violet-400", dot: "#8b5cf6" },
  { bg: "bg-amber-500/20",  border: "border-amber-500",  text: "text-amber-400",  dot: "#f59e0b" },
  { bg: "bg-rose-500/20",   border: "border-rose-500",   text: "text-rose-400",   dot: "#f43f5e" },
  { bg: "bg-cyan-500/20",   border: "border-cyan-500",   text: "text-cyan-400",   dot: "#06b6d4" },
  { bg: "bg-pink-500/20",   border: "border-pink-500",   text: "text-pink-400",   dot: "#ec4899" },
  { bg: "bg-teal-500/20",   border: "border-teal-500",   text: "text-teal-400",   dot: "#14b8a6" },
];

export function getSpeakerColor(speaker: string) {
  return SPEAKER_COLORS[speakerColorIndex(speaker)];
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

export function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export function confidenceBadge(confidence: number): {
  emoji: string;
  label: string;
  color: string;
} {
  if (confidence >= 0.9) return { emoji: "🟢", label: "High", color: "text-emerald-400" };
  if (confidence >= 0.7) return { emoji: "🟡", label: "Medium", color: "text-amber-400" };
  return { emoji: "🔴", label: "Low", color: "text-rose-400" };
}

export function qualityRatingColor(rating: string): string {
  switch (rating) {
    case "Excellent":         return "text-emerald-400";
    case "Good":              return "text-blue-400";
    case "Fair":              return "text-amber-400";
    case "Needs Improvement": return "text-orange-400";
    case "Poor":              return "text-rose-400";
    default:                  return "text-slate-400";
  }
}

export function relativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
