"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJobStatus, getResults, getRecapUrl } from "@/lib/api";
import type { Job, AnalysisResults } from "@/lib/types";
import {
  CheckCircle2, Loader2, XCircle, Download, ChevronLeft,
  Users, MessageSquare, Target, HelpCircle, ArrowRight,
  Trophy, AlertTriangle,
} from "lucide-react";
import { cn, getSpeakerColor, formatDuration, formatTime, confidenceBadge, qualityRatingColor, relativeTime } from "@/lib/utils";
import ParticipationChart from "@/components/ParticipationChart";
import SentimentChart from "@/components/SentimentChart";
import TopicTimeline from "@/components/TopicTimeline";

// ── Pipeline stages ────────────────────────────────────────────────────────────

const STAGES = [
  { key: "preprocessing",  label: "Preprocessing",  desc: "VAD & noise reduction" },
  { key: "transcribing",   label: "Transcribing",    desc: "Speaker diarization" },
  { key: "correcting",     label: "Correcting",      desc: "Cleaning transcript" },
  { key: "analyzing",      label: "Analyzing",       desc: "Participation & topics" },
  { key: "extracting",     label: "Extracting",      desc: "Action items & decisions" },
];

function stageIndex(status: string): number {
  const map: Record<string, number> = {
    queued: -1, preprocessing: 0, transcribing: 1,
    correcting: 2, analyzing: 3, extracting: 4, complete: 5, failed: -2,
  };
  return map[status] ?? -1;
}

// ── Progress view ──────────────────────────────────────────────────────────────

function ProgressView({ job }: { job: Job }) {
  const current = stageIndex(job.status);

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-lg">
        {/* Header */}
        <div className="text-center mb-10">
          <h1 className="text-2xl font-bold text-white mb-2">
            Analyzing{" "}
            <span className="gradient-text">{job.meeting_title}</span>
          </h1>
          <p className="text-slate-400 text-sm">{job.current_stage}</p>
        </div>

        {/* Overall progress bar */}
        <div className="mb-10">
          <div className="flex justify-between text-xs text-slate-500 mb-2">
            <span>Progress</span>
            <span>{job.progress}%</span>
          </div>
          <div className="h-2 rounded-full bg-[#1a2234] overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-700"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>

        {/* Stage list */}
        <div className="space-y-3">
          {STAGES.map((stage, idx) => {
            const done = idx < current;
            const active = idx === current;
            const pending = idx > current;

            return (
              <div
                key={stage.key}
                className={cn(
                  "flex items-center gap-4 px-5 py-4 rounded-xl border transition-all duration-300",
                  done    && "border-emerald-500/20 bg-emerald-500/5",
                  active  && "border-indigo-500/40 bg-indigo-500/8 glow-accent",
                  pending && "border-[#1e293b] bg-[#111827] opacity-50"
                )}
              >
                <div className={cn("w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
                  done    && "bg-emerald-500/20",
                  active  && "bg-indigo-500/20",
                  pending && "bg-[#1a2234]"
                )}>
                  {done ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  ) : active ? (
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-slate-600" />
                  )}
                </div>
                <div>
                  <p className={cn("text-sm font-medium",
                    done ? "text-emerald-300" : active ? "text-white" : "text-slate-500"
                  )}>
                    {stage.label}
                  </p>
                  <p className="text-xs text-slate-600">{stage.desc}</p>
                </div>
              </div>
            );
          })}
        </div>

        {job.status === "failed" && (
          <div className="mt-6 px-5 py-4 rounded-xl bg-rose-500/10 border border-rose-500/20">
            <div className="flex items-center gap-2 mb-1">
              <XCircle className="w-4 h-4 text-rose-400" />
              <p className="text-sm font-medium text-rose-300">Analysis Failed</p>
            </div>
            <p className="text-xs text-rose-400/70">{job.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Section wrapper ────────────────────────────────────────────────────────────

function Section({
  title, icon: Icon, children, className,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-2xl bg-[#111827] border border-[#1e293b] overflow-hidden", className)}>
      <div className="px-6 py-4 border-b border-[#1e293b] flex items-center gap-2.5">
        <Icon className="w-4 h-4 text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">{title}</h2>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

// ── Quality score card ─────────────────────────────────────────────────────────

function QualityCard({ quality }: { quality: AnalysisResults["quality_score"] }) {
  const ratingColor = qualityRatingColor(quality.rating);
  const pct = quality.total;

  const subs = [
    { label: "Participation", value: quality.sub_scores.participation },
    { label: "Sentiment",     value: quality.sub_scores.sentiment },
    { label: "Decisions",     value: quality.sub_scores.decision_and_actions },
    { label: "Interruptions", value: quality.sub_scores.interruption_control },
    { label: "Engagement",    value: quality.sub_scores.engagement_consistency },
  ];

  return (
    <div className="rounded-2xl bg-[#111827] border border-[#1e293b] overflow-hidden">
      <div className="px-6 py-4 border-b border-[#1e293b] flex items-center gap-2.5">
        <Trophy className="w-4 h-4 text-indigo-400" />
        <h2 className="text-sm font-semibold text-slate-200">Meeting Quality Score</h2>
      </div>
      <div className="p-6">
        <div className="flex items-center gap-6 mb-6">
          {/* Circular score */}
          <div className="relative w-24 h-24 flex-shrink-0">
            <svg className="w-24 h-24 -rotate-90" viewBox="0 0 96 96">
              <circle cx="48" cy="48" r="40" fill="none" stroke="#1e293b" strokeWidth="8" />
              <circle
                cx="48" cy="48" r="40" fill="none"
                stroke="url(#scoreGrad)" strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 40}`}
                strokeDashoffset={`${2 * Math.PI * 40 * (1 - pct / 100)}`}
                className="transition-all duration-1000"
              />
              <defs>
                <linearGradient id="scoreGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#6366f1" />
                  <stop offset="100%" stopColor="#8b5cf6" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold text-white">{pct}</span>
              <span className="text-[10px] text-slate-500">/ 100</span>
            </div>
          </div>
          <div>
            <p className={cn("text-2xl font-bold mb-1", ratingColor)}>{quality.rating}</p>
            <p className="text-xs text-slate-500">Composite quality score based on<br />5 weighted analytics dimensions</p>
          </div>
        </div>

        {/* Sub-scores */}
        <div className="space-y-2.5">
          {subs.map((s) => (
            <div key={s.label}>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-400">{s.label}</span>
                <span className="text-slate-300 font-mono">{s.value.toFixed(1)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-[#1a2234] overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-700"
                  style={{ width: `${s.value}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function SimpleMarkdown({ content }: { content: string }) {
  if (!content) return null;
  const lines = content.split('\n');
  return (
    <div className="space-y-3 text-sm text-slate-300 leading-relaxed">
      {lines.map((line, i) => {
        if (line.startsWith('# ')) return <h1 key={i} className="text-xl font-bold text-white mt-4 mb-2">{line.replace('# ', '')}</h1>;
        if (line.startsWith('## ')) return <h2 key={i} className="text-lg font-semibold text-slate-200 mt-4 mb-2">{line.replace('## ', '')}</h2>;
        if (line.startsWith('### ')) return <h3 key={i} className="text-md font-medium text-slate-200 mt-3 mb-1">{line.replace('### ', '')}</h3>;
        if (line.startsWith('- ') || line.startsWith('* ')) return <li key={i} className="ml-4 list-disc">{line.substring(2)}</li>;
        if (line.trim() === '') return null;
        
        const parts = line.split(/(\*\*.*?\*\*)/g);
        return (
          <p key={i}>
            {parts.map((part, j) => {
              if (part.startsWith('**') && part.endsWith('**')) {
                return <strong key={j} className="text-white font-semibold">{part.slice(2, -2)}</strong>;
              }
              return part;
            })}
          </p>
        );
      })}
    </div>
  );
}

// ── Transcript view ────────────────────────────────────────────────────────────

function TranscriptView({ utterances }: { utterances: AnalysisResults["utterances"] }) {
  return (
    <div className="space-y-2">
      {utterances.map((utt, i) => {
        const color = getSpeakerColor(utt.speaker);
        return (
          <div key={i} className={cn("flex gap-3 p-3 rounded-lg border", color.bg, color.border + "/20")}>
            <div className={cn("w-2 h-2 rounded-full mt-2 flex-shrink-0", `bg-[${color.dot}]`)}
              style={{ backgroundColor: color.dot }} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={cn("text-xs font-semibold", color.text)}>
                  {utt.speaker}
                </span>
                <span className="text-[10px] text-slate-600">
                  {formatTime(utt.start / 1000)}
                </span>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{utt.text}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Action items ───────────────────────────────────────────────────────────────

function ActionItemList({ items, uncertain }: {
  items: AnalysisResults["intelligence"]["action_items"];
  uncertain: AnalysisResults["intelligence"]["action_items"];
}) {
  const [checkedItems, setCheckedItems] = useState<Set<number>>(new Set());

  const toggleCheck = (idx: number) => {
    const newSet = new Set(checkedItems);
    if (newSet.has(idx)) {
      newSet.delete(idx);
    } else {
      newSet.add(idx);
    }
    setCheckedItems(newSet);
  };

  if (!items.length && !uncertain.length) {
    return <p className="text-sm text-slate-500 italic">No action items identified.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((item, i) => {
        const { emoji, label, color } = confidenceBadge(item.confidence);
        const isChecked = checkedItems.has(i);
        return (
          <div key={i} className={cn("px-4 py-3 rounded-xl border transition-colors", 
            isChecked ? "bg-[#0d1424]/50 border-[#1e293b]/50 opacity-60" : "bg-[#0d1424] border-[#1e293b]")}>
            <div className="flex items-start gap-3">
              <button 
                onClick={() => toggleCheck(i)}
                className={cn("w-5 h-5 rounded border mt-0.5 flex-shrink-0 flex items-center justify-center transition-colors", 
                  isChecked ? "bg-indigo-500 border-indigo-500 text-white" : "border-[#1e293b] hover:border-indigo-500/50")}
              >
                {isChecked && <CheckCircle2 className="w-3.5 h-3.5" />}
              </button>
              <div className="flex-1 min-w-0">
                <p className={cn("text-sm transition-colors", isChecked ? "text-slate-500 line-through" : "text-slate-200")}>{item.action}</p>
                <div className="flex flex-wrap gap-2 mt-1.5">
                  {item.owner && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      @{item.owner}
                    </span>
                  )}
                  {item.deadline && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                      📅 {item.deadline}
                    </span>
                  )}
                  <span className={cn("text-xs px-2 py-0.5 rounded-full border", color,
                    item.confidence >= 0.9 ? "bg-emerald-500/10 border-emerald-500/20" :
                    item.confidence >= 0.7 ? "bg-amber-500/10 border-amber-500/20" :
                    "bg-rose-500/10 border-rose-500/20"
                  )}>
                    {emoji} {label} ({Math.round(item.confidence * 100)}%)
                  </span>
                </div>
                {item.source_quote && (
                  <p className="text-xs text-slate-500 mt-1.5 italic">
                    &ldquo;{item.source_quote}&rdquo;
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}

      {uncertain.length > 0 && (
        <div className="mt-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            <p className="text-xs font-medium text-amber-400">Needs Human Review</p>
          </div>
          {uncertain.map((item, i) => (
            <div key={i} className="px-4 py-3 rounded-xl bg-amber-500/5 border border-amber-500/20 opacity-75 mb-2">
              <p className="text-sm text-slate-300">{item.action}</p>
              <p className="text-xs text-slate-500 mt-1">
                {Math.round(item.confidence * 100)}% confidence · @{item.owner || "unassigned"}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Results view ───────────────────────────────────────────────────────────────

function ResultsView({ results, jobId }: { results: AnalysisResults; jobId: string }) {
  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-1">Analysis Complete</p>
          <h1 className="text-2xl font-bold text-white">{results.meeting_title}</h1>
        </div>
        <a
          href={getRecapUrl(jobId)}
          download
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-300 text-sm font-medium hover:bg-indigo-500/25 transition-colors"
        >
          <Download className="w-4 h-4" />
          Download Recap
        </a>
      </div>

      {/* Quality + participation side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <QualityCard quality={results.quality_score} />
        <Section title="Participation" icon={Users}>
          <ParticipationChart participation={results.participation} />
        </Section>
      </div>

      {/* Topic Timeline */}
      {results.topics?.length > 0 && (
        <Section title="Topic Segments" icon={ArrowRight}>
          <TopicTimeline topics={results.topics} />
        </Section>
      )}

      {/* Sentiment timeline */}
      {results.sentiment?.timeline?.length > 0 && (
        <Section title="Sentiment Timeline" icon={MessageSquare}>
          <SentimentChart timeline={results.sentiment.timeline} />
        </Section>
      )}

      {/* Action items */}
      <Section title="Action Items" icon={Target}>
        <ActionItemList
          items={results.intelligence?.action_items ?? []}
          uncertain={results.intelligence?.uncertain_action_items ?? []}
        />
      </Section>

      {/* Decisions */}
      {results.intelligence?.decisions?.length > 0 && (
        <Section title="Decisions Made" icon={CheckCircle2}>
          <div className="space-y-2">
            {results.intelligence.decisions.map((d, i) => {
              const { emoji } = confidenceBadge(d.confidence);
              return (
                <div key={i} className="px-4 py-3 rounded-xl bg-[#0d1424] border border-[#1e293b]">
                  <p className="text-sm text-slate-200">{emoji} {d.decision}</p>
                  {d.source_quote && (
                    <p className="text-xs text-slate-500 mt-1 italic">&ldquo;{d.source_quote}&rdquo;</p>
                  )}
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Follow-ups + open questions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {results.intelligence?.follow_ups?.length > 0 && (
          <Section title="Follow-ups" icon={ArrowRight}>
            <div className="space-y-2">
              {results.intelligence.follow_ups.map((f, i) => (
                <div key={i} className="px-4 py-3 rounded-xl bg-[#0d1424] border border-[#1e293b]">
                  <p className="text-sm text-slate-200">{f.topic}</p>
                  {f.reason && <p className="text-xs text-slate-500 mt-1">{f.reason}</p>}
                </div>
              ))}
            </div>
          </Section>
        )}

        {results.intelligence?.open_questions?.length > 0 && (
          <Section title="Open Questions" icon={HelpCircle}>
            <div className="space-y-2">
              {results.intelligence.open_questions.map((q, i) => (
                <div key={i} className="px-4 py-3 rounded-xl bg-[#0d1424] border border-[#1e293b]">
                  <p className="text-sm text-slate-200">❓ {q.question}</p>
                  <p className="text-xs text-slate-500 mt-1">Asked by {q.asked_by}</p>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>

      {/* AI Summary */}
      {results.recap_markdown && (
        <Section title="AI Meeting Summary" icon={MessageSquare}>
          <SimpleMarkdown content={results.recap_markdown} />
        </Section>
      )}

      {/* Transcript */}
      <Section title="Full Transcript" icon={MessageSquare}>
        <TranscriptView utterances={results.utterances} />
      </Section>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function MeetingPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<Job | null>(null);
  const [results, setResults] = useState<AnalysisResults | null>(null);
  const [error, setError] = useState("");

  const poll = useCallback(async () => {
    try {
      const j = await getJobStatus(id);
      setJob(j);

      if (j.status === "complete") {
        const r = await getResults(id);
        setResults(r);
      } else if (j.status === "failed") {
        setError(j.error ?? "Analysis failed");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch status");
    }
  }, [id]);

  useEffect(() => {
    poll();
    const interval = setInterval(async () => {
      const j = job;
      if (j && (j.status === "complete" || j.status === "failed")) return;
      await poll();
    }, 2500);
    return () => clearInterval(interval);
  }, [poll, job?.status]);

  return (
    <div>
      {/* Back button */}
      <div className="px-8 pt-6">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          <ChevronLeft className="w-3.5 h-3.5" />
          Back to Upload
        </button>
      </div>

      {error && (
        <div className="p-8">
          <div className="px-5 py-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
            {error}
          </div>
        </div>
      )}

      {results ? (
        <ResultsView results={results} jobId={id} />
      ) : job ? (
        <ProgressView job={job} />
      ) : (
        <div className="min-h-screen flex items-center justify-center">
          <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
        </div>
      )}
    </div>
  );
}
