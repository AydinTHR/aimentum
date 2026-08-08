import { useState } from "react";

import { api } from "../api/client";
import type { MorningPlan } from "../api/types";
import { useRecorder } from "../lib/recorder";
import { MicIcon, StopIcon } from "./icons";
import { Button, Card, ErrorNote, SectionLabel } from "./ui";

interface Props {
  initialText?: string;
  onPlanned: (result: MorningPlan) => void;
  onCancel?: () => void;
}

/** The morning check-in. Voice lands here as editable text first: the plan
 * is always made from words the owner confirmed, never from raw STT. */
export function MorningComposer({ initialText = "", onPlanned, onCancel }: Props) {
  const [text, setText] = useState(initialText);
  const [usedVoice, setUsedVoice] = useState(false);
  const [planning, setPlanning] = useState(false);
  const [error, setError] = useState<string>();

  const recorder = useRecorder((transcript) => {
    setUsedVoice(true);
    setText((current) => (current.trim() ? `${current.trim()} ${transcript}` : transcript));
  });

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim() || planning) return;
    setPlanning(true);
    setError(undefined);
    try {
      const result = await api.morningCheckin(text.trim(), usedVoice ? "voice" : "text");
      onPlanned(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setPlanning(false);
    }
  }

  const recording = recorder.status === "recording";

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <SectionLabel>Morning check-in</SectionLabel>
        {onCancel && (
          <button onClick={onCancel} className="text-xs text-zinc-500 hover:text-zinc-300">
            Keep current plan
          </button>
        )}
      </div>
      <p className="mt-2 text-sm text-zinc-400">
        Say or type everything on your plate today. I will sort out what matters and block time for
        it.
      </p>
      <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={5}
          placeholder="Apply to the Shopify posting, follow up with Priya, gym at lunch..."
          aria-label="Morning check-in"
          className="resize-none rounded-xl border border-zinc-700 bg-zinc-950/60 px-3.5 py-3 text-sm leading-relaxed text-zinc-100 placeholder:text-zinc-600 focus:border-emerald-600 focus:outline-none"
        />
        <div className="flex items-center gap-3">
          {recorder.supported && (
            <button
              type="button"
              onClick={recording ? recorder.stop : recorder.start}
              disabled={recorder.status === "transcribing" || planning}
              aria-label={recording ? "Stop recording" : "Record your check-in"}
              className={`flex size-11 items-center justify-center rounded-full border transition-colors ${
                recording
                  ? "animate-pulse border-red-500/60 bg-red-500/15 text-red-300"
                  : "border-zinc-700 text-zinc-300 hover:border-zinc-500 disabled:text-zinc-600"
              }`}
            >
              {recording ? <StopIcon className="size-5" /> : <MicIcon className="size-5" />}
            </button>
          )}
          {recording && (
            <span className="text-sm tabular-nums text-red-300">
              {Math.floor(recorder.seconds / 60)}:{String(recorder.seconds % 60).padStart(2, "0")}
            </span>
          )}
          {recorder.status === "transcribing" && (
            <span className="text-sm text-zinc-400">Transcribing...</span>
          )}
          <div className="flex-1" />
          <Button type="submit" disabled={!text.trim() || planning || recording}>
            {planning ? "Planning..." : "Make my plan"}
          </Button>
        </div>
        {recorder.error && <ErrorNote>{recorder.error}</ErrorNote>}
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </Card>
  );
}
