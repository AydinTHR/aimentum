import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "../api/client";

/** The backend caps audio at 90 seconds; stopping a hair early client-side
 * beats uploading something the server will reject. */
const MAX_SECONDS = 88;

/** Safari records audio/mp4, Chrome and Firefox webm/opus. The backend
 * transcodes everything through ffmpeg, so any of these is fine. */
const MIME_CANDIDATES = ["audio/mp4", "audio/webm;codecs=opus", "audio/webm"];

export type RecorderStatus = "idle" | "recording" | "transcribing";

export interface Recorder {
  status: RecorderStatus;
  seconds: number;
  error: string | undefined;
  supported: boolean;
  start: () => void;
  stop: () => void;
}

/** Voice capture for the morning check-in. The transcript lands in the
 * composer for the owner to confirm or fix; nothing is planned from raw
 * speech-to-text output. */
export function useRecorder(onTranscript: (text: string) => void): Recorder {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState<string>();
  const recorderRef = useRef<MediaRecorder | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onTranscriptRef = useRef(onTranscript);
  onTranscriptRef.current = onTranscript;

  const supported =
    typeof navigator !== "undefined" &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof MediaRecorder !== "undefined";

  const clearTimer = () => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const stop = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state === "recording") recorder.stop();
  }, []);

  const start = useCallback(async () => {
    setError(undefined);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Microphone access was declined. You can still type.");
      return;
    }

    const mimeType = MIME_CANDIDATES.find((candidate) => MediaRecorder.isTypeSupported(candidate));
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data);
    };
    recorder.onstop = async () => {
      clearTimer();
      stream.getTracks().forEach((track) => track.stop());
      recorderRef.current = null;
      const type = recorder.mimeType || "audio/webm";
      const extension = type.includes("mp4") ? "mp4" : "webm";
      setStatus("transcribing");
      try {
        const blob = new Blob(chunks, { type });
        const { transcript } = await api.transcribe(blob, `checkin.${extension}`);
        onTranscriptRef.current(transcript);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Transcription failed.");
      } finally {
        setStatus("idle");
      }
    };

    recorderRef.current = recorder;
    recorder.start();
    setSeconds(0);
    setStatus("recording");
    let elapsed = 0;
    timerRef.current = setInterval(() => {
      elapsed += 1;
      setSeconds(elapsed);
      if (elapsed >= MAX_SECONDS) stop();
    }, 1000);
  }, [stop]);

  useEffect(
    () => () => {
      clearTimer();
      const recorder = recorderRef.current;
      if (recorder && recorder.state === "recording") {
        recorder.stream.getTracks().forEach((track) => track.stop());
        recorder.stop();
      }
    },
    [],
  );

  return {
    status,
    seconds,
    error,
    supported,
    start: () => void start(),
    stop,
  };
}
