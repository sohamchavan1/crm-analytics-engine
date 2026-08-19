"use client";

import { useState, useCallback } from "react";

export interface GenerationStep {
  step: number;
  total: number;
  message: string;
  detail?: string | null;
  status: "running" | "complete" | "error";
}

export interface GenerationResult {
  report_path: string;
  run_id?: string;
  message: string;
}

interface UseGenerationReturn {
  isRunning: boolean;
  steps: GenerationStep[];
  result: GenerationResult | null;
  error: string | null;
  startGeneration: (params: {
    upload_id: string;
    company: string;
    vertical_code: string;
    sections: string[];
  }) => void;
  reset: () => void;
}

/**
 * Hook that manages report generation with SSE progress streaming.
 *
 * Usage:
 *   const { isRunning, steps, result, error, startGeneration } = useGeneration();
 *   startGeneration({ upload_id, company, vertical_code, sections });
 */
export function useGeneration(): UseGenerationReturn {
  const [isRunning, setIsRunning] = useState(false);
  const [steps, setSteps] = useState<GenerationStep[]>([]);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reset = useCallback(() => {
    setIsRunning(false);
    setSteps([]);
    setResult(null);
    setError(null);
  }, []);

  const startGeneration = useCallback(
    async (params: {
      upload_id: string;
      company: string;
      vertical_code: string;
      sections: string[];
    }) => {
      reset();
      setIsRunning(true);
      setSteps([]);

      try {
        // POST with form data to get SSE stream
        const formData = new URLSearchParams();
        formData.set("upload_id", params.upload_id);
        formData.set("company", params.company);
        formData.set("vertical_code", params.vertical_code);
        formData.set("sections", params.sections.join(","));

        // Call FastAPI directly for SSE — Next.js rewrite proxy buffers streams
        const sseBase =
          typeof window !== "undefined" && window.location.hostname === "localhost"
            ? "http://localhost:8000"
            : "";
        const response = await fetch(`${sseBase}/api/generate/run`, {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: formData.toString(),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => null);
          throw new Error(errData?.detail || `Server error: ${response.status}`);
        }

        // Read SSE stream
        const reader = response.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let buffer = "";
        let gotFirstEvent = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Split on double-newline (SSE event boundary)
          // Process complete events, keep partial data in buffer
          let boundary = buffer.indexOf("\n\n");
          while (boundary !== -1) {
            const rawEvent = buffer.slice(0, boundary);
            buffer = buffer.slice(boundary + 2);

            // Parse the event block
            let eventType = "message";
            let eventData = "";

            for (const line of rawEvent.split("\n")) {
              if (line.startsWith("event: ")) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith("data: ")) {
                eventData += line.slice(6);
              } else if (line.startsWith(":")) {
                // SSE comment (keepalive) — ignore
              }
            }

            if (eventData) {
              try {
                const parsed = JSON.parse(eventData);

                if (eventType === "step") {
                  if (!gotFirstEvent) gotFirstEvent = true;
                  setSteps((prev) => {
                    const existing = prev.findIndex(
                      (s) => s.step === parsed.step
                    );
                    if (existing >= 0) {
                      const updated = [...prev];
                      updated[existing] = parsed;
                      return updated;
                    }
                    return [...prev, parsed];
                  });
                } else if (eventType === "complete") {
                  setResult(parsed);
                  setIsRunning(false);
                } else if (eventType === "error") {
                  setError(parsed.message);
                  setIsRunning(false);
                }
              } catch {
                // Skip malformed JSON
              }
            }

            boundary = buffer.indexOf("\n\n");
          }
        }

        // If stream ended without a complete/error event, mark as done
        if (!result && !error) {
          setIsRunning(false);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
        setIsRunning(false);
      }
    },
    [reset]
  );

  return { isRunning, steps, result, error, startGeneration, reset };
}
