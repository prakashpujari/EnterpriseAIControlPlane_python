/**
 * useMetrics Hook
 * Shared metrics state (tokens, cost, model, latency, quality) for the
 * chat + metrics panel. Implemented as a React context so the chat window
 * can push real per-response data and the MetricsPanel can display it.
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  ReactNode,
} from 'react';

export interface Metrics {
  tokens_input: number;
  tokens_output: number;
  cost: number;
  model_used: string;
  latency_ms: number;
  cache_hit_rate: number;
  quality_score: number;
}

// Approximate Groq pricing per 1M tokens (USD). Used to estimate cost.
const PRICING: Record<string, { in: number; out: number }> = {
  'llama-3.1-8b-instant': { in: 0.05, out: 0.08 },
  'llama-3.3-70b-versatile': { in: 0.59, out: 0.79 },
  'mixtral-8x7b-32768': { in: 0.24, out: 0.24 },
};

function costFor(model: string, inTokens: number, outTokens: number): number {
  const p = PRICING[model] ?? { in: 0.1, out: 0.1 };
  return (inTokens / 1_000_000) * p.in + (outTokens / 1_000_000) * p.out;
}

const DEFAULT_METRICS: Metrics = {
  tokens_input: 0,
  tokens_output: 0,
  cost: 0,
  model_used: '—',
  latency_ms: 0,
  cache_hit_rate: 0,
  quality_score: 1.0,
};

interface MetricsContextValue {
  metrics: Metrics;
  driftDetected: boolean;
  updateMetrics: (m: Partial<Metrics> & { is_valid?: boolean }) => void;
  resetMetrics: () => void;
}

const MetricsContext = createContext<MetricsContextValue | undefined>(undefined);

export function MetricsProvider({ children }: { children: ReactNode }) {
  const [metrics, setMetrics] = useState<Metrics>(DEFAULT_METRICS);
  const [driftDetected, setDriftDetected] = useState(false);

  const updateMetrics = useCallback(
    (m: Partial<Metrics> & { is_valid?: boolean }) => {
      setMetrics((prev) => {
        const tokens_input = prev.tokens_input + (m.tokens_input ?? 0);
        const tokens_output = prev.tokens_output + (m.tokens_output ?? 0);
        const cost =
          prev.cost +
          costFor(
            m.model_used ?? prev.model_used,
            m.tokens_input ?? 0,
            m.tokens_output ?? 0,
          );
        const quality =
          m.is_valid === false
            ? 0.5
            : m.is_valid === true
              ? 1.0
              : prev.quality_score;

        return {
          tokens_input,
          tokens_output,
          cost,
          model_used: m.model_used ?? prev.model_used,
          latency_ms: m.latency_ms ?? prev.latency_ms,
          cache_hit_rate: prev.cache_hit_rate,
          quality_score: quality,
        };
      });
    },
    [],
  );

  const resetMetrics = useCallback(() => {
    setMetrics(DEFAULT_METRICS);
    setDriftDetected(false);
  }, []);

  // Recompute drift whenever metrics change.
  useEffect(() => {
    const drift =
      metrics.quality_score < 0.7 || metrics.latency_ms > 5000;
    setDriftDetected(drift);
  }, [metrics]);

  return (
    <MetricsContext.Provider value={{ metrics, driftDetected, updateMetrics, resetMetrics }}>
      {children}
    </MetricsContext.Provider>
  );
}

export function useMetrics(): MetricsContextValue {
  const context = useContext(MetricsContext);
  if (!context) {
    throw new Error('useMetrics must be used within a MetricsProvider');
  }
  return context;
}
