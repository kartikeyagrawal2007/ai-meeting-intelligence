"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listJobs, getTokenUsage } from "@/lib/api";
import type { Job, TokenUsage } from "@/lib/types";
import {
  Search, LayoutDashboard, CheckCircle2, Loader2,
  XCircle, Clock, Trophy, Zap, TrendingUp,
} from "lucide-react";
import { cn, qualityRatingColor, relativeTime } from "@/lib/utils";

function StatusBadge({ status }: { status: Job["status"] }) {
  const map = {
    complete:      { icon: CheckCircle2, color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
    failed:        { icon: XCircle,      color: "text-rose-400 bg-rose-500/10 border-rose-500/20" },
    queued:        { icon: Clock,        color: "text-slate-400 bg-slate-500/10 border-slate-500/20" },
    preprocessing: { icon: Loader2,      color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
    transcribing:  { icon: Loader2,      color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
    correcting:    { icon: Loader2,      color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
    analyzing:     { icon: Loader2,      color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
    extracting:    { icon: Loader2,      color: "text-indigo-400 bg-indigo-500/10 border-indigo-500/20" },
  };

  const { icon: Icon, color } = map[status] ?? map.queued;
  const isActive = !["complete", "failed", "queued"].includes(status);

  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border", color)}>
      <Icon className={cn("w-3 h-3", isActive && "animate-spin")} />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function SkeletonRow() {
  return (
    <div className="px-6 py-4 flex items-center gap-4">
      <div className="h-4 w-48 rounded shimmer" />
      <div className="h-4 w-20 rounded shimmer ml-auto" />
      <div className="h-4 w-16 rounded shimmer" />
    </div>
  );
}

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [tokenData, setTokenData] = useState<{ today: TokenUsage } | null>(null);

  useEffect(() => {
    const load = async () => {
      const [j, t] = await Promise.allSettled([listJobs(), getTokenUsage()]);
      if (j.status === "fulfilled") setJobs(j.value);
      if (t.status === "fulfilled") setTokenData(t.value);
      setLoading(false);
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  const filtered = jobs.filter((j) =>
    j.meeting_title.toLowerCase().includes(search.toLowerCase())
  );

  const completedJobs = jobs.filter((j) => j.status === "complete");
  const activeJobs = jobs.filter((j) =>
    !["complete", "failed"].includes(j.status)
  );

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <LayoutDashboard className="w-5 h-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        </div>
        <p className="text-slate-400 text-sm">All analyzed meetings</p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Meetings",  value: jobs.length,          icon: Trophy,    color: "text-indigo-400" },
          { label: "Completed",       value: completedJobs.length, icon: CheckCircle2, color: "text-emerald-400" },
          { label: "In Progress",     value: activeJobs.length,    icon: Loader2,   color: "text-amber-400" },
          {
            label: "Tokens Today",
            value: tokenData ? `${(tokenData.today.tokens_used / 1000).toFixed(1)}k` : "—",
            icon: Zap,
            color: tokenData?.today.status === "warning" ? "text-amber-400" :
                   tokenData?.today.status === "critical" ? "text-rose-400" : "text-slate-400",
          },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="rounded-xl bg-[#111827] border border-[#1e293b] px-5 py-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
              <Icon className={cn("w-4 h-4", color)} />
            </div>
            <p className="text-2xl font-bold text-white">{value}</p>
          </div>
        ))}
      </div>

      {/* Token usage bar */}
      {tokenData && (
        <div className="rounded-xl bg-[#111827] border border-[#1e293b] px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Zap className="w-4 h-4 text-indigo-400" />
              <p className="text-sm font-medium text-slate-200">Daily Token Budget</p>
            </div>
            <span className={cn("text-xs font-mono",
              tokenData.today.status === "critical" ? "text-rose-400" :
              tokenData.today.status === "warning"  ? "text-amber-400" : "text-slate-400"
            )}>
              {tokenData.today.tokens_used.toLocaleString()} / {tokenData.today.daily_limit.toLocaleString()}
            </span>
          </div>
          <div className="h-2 rounded-full bg-[#1a2234] overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-500",
                tokenData.today.status === "critical" ? "bg-rose-500" :
                tokenData.today.status === "warning"  ? "bg-amber-500" : "bg-indigo-500"
              )}
              style={{ width: `${Math.min(tokenData.today.percent_used, 100)}%` }}
            />
          </div>
          <div className="flex justify-between mt-1.5 text-xs text-slate-600">
            <span>{tokenData.today.percent_used}% used</span>
            <span>{tokenData.today.remaining.toLocaleString()} remaining</span>
          </div>
        </div>
      )}

      {/* Search + table */}
      <div className="rounded-2xl bg-[#111827] border border-[#1e293b] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#1e293b] flex items-center gap-3">
          <Search className="w-4 h-4 text-slate-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search meetings…"
            className="flex-1 bg-transparent text-sm text-slate-200 placeholder:text-slate-600 focus:outline-none"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Clear
            </button>
          )}
        </div>

        {loading ? (
          <div className="divide-y divide-[#1e293b]">
            {[...Array(4)].map((_, i) => <SkeletonRow key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <Trophy className="w-8 h-8 text-slate-700 mx-auto mb-3" />
            <p className="text-sm text-slate-500">
              {search ? "No meetings match your search" : "No meetings analyzed yet"}
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center gap-1.5 text-xs text-indigo-400 hover:text-indigo-300"
            >
              Upload your first meeting →
            </Link>
          </div>
        ) : (
          <div className="divide-y divide-[#1e293b]">
            {/* Table header */}
            <div className="px-6 py-2.5 grid grid-cols-12 gap-4 text-[10px] uppercase tracking-widest text-slate-600 font-medium">
              <span className="col-span-5">Title</span>
              <span className="col-span-2">Status</span>
              <span className="col-span-2">Provider</span>
              <span className="col-span-2">Created</span>
              <span className="col-span-1" />
            </div>

            {filtered.map((job) => (
              <div
                key={job.job_id}
                className="px-6 py-4 grid grid-cols-12 gap-4 items-center hover:bg-white/[0.02] transition-colors"
              >
                <div className="col-span-5 min-w-0">
                  <p className="text-sm font-medium text-slate-200 truncate">
                    {job.meeting_title}
                  </p>
                  <p className="text-xs text-slate-600 truncate">{job.audio_filename}</p>
                </div>

                <div className="col-span-2">
                  <StatusBadge status={job.status} />
                  {!["complete","failed","queued"].includes(job.status) && (
                    <div className="mt-1.5 h-1 rounded-full bg-[#1a2234] overflow-hidden">
                      <div
                        className="h-full rounded-full bg-indigo-500 transition-all"
                        style={{ width: `${job.progress}%` }}
                      />
                    </div>
                  )}
                </div>

                <div className="col-span-2">
                  <span className="text-xs text-slate-500 capitalize">{job.provider}</span>
                </div>

                <div className="col-span-2">
                  <span className="text-xs text-slate-500">{relativeTime(job.created_at)}</span>
                </div>

                <div className="col-span-1 text-right">
                  {job.status === "complete" ? (
                    <Link
                      href={`/meeting/${job.job_id}`}
                      className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                    >
                      View →
                    </Link>
                  ) : job.status !== "failed" ? (
                    <Link
                      href={`/meeting/${job.job_id}`}
                      className="text-xs text-slate-500 hover:text-slate-300"
                    >
                      Track →
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
