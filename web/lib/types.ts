// lib/types.ts — shared TypeScript types for the Meeting Intelligence app

export type JobStatus =
  | "queued"
  | "preprocessing"
  | "transcribing"
  | "correcting"
  | "analyzing"
  | "extracting"
  | "complete"
  | "failed";

export interface Job {
  job_id: string;
  meeting_title: string;
  audio_filename: string;
  provider: string;
  status: JobStatus;
  progress: number;
  current_stage: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  has_results: boolean;
}

export interface Utterance {
  speaker: string;
  start: number;
  end: number;
  text: string;
}

export interface ParticipationStats {
  speaking_time_seconds: number;
  speaking_share_percent: number;
  utterance_count: number;
  average_words_per_utterance: number;
  longest_speaking_streak_seconds: number;
}

export interface SentimentEntry {
  speaker: string;
  start_sec: number;
  original_index: number;
  text: string;
  sentiment: "positive" | "negative" | "neutral";
  score: number;
  emotion: string;
  energy: "high" | "medium" | "low";
  flags: {
    is_frustrated: boolean;
    is_confused: boolean;
    is_agreeable: boolean;
    is_decisive: boolean;
  };
}

export interface SpeakerSentimentSummary {
  average_score: number;
  overall_sentiment: "positive" | "negative" | "neutral";
  dominant_emotion: string;
  utterance_count: number;
  flags: {
    frustrated_count: number;
    confused_count: number;
    agreeable_count: number;
    decisive_count: number;
  };
}

export interface ActionItem {
  action: string;
  owner: string;
  deadline: string | null;
  confidence: number;
  source_quote: string;
}

export interface Decision {
  decision: string;
  decided_by: string[];
  confidence: number;
  source_quote: string;
}

export interface FollowUp {
  topic: string;
  reason: string;
  owner: string | null;
}

export interface OpenQuestion {
  question: string;
  asked_by: string;
}

export interface Intelligence {
  action_items: ActionItem[];
  uncertain_action_items: ActionItem[];
  decisions: Decision[];
  uncertain_decisions: Decision[];
  follow_ups: FollowUp[];
  open_questions: OpenQuestion[];
}

export interface TopicSegment {
  segment_id: number;
  label: string;
  keywords: string[];
  speakers: string[];
  start_sec: number;
  end_sec: number;
  duration_sec: number;
  utterance_count: number;
}

export interface QualityScore {
  total: number;
  rating: "Excellent" | "Good" | "Fair" | "Needs Improvement" | "Poor";
  sub_scores: {
    participation: number;
    sentiment: number;
    decision_and_actions: number;
    interruption_control: number;
    engagement_consistency: number;
  };
}

export interface AnalysisResults {
  meeting_title: string;
  transcript: string;
  utterances: Utterance[];
  participation: Record<string, ParticipationStats>;
  interruptions: Array<{
    interrupter: string;
    interrupted: string;
    overlap_ms: number;
    text: string;
  }>;
  sentiment: {
    timeline: SentimentEntry[];
    speaker_summary: Record<string, SpeakerSentimentSummary>;
  };
  intelligence: Intelligence;
  topics: TopicSegment[];
  quality_score: QualityScore;
  recap_markdown: string;
  token_usage: {
    tokens_used: number;
    daily_limit: number;
    percent_used: number;
    status: "ok" | "warning" | "critical";
  };
}

export interface TokenUsage {
  date: string;
  tokens_used: number;
  calls: number;
  daily_limit: number;
  warn_threshold: number;
  remaining: number;
  percent_used: number;
  status: "ok" | "warning" | "critical";
  breakdown: Record<string, number>;
}
