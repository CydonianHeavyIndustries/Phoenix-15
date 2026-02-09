import { useEffect, useState, useCallback } from 'react';
import {
  getPhoenixState,
  setPhoenixHome,
  setPhoenixMood,
  getPhoenixInventoryLog,
  PhoenixState,
  PhoenixLogEntry,
} from '../api/client';

export function usePhoenix(pollMs: number = 8000) {
  const [state, setState] = useState<PhoenixState | null>(null);
  const [log, setLog] = useState<PhoenixLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPhoenixState();
      setState(res.state);
      const logRes = await getPhoenixInventoryLog(20);
      const parsed = Array.isArray(logRes.lines)
        ? logRes.lines.map((line: any) => (typeof line === 'string' ? JSON.parse(line) : line))
        : [];
      setLog(parsed as PhoenixLogEntry[]);
    } catch (err: any) {
      setError(err?.message || 'Failed to load Phoenix state');
    } finally {
      setLoading(false);
    }
  }, []);

  const changeHome = useCallback(async (home: 'home' | 'away' | 'sleep') => {
    await setPhoenixHome(home);
    refresh();
  }, [refresh]);

  const changeMood = useCallback(async (label: string, intensity?: number) => {
    await setPhoenixMood(label, intensity);
    refresh();
  }, [refresh]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { state, log, loading, error, refresh, changeHome, changeMood };
}
