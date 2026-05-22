/**
 * Xdl Download Manager - API Client
 * Communicates with the FastAPI backend via the Caddy gateway.
 */

const API_BASE = "/api";

function apiUrl(path: string): string {
  return `${API_BASE}${path}?XTransformPort=8000`;
}

export interface DownloadItem {
  id: string;
  url: string;
  filename: string;
  save_path: string;
  status: string;
  category: string;
  file_size: number;
  file_size_formatted: string;
  downloaded: number;
  downloaded_formatted: string;
  speed: number;
  speed_formatted: string;
  progress: number;
  num_segments: number;
  resume_supported: boolean;
  created_at: number;
  started_at: number | null;
  completed_at: number | null;
  eta: number;
  eta_formatted: string;
  error_message: string;
  site_name: string;
  is_media: boolean;
  media_format: string;
  media_quality: string;
}

export interface Stats {
  total: number;
  active: number;
  completed: number;
  paused: number;
  errors: number;
  total_speed: string;
  total_speed_bytes: number;
}

export interface Settings {
  default_save_path: string;
  max_concurrent: number;
  default_segments: number;
  proxy: string;
  user_agent: string;
  speed_limit_kb: number;
}

export interface DetectResult {
  site: string;
  filename: string;
  file_size: string;
  file_size_bytes?: number;
  category: string;
  error?: string;
}

export interface FullState {
  downloads: DownloadItem[];
  stats: Stats;
}

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(apiUrl(path), {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "API request failed");
  }
  return res.json();
}

export const xdlApi = {
  // Stats
  getStats: () => apiRequest<Stats>("/stats"),

  // Downloads
  addDownload: (data: {
    url: string;
    save_path?: string;
    download_type?: string;
    quality?: string;
    audio_format?: string;
    segments?: number;
  }) =>
    apiRequest<{ status: string; download: DownloadItem }>("/downloads", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  batchDownload: (urls: string[], save_path?: string) =>
    apiRequest<{ status: string; count: number }>("/downloads/batch", {
      method: "POST",
      body: JSON.stringify({ urls, save_path }),
    }),

  listDownloads: (category?: string) =>
    apiRequest<{ downloads: DownloadItem[] }>(
      `/downloads${category && category !== "All" ? `?category=${category}` : ""}`
    ),

  getDownload: (id: string) => apiRequest<DownloadItem>(`/downloads/${id}`),

  pauseDownload: (id: string) =>
    apiRequest<{ status: string }>(`/downloads/${id}/pause`, { method: "POST" }),

  resumeDownload: (id: string) =>
    apiRequest<{ status: string }>(`/downloads/${id}/resume`, { method: "POST" }),

  cancelDownload: (id: string) =>
    apiRequest<{ status: string }>(`/downloads/${id}/cancel`, { method: "POST" }),

  removeDownload: (id: string) =>
    apiRequest<{ status: string }>(`/downloads/${id}`, { method: "DELETE" }),

  // Detection
  detectUrl: (url: string) =>
    apiRequest<DetectResult>("/detect", {
      method: "POST",
      body: JSON.stringify({ url }),
    }),

  // Settings
  getSettings: () => apiRequest<Settings>("/settings"),

  updateSettings: (data: Partial<Settings>) =>
    apiRequest<{ status: string; settings: Settings }>("/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  // Sites
  getSupportedSites: () => apiRequest<{ sites: string[] }>("/sites"),

  // Health
  healthCheck: () => apiRequest<{ status: string; version: string }>("/health"),
};
