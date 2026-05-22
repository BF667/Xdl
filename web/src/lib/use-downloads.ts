/**
 * Xdl Download Manager - React Hook for real-time state
 * Polls the FastAPI backend every 2 seconds for download state.
 */

"use client";

import { useState, useEffect, useCallback } from "react";
import { xdlApi, type DownloadItem, type Stats, type FullState } from "./api";

const POLL_INTERVAL = 2000;

export function useDownloads() {
  const [downloads, setDownloads] = useState<DownloadItem[]>([]);
  const [stats, setStats] = useState<Stats>({
    total: 0,
    active: 0,
    completed: 0,
    paused: 0,
    errors: 0,
    total_speed: "0 B/s",
    total_speed_bytes: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [dlRes, statsRes] = await Promise.all([
        xdlApi.listDownloads(),
        xdlApi.getStats(),
      ]);
      setDownloads(dlRes.downloads);
      setStats(statsRes);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to fetch downloads");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [refresh]);

  return { downloads, stats, loading, error, refresh };
}
