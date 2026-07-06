/**
 * useMetrics Hook
 * Manages metrics state and drift detection
 */

import { useState, useEffect, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

interface Metrics {
  tokens_input: number;
  tokens_output: number;
  cost: number;
  model_used: string;
  latency_ms: number;
  cache_hit_rate: number;
  quality_score: number;
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

const driftThresholds = {
  quality: 0.7,
  cost: 1.5, // 50% increase
  latency: 5000, // 5 seconds
};

export function useMetrics() {
  const [metrics, setMetrics] = useState<Metrics>({
    tokens_input: 0,
    tokens_output: 0,
    cost: 0,
    model_used: 'claude-3-sonnet-20240229',
    latency_ms: 0,
    cache_hit_rate: 0,
    quality_score: 1.0,
  });

  const [driftDetected, setDriftDetected] = useState(false);

  // Update metrics after each message
  const updateMetrics = useCallback((newMetrics: Partial<Metrics>) => {
    setMetrics((prev) => ({ ...prev, ...newMetrics }));
  }, []);

  // Check for drift
  useEffect(() => {
    let drift = false;

    if (metrics.quality_score < driftThresholds.quality) {
      drift = true;
    }

    if (metrics.latency_ms > driftThresholds.latency) {
      drift = true;
    }

    setDriftDetected(drift);
  }, [metrics]);

  // Reset metrics
  const resetMetrics = useCallback(() => {
    setMetrics({
      tokens_input: 0,
      tokens_output: 0,
      cost: 0,
      model_used: 'claude-3-sonnet-20240229',
      latency_ms: 0,
      cache_hit_rate: 0,
      quality_score: 1.0,
    });
    setDriftDetected(false);
  }, []);

  return {
    metrics,
    driftDetected,
    updateMetrics,
    resetMetrics,
  };
}
