import { useEffect, useState, useCallback } from 'react';

type Telemetry = {
  map?: string;
  mode?: string;
  elims?: number;
  deaths?: number;
  duration?: number;
};

type BotTuning = {
  aggression?: number;
  evasiveness?: number;
  range_preference?: string;
};

type CoachResponse = {
  telemetry?: Telemetry;
  coach?: {
    advice?: string[] | any;
    bot_tuning?: BotTuning;
  };
};

const DEFAULT_BASE = 'http://localhost:1326';

export function useCoach(pollMs: number = 10000) {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [advice, setAdvice] = useState<string[]>([]);
  const [botTuning, setBotTuning] = useState<BotTuning | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCoach = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${DEFAULT_BASE}/tf2/coach/advice`, {
        headers: { 'Accept': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: CoachResponse = await res.json();
      setTelemetry(data.telemetry || null);

      const tips = Array.isArray(data.coach?.advice)
        ? data.coach?.advice as string[]
        : data.coach?.advice
          ? [String(data.coach.advice)]
          : [];
      setAdvice(tips);

      setBotTuning(data.coach?.bot_tuning || null);
    } catch (err: any) {
      setError(err?.message || 'Failed to load coach data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCoach();
    const id = setInterval(fetchCoach, pollMs);
    return () => clearInterval(id);
  }, [fetchCoach, pollMs]);

  return { telemetry, advice, botTuning, loading, error, refresh: fetchCoach };
}
