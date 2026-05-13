"use client";

import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  Upload, FileAudio, X, ChevronRight, Settings2,
  Mic2, ToggleLeft, ToggleRight,
} from "lucide-react";
import { uploadAudio } from "@/lib/api";
import { cn } from "@/lib/utils";

const ACCEPT = ".mp3,.wav,.m4a,.mp4,.ogg,.flac";

function Toggle({
  label, description, value, onChange,
}: {
  label: string; description: string; value: boolean; onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!value)}
      className="flex items-center justify-between w-full px-4 py-3 rounded-lg bg-[#111827] border border-[#1e293b] hover:border-slate-600 transition-colors group"
    >
      <div className="text-left">
        <p className="text-sm font-medium text-slate-200">{label}</p>
        <p className="text-xs text-slate-500 mt-0.5">{description}</p>
      </div>
      {value ? (
        <ToggleRight className="w-5 h-5 text-indigo-400 flex-shrink-0" />
      ) : (
        <ToggleLeft className="w-5 h-5 text-slate-600 flex-shrink-0" />
      )}
    </button>
  );
}

export default function UploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [title, setTitle] = useState("");
  const [provider, setProvider] = useState<"assemblyai" | "groq">("assemblyai");
  const [skipPreprocess, setSkipPreprocess] = useState(false);
  const [skipCorrection, setSkipCorrection] = useState(false);
  const [skipSentiment, setSkipSentiment] = useState(false);
  const [skipExtraction, setSkipExtraction] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Drag & drop handlers
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);
  const onDragLeave = useCallback(() => setDragging(false), []);
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");

    try {
      const { job_id } = await uploadAudio(file, {
        meetingTitle: title || file.name.replace(/\.[^.]+$/, ""),
        provider,
        skipPreprocess,
        skipCorrection,
        skipSentiment,
        skipExtraction,
      });
      router.push(`/meeting/${job_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setLoading(false);
    }
  };

  const formatBytes = (b: number) =>
    b > 1_000_000 ? `${(b / 1_000_000).toFixed(1)} MB` : `${(b / 1024).toFixed(0)} KB`;

  return (
    <div className="min-h-screen p-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-4">
          <Mic2 className="w-3 h-3" />
          AI Meeting Intelligence
        </div>
        <h1 className="text-3xl font-bold text-white mb-2">
          Analyze a{" "}
          <span className="gradient-text">Meeting Recording</span>
        </h1>
        <p className="text-slate-400 text-sm">
          Upload your audio file. Our AI will transcribe, analyze sentiment,
          extract action items, and score meeting quality — automatically.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Drop zone */}
        <div
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          className={cn(
            "relative border-2 border-dashed rounded-2xl p-10 cursor-pointer transition-all duration-200 text-center",
            dragging
              ? "border-indigo-500 bg-indigo-500/8 shadow-lg shadow-indigo-500/10 dropzone-active"
              : file
              ? "border-indigo-500/40 bg-indigo-500/5"
              : "border-[#1e293b] bg-[#111827] hover:border-slate-600 hover:bg-[#131e30]"
          )}
        >
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            className="hidden"
            onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
          />

          {file ? (
            <div className="flex items-center justify-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
                <FileAudio className="w-5 h-5 text-indigo-400" />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
              </div>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); setFile(null); }}
                className="ml-auto w-6 h-6 rounded-full bg-slate-700 hover:bg-slate-600 flex items-center justify-center transition-colors"
              >
                <X className="w-3 h-3 text-slate-300" />
              </button>
            </div>
          ) : (
            <>
              <div className="w-12 h-12 rounded-2xl bg-[#1a2234] border border-[#1e293b] flex items-center justify-center mx-auto mb-4">
                <Upload className="w-5 h-5 text-slate-400" />
              </div>
              <p className="text-sm font-medium text-slate-200 mb-1">
                Drop your audio file here
              </p>
              <p className="text-xs text-slate-500">
                MP3, WAV, M4A, MP4, OGG, FLAC · Up to 500 MB
              </p>
            </>
          )}
        </div>

        {/* Meeting title */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">
            Meeting Title
          </label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Q2 Planning Session"
            className="w-full px-4 py-3 rounded-xl bg-[#111827] border border-[#1e293b] text-slate-200 placeholder:text-slate-600 text-sm focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/30 transition-colors"
          />
        </div>

        {/* Provider toggle */}
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">
            Transcription Provider
          </label>
          <div className="grid grid-cols-2 gap-2">
            {(["assemblyai", "groq"] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setProvider(p)}
                className={cn(
                  "py-3 rounded-xl text-sm font-medium border transition-all duration-150",
                  provider === p
                    ? "bg-indigo-500/15 border-indigo-500/40 text-indigo-300"
                    : "bg-[#111827] border-[#1e293b] text-slate-400 hover:text-slate-300 hover:border-slate-600"
                )}
              >
                {p === "assemblyai" ? "🎙 AssemblyAI" : "⚡ Groq Whisper"}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-600 mt-2">
            AssemblyAI provides speaker diarization · Groq Whisper is faster but single-speaker
          </p>
        </div>

        {/* Skip flags */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Settings2 className="w-3.5 h-3.5 text-slate-500" />
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Pipeline Options
            </label>
          </div>
          <div className="space-y-2">
            <Toggle
              label="Skip Preprocessing"
              description="Bypass VAD & noise reduction (faster)"
              value={skipPreprocess}
              onChange={setSkipPreprocess}
            />
            <Toggle
              label="Skip Correction"
              description="Don't clean up filler words & false starts"
              value={skipCorrection}
              onChange={setSkipCorrection}
            />
            <Toggle
              label="Skip Sentiment Analysis"
              description="Save ~30k tokens — skip emotional analysis"
              value={skipSentiment}
              onChange={setSkipSentiment}
            />
            <Toggle
              label="Skip Intelligence Extraction"
              description="Don't extract action items & decisions"
              value={skipExtraction}
              onChange={setSkipExtraction}
            />
          </div>
        </div>

        {error && (
          <div className="px-4 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
            {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!file || loading}
          className={cn(
            "w-full py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all duration-200",
            !file || loading
              ? "bg-slate-800 text-slate-600 cursor-not-allowed"
              : "bg-gradient-to-r from-indigo-600 to-violet-600 text-white hover:from-indigo-500 hover:to-violet-500 shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 hover:-translate-y-0.5"
          )}
        >
          {loading ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Starting analysis…
            </>
          ) : (
            <>
              Analyze Meeting
              <ChevronRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>
    </div>
  );
}
