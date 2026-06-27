// frontend/lib/usePolling.ts
"use client";

import { useEffect, useRef, useState, useCallback } from "react";

interface PollingState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Polls an async fetcher on an interval, exposing data/error/loading state.
 * Used throughout the dashboard for "live" panels (context counts, recent
 * actions, conversation feeds) without pulling in a full data-fetching
 * library for what is fundamentally a handful of polled GET requests.
 */
export function usePolling<T>(fetcher: () => Promise<T>, intervalMs = 5000, deps: any[] = []) {
  const [state, setState] = useState<PollingState<T>>({ data: null, error: null, loading: true });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const refetch = useCallback(async () => {
    try {
      const data = await fetcherRef.current();
      setState({ data, error: null, loading: false });
    } catch (err) {
      setState((prev) => ({
        data: prev.data,
        error: err instanceof Error ? err.message : "Unknown error",
        loading: false,
      }));
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      if (cancelled) return;
      await refetch();
    };
    
    setState((prev) => ({ ...prev, loading: true }));
    tick();
    
    const id = setInterval(tick, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refetch, intervalMs, ...deps]);

  return { ...state, refetch };
}
