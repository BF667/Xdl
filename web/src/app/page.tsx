"use client";

import { useState, useEffect, useCallback } from "react";
import { useDownloads } from "@/lib/use-downloads";
import { xdlApi, type DownloadItem, type DetectResult, type Settings } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Download,
  Play,
  Pause,
  X,
  Trash2,
  Search,
  Plus,
  Settings,
  Info,
  FolderDown,
  Zap,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
  Globe,
  FileVideo,
  FileAudio,
  FileText,
  Archive,
  ImageIcon,
  Package,
  HelpCircle,
} from "lucide-react";

// ─── Helpers ──────────────────────────────────────

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  pending: { color: "bg-gray-100 text-gray-700", icon: <Clock className="h-3.5 w-3.5" />, label: "Pending" },
  queued: { color: "bg-gray-100 text-gray-700", icon: <Clock className="h-3.5 w-3.5" />, label: "Queued" },
  downloading: { color: "bg-blue-50 text-blue-700", icon: <Download className="h-3.5 w-3.5" />, label: "Downloading" },
  paused: { color: "bg-amber-50 text-amber-700", icon: <Pause className="h-3.5 w-3.5" />, label: "Paused" },
  completed: { color: "bg-green-50 text-green-700", icon: <CheckCircle2 className="h-3.5 w-3.5" />, label: "Completed" },
  error: { color: "bg-red-50 text-red-700", icon: <AlertCircle className="h-3.5 w-3.5" />, label: "Error" },
  cancelled: { color: "bg-gray-100 text-gray-500", icon: <X className="h-3.5 w-3.5" />, label: "Cancelled" },
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  Video: <FileVideo className="h-4 w-4" />,
  Audio: <FileAudio className="h-4 w-4" />,
  Document: <FileText className="h-4 w-4" />,
  Compressed: <Archive className="h-4 w-4" />,
  Program: <Package className="h-4 w-4" />,
  Image: <ImageIcon className="h-4 w-4" />,
  Other: <HelpCircle className="h-4 w-4" />,
};

// ─── Stats Bar ──────────────────────────────────────

function StatsBar({ stats }: { stats: ReturnType<typeof useDownloads>["stats"] }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <Card className="py-3">
        <CardContent className="px-4 py-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Total</p>
              <p className="text-2xl font-bold">{stats.total}</p>
            </div>
            <FolderDown className="h-8 w-8 text-muted-foreground/40" />
          </div>
        </CardContent>
      </Card>
      <Card className="py-3">
        <CardContent className="px-4 py-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Active</p>
              <p className="text-2xl font-bold text-blue-600">{stats.active}</p>
            </div>
            <Download className="h-8 w-8 text-blue-400/40" />
          </div>
        </CardContent>
      </Card>
      <Card className="py-3">
        <CardContent className="px-4 py-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
            </div>
            <CheckCircle2 className="h-8 w-8 text-green-400/40" />
          </div>
        </CardContent>
      </Card>
      <Card className="py-3">
        <CardContent className="px-4 py-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted-foreground">Speed</p>
              <p className="text-lg font-bold">{stats.total_speed}</p>
            </div>
            <Zap className="h-8 w-8 text-amber-400/40" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Download Row ──────────────────────────────────────

function DownloadRow({
  item,
  onAction,
}: {
  item: DownloadItem;
  onAction: (id: string, action: string) => void;
}) {
  const statusCfg = STATUS_CONFIG[item.status] || STATUS_CONFIG.pending;
  const catIcon = CATEGORY_ICONS[item.category] || CATEGORY_ICONS.Other;
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const handleAction = async (action: string) => {
    setActionLoading(action);
    await onAction(item.id, action);
    setActionLoading(null);
  };

  return (
    <div className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
      {/* Category Icon */}
      <div className="shrink-0 p-2 rounded-md bg-muted">{catIcon}</div>

      {/* Main Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="font-medium text-sm truncate">{item.filename}</span>
          <Badge variant="outline" className={`text-xs px-1.5 py-0 ${statusCfg.color}`}>
            <span className="flex items-center gap-1">
              {statusCfg.icon}
              {statusCfg.label}
            </span>
          </Badge>
        </div>

        {/* Progress Bar */}
        {(item.status === "downloading" || item.status === "paused") && (
          <div className="mb-1">
            <Progress value={item.progress} className="h-1.5" />
          </div>
        )}

        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{item.file_size_formatted}</span>
          {item.status === "downloading" && (
            <>
              <span>{item.progress}%</span>
              <span>{item.speed_formatted}</span>
              <span>ETA: {item.eta_formatted}</span>
            </>
          )}
          {item.status === "completed" && item.downloaded_formatted && (
            <span>{item.downloaded_formatted}</span>
          )}
          {item.error_message && (
            <span className="text-destructive truncate max-w-[200px]">{item.error_message}</span>
          )}
        </div>
      </div>

      {/* Site Badge */}
      <Badge variant="secondary" className="shrink-0 text-xs">
        <Globe className="h-3 w-3 mr-1" />
        {item.site_name || "Unknown"}
      </Badge>

      {/* Action Buttons */}
      <div className="flex items-center gap-1 shrink-0">
        {item.status === "downloading" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAction("pause")}
            disabled={actionLoading !== null}
          >
            {actionLoading === "pause" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Pause className="h-4 w-4" />
            )}
          </Button>
        )}
        {(item.status === "paused" || item.status === "error") && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAction("resume")}
            disabled={actionLoading !== null}
          >
            {actionLoading === "resume" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </Button>
        )}
        {item.status === "downloading" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAction("cancel")}
            disabled={actionLoading !== null}
          >
            {actionLoading === "cancel" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <X className="h-4 w-4" />
            )}
          </Button>
        )}
        {item.status !== "downloading" && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => handleAction("remove")}
            disabled={actionLoading !== null}
          >
            {actionLoading === "remove" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Add Download Tab ──────────────────────────────────────

function AddDownloadTab({ onAdded }: { onAdded: () => void }) {
  const [url, setUrl] = useState("");
  const [savePath, setSavePath] = useState("");
  const [downloadType, setDownloadType] = useState("Video");
  const [quality, setQuality] = useState("Best Quality");
  const [audioFormat, setAudioFormat] = useState("MP3");
  const [segments, setSegments] = useState(8);
  const [detectResult, setDetectResult] = useState<DetectResult | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: "success" | "error" } | null>(null);

  // Batch state
  const [batchUrls, setBatchUrls] = useState("");
  const [batchAdding, setBatchAdding] = useState(false);

  useEffect(() => {
    xdlApi.getSettings().then((s) => setSavePath(s.default_save_path)).catch(() => {});
  }, []);

  const handleDetect = async () => {
    if (!url.trim()) return;
    setDetecting(true);
    try {
      const result = await xdlApi.detectUrl(url.trim());
      setDetectResult(result);
    } catch (err: any) {
      setDetectResult({ site: "Error", filename: "", file_size: "", category: "", error: err.message });
    } finally {
      setDetecting(false);
    }
  };

  const handleAdd = async () => {
    if (!url.trim()) return;
    setAdding(true);
    setMessage(null);
    try {
      await xdlApi.addDownload({
        url: url.trim(),
        save_path: savePath,
        download_type: downloadType,
        quality,
        audio_format: audioFormat,
        segments,
      });
      setMessage({ text: `Download started: ${detectResult?.filename || url}`, type: "success" });
      setUrl("");
      setDetectResult(null);
      onAdded();
    } catch (err: any) {
      setMessage({ text: err.message || "Failed to add download", type: "error" });
    } finally {
      setAdding(false);
    }
  };

  const handleBatch = async () => {
    if (!batchUrls.trim()) return;
    setBatchAdding(true);
    try {
      const urls = batchUrls
        .split("\n")
        .map((u) => u.trim())
        .filter((u) => u.startsWith("http://") || u.startsWith("https://"));
      if (urls.length === 0) {
        setMessage({ text: "No valid URLs found", type: "error" });
        return;
      }
      const result = await xdlApi.batchDownload(urls, savePath);
      setMessage({ text: `Added ${result.count} downloads`, type: "success" });
      setBatchUrls("");
      onAdded();
    } catch (err: any) {
      setMessage({ text: err.message, type: "error" });
    } finally {
      setBatchAdding(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Add Download</CardTitle>
          <CardDescription>Paste a URL to download. Supports YouTube, Google Drive, MediaFire, and 1000+ other sites.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* URL Input */}
          <div className="flex gap-2">
            <div className="flex-1">
              <Input
                placeholder="Paste URL here (YouTube, Google Drive, any direct link...)"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleDetect()}
              />
            </div>
            <Button variant="outline" onClick={handleDetect} disabled={detecting || !url.trim()}>
              {detecting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
              Detect
            </Button>
          </div>

          {/* Detect Result */}
          {detectResult && (
            <Card className="bg-muted/50">
              <CardContent className="py-3 px-4">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground">Site</p>
                    <p className="font-medium">{detectResult.site}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Filename</p>
                    <p className="font-medium truncate">{detectResult.filename || "Unknown"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Size</p>
                    <p className="font-medium">{detectResult.file_size || "Unknown"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Category</p>
                    <p className="font-medium">{detectResult.category || "Unknown"}</p>
                  </div>
                </div>
                {detectResult.error && (
                  <p className="text-xs text-destructive mt-2">{detectResult.error}</p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Save Path */}
          <div>
            <Label className="text-sm">Save Path</Label>
            <Input value={savePath} onChange={(e) => setSavePath(e.target.value)} className="mt-1" />
          </div>

          {/* Download Options */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="text-sm">Download Type</Label>
              <RadioGroup
                value={downloadType}
                onValueChange={setDownloadType}
                className="flex gap-4 mt-2"
              >
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="Video" id="video" />
                  <Label htmlFor="video" className="flex items-center gap-1">
                    <FileVideo className="h-4 w-4" /> Video
                  </Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="Audio" id="audio" />
                  <Label htmlFor="audio" className="flex items-center gap-1">
                    <FileAudio className="h-4 w-4" /> Audio
                  </Label>
                </div>
              </RadioGroup>
            </div>

            {downloadType === "Video" ? (
              <div>
                <Label className="text-sm">Video Quality</Label>
                <Select value={quality} onValueChange={setQuality}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Best Quality">Best Quality</SelectItem>
                    <SelectItem value="720p">720p</SelectItem>
                    <SelectItem value="480p">480p</SelectItem>
                    <SelectItem value="360p">360p</SelectItem>
                    <SelectItem value="240p">240p</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <div>
                <Label className="text-sm">Audio Format</Label>
                <Select value={audioFormat} onValueChange={setAudioFormat}>
                  <SelectTrigger className="mt-1">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="MP3">MP3</SelectItem>
                    <SelectItem value="AAC">AAC</SelectItem>
                    <SelectItem value="FLAC">FLAC</SelectItem>
                    <SelectItem value="Opus">Opus</SelectItem>
                    <SelectItem value="WAV">WAV</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
          </div>

          {/* Segments */}
          <div>
            <div className="flex items-center justify-between">
              <Label className="text-sm">Download Segments</Label>
              <span className="text-sm text-muted-foreground">{segments} segment{segments !== 1 ? "s" : ""}</span>
            </div>
            <Slider
              value={[segments]}
              onValueChange={([v]) => setSegments(v)}
              min={1}
              max={32}
              step={1}
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-1">More segments = faster for large files</p>
          </div>

          {/* Add Button */}
          <Button onClick={handleAdd} disabled={adding || !url.trim()} className="w-full" size="lg">
            {adding ? (
              <Loader2 className="h-5 w-5 animate-spin mr-2" />
            ) : (
              <Download className="h-5 w-5 mr-2" />
            )}
            Start Download
          </Button>

          {/* Message */}
          {message && (
            <div
              className={`text-sm p-3 rounded-md ${
                message.type === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"
              }`}
            >
              {message.text}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Batch Download */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Batch Download</CardTitle>
          <CardDescription>Add multiple URLs at once (one per line)</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <Textarea
            placeholder={"https://youtube.com/watch?v=...\nhttps://vimeo.com/...\nhttps://example.com/file.zip"}
            value={batchUrls}
            onChange={(e) => setBatchUrls(e.target.value)}
            rows={4}
          />
          <Button onClick={handleBatch} disabled={batchAdding} className="w-full">
            {batchAdding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
            Add All URLs
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Downloads Tab ──────────────────────────────────────

function DownloadsTab({
  downloads,
  onAction,
}: {
  downloads: DownloadItem[];
  onAction: (id: string, action: string) => void;
}) {
  const [filter, setFilter] = useState("All");
  const filters = [
    "All", "Active", "Completed", "Paused", "Error",
    "Video", "Audio", "Document", "Compressed", "Program", "Image", "Other",
  ];

  const filtered = downloads.filter((item) => {
    if (filter === "All") return true;
    if (filter === "Active") return item.status === "downloading";
    if (filter === "Completed") return item.status === "completed";
    if (filter === "Paused") return item.status === "paused";
    if (filter === "Error") return item.status === "error";
    return item.category === filter;
  });

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="flex flex-wrap gap-2">
        {filters.map((f) => (
          <Button
            key={f}
            variant={filter === f ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter(f)}
          >
            {f}
            {f !== "All" && (
              <span className="ml-1 text-xs opacity-60">
                {f === "Active"
                  ? downloads.filter((d) => d.status === "downloading").length
                  : f === "Completed"
                  ? downloads.filter((d) => d.status === "completed").length
                  : f === "Paused"
                  ? downloads.filter((d) => d.status === "paused").length
                  : f === "Error"
                  ? downloads.filter((d) => d.status === "error").length
                  : downloads.filter((d) => d.category === f).length}
              </span>
            )}
          </Button>
        ))}
      </div>

      {/* Download List */}
      {filtered.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <FolderDown className="h-12 w-12 mx-auto text-muted-foreground/30 mb-3" />
            <p className="text-muted-foreground">No downloads {filter !== "All" ? `in "${filter}"` : "yet"}</p>
            <p className="text-sm text-muted-foreground/60 mt-1">Add a download from the "Add Download" tab</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
          {filtered.map((item) => (
            <DownloadRow key={item.id} item={item} onAction={onAction} />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── URL Info Tab ──────────────────────────────────────

function UrlInfoTab() {
  const [url, setUrl] = useState("");
  const [result, setResult] = useState<DetectResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    if (!url.trim()) return;
    setLoading(true);
    try {
      const r = await xdlApi.detectUrl(url.trim());
      setResult(r);
    } catch (err: any) {
      setResult({ site: "Error", filename: "", file_size: "", category: "", error: err.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">URL Analyzer</CardTitle>
          <CardDescription>Analyze any URL to get download information before downloading.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Enter any URL to analyze..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
              className="flex-1"
            />
            <Button onClick={handleAnalyze} disabled={loading || !url.trim()}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Search className="h-4 w-4 mr-1" />}
              Analyze
            </Button>
          </div>

          {result && (
            <Card className="bg-muted/50">
              <CardContent className="py-4 px-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Site</p>
                    <p className="font-medium text-lg">{result.site}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Filename</p>
                    <p className="font-medium">{result.filename || "Unknown"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">File Size</p>
                    <p className="font-medium">{result.file_size || "Unknown"}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Category</p>
                    <p className="font-medium">{result.category || "Unknown"}</p>
                  </div>
                </div>
                {result.error && (
                  <p className="text-sm text-destructive mt-3">{result.error}</p>
                )}
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>

      {/* Supported Sites Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Supported Sites</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { cat: "Video", sites: "YouTube, Vimeo, Dailymotion, TikTok, Twitch, Rumble, Odysee, Bilibili, and 900+ more" },
              { cat: "Social", sites: "Twitter/X, Facebook, Instagram, Reddit" },
              { cat: "Audio", sites: "SoundCloud, Bandcamp, Audiomack, Mixcloud" },
              { cat: "Cloud", sites: "Google Drive, MediaFire, Pixeldrain, HuggingFace" },
              { cat: "Generic", sites: "Any HTTP/HTTPS direct download link" },
            ].map((row) => (
              <div key={row.cat} className="flex gap-3 p-3 rounded-md border">
                <div className="shrink-0">
                  {CATEGORY_ICONS[row.cat] || <Globe className="h-4 w-4" />}
                </div>
                <div>
                  <p className="font-medium text-sm">{row.cat}</p>
                  <p className="text-xs text-muted-foreground">{row.sites}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Settings Tab ──────────────────────────────────────

function SettingsTab() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    xdlApi
      .getSettings()
      .then(setSettings)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    setMessage(null);
    try {
      const result = await xdlApi.updateSettings(settings);
      setSettings(result.settings);
      setMessage("Settings saved successfully!");
    } catch (err: any) {
      setMessage(err.message || "Failed to save settings");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!settings) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <AlertCircle className="h-12 w-12 mx-auto text-destructive mb-3" />
          <p className="text-muted-foreground">Could not load settings. Make sure the API server is running.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">General Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm">Default Save Path</Label>
            <Input
              value={settings.default_save_path}
              onChange={(e) => setSettings({ ...settings, default_save_path: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-sm">Max Concurrent Downloads</Label>
            <Slider
              value={[settings.max_concurrent]}
              onValueChange={([v]) => setSettings({ ...settings, max_concurrent: v })}
              min={1}
              max={10}
              step={1}
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-1">{settings.max_concurrent} simultaneous downloads</p>
          </div>
          <div>
            <Label className="text-sm">Default Segments</Label>
            <Slider
              value={[settings.default_segments]}
              onValueChange={([v]) => setSettings({ ...settings, default_segments: v })}
              min={1}
              max={32}
              step={1}
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-1">{settings.default_segments} segments per download</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Connection Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label className="text-sm">Proxy Server</Label>
            <Input
              placeholder="http://proxy:port or socks5://proxy:port"
              value={settings.proxy}
              onChange={(e) => setSettings({ ...settings, proxy: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-sm">Custom User-Agent</Label>
            <Input
              placeholder="Leave empty for default"
              value={settings.user_agent}
              onChange={(e) => setSettings({ ...settings, user_agent: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <Label className="text-sm">Speed Limit (KB/s, 0 = unlimited)</Label>
            <Input
              type="number"
              value={settings.speed_limit_kb}
              onChange={(e) => setSettings({ ...settings, speed_limit_kb: parseInt(e.target.value) || 0 })}
              className="mt-1"
            />
          </div>
        </CardContent>
      </Card>

      <Button onClick={handleSave} disabled={saving} className="w-full" size="lg">
        {saving ? <Loader2 className="h-5 w-5 animate-spin mr-2" /> : <Settings className="h-5 w-5 mr-2" />}
        Save Settings
      </Button>

      {message && (
        <div className="text-sm p-3 rounded-md bg-green-50 text-green-700">{message}</div>
      )}
    </div>
  );
}

// ─── About Tab ──────────────────────────────────────

function AboutTab() {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 p-4 rounded-full bg-primary/10 w-fit">
            <Download className="h-10 w-10 text-primary" />
          </div>
          <CardTitle className="text-2xl">Xdl Download Manager</CardTitle>
          <CardDescription className="text-base">v2.0.0 — Open-source IDM Alternative</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-center text-muted-foreground mb-6">
            A powerful, feature-rich download manager that supports video/audio downloads from 1000+ sites,
            cloud storage services, and generic HTTP/HTTPS file downloads.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { icon: <Zap className="h-5 w-5" />, title: "Multi-threaded", desc: "Up to 32 segments for maximum speed" },
              { icon: <Play className="h-5 w-5" />, title: "Resume Support", desc: "Pause and resume downloads anytime" },
              { icon: <Globe className="h-5 w-5" />, title: "1000+ Video Sites", desc: "YouTube, Vimeo, TikTok, Twitter, and more" },
              { icon: <FileAudio className="h-5 w-5" />, title: "Audio Extraction", desc: "Convert videos to MP3, AAC, FLAC, Opus, WAV" },
              { icon: <FolderDown className="h-5 w-5" />, title: "Cloud Storage", desc: "Google Drive, MediaFire, Pixeldrain, HuggingFace" },
              { icon: <Archive className="h-5 w-5" />, title: "Smart Categories", desc: "Auto-organize by file type" },
              { icon: <Plus className="h-5 w-5" />, title: "Batch Download", desc: "Add multiple URLs at once" },
              { icon: <Settings className="h-5 w-5" />, title: "CLI + Web + GUI", desc: "Multiple interfaces for every use case" },
            ].map((f) => (
              <div key={f.title} className="flex gap-3 p-3 rounded-md border">
                <div className="shrink-0 p-2 rounded-md bg-muted">{f.icon}</div>
                <div>
                  <p className="font-medium text-sm">{f.title}</p>
                  <p className="text-xs text-muted-foreground">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Powered By</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-center text-sm">
            {[
              { name: "yt-dlp", desc: "Video/Audio Engine" },
              { name: "FastAPI", desc: "Backend API" },
              { name: "Next.js", desc: "Web Frontend" },
              { name: "requests", desc: "HTTP Library" },
            ].map((lib) => (
              <div key={lib.name} className="p-3 rounded-md border">
                <p className="font-medium">{lib.name}</p>
                <p className="text-xs text-muted-foreground">{lib.desc}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="py-4 text-center">
          <p className="text-sm text-muted-foreground">
            Licensed under the{" "}
            <span className="font-medium">Unlicense</span> — Free and unencumbered software released into the public domain.
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            GitHub: <span className="font-medium">https://github.com/BF667/Xdl</span>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

// ─── Main Page ──────────────────────────────────────

export default function XdlDownloadManager() {
  const { downloads, stats, loading, error, refresh } = useDownloads();
  const [activeTab, setActiveTab] = useState("add");
  const [apiStatus, setApiStatus] = useState<"checking" | "online" | "offline">("checking");

  useEffect(() => {
    xdlApi
      .healthCheck()
      .then(() => setApiStatus("online"))
      .catch(() => setApiStatus("offline"));
  }, []);

  const handleAction = useCallback(
    async (id: string, action: string) => {
      try {
        switch (action) {
          case "pause":
            await xdlApi.pauseDownload(id);
            break;
          case "resume":
            await xdlApi.resumeDownload(id);
            break;
          case "cancel":
            await xdlApi.cancelDownload(id);
            break;
          case "remove":
            await xdlApi.removeDownload(id);
            break;
        }
        refresh();
      } catch (err: any) {
        console.error("Action failed:", err);
      }
    },
    [refresh]
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b bg-card">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-primary text-primary-foreground">
                <Download className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-xl font-bold">Xdl Download Manager</h1>
                <p className="text-xs text-muted-foreground">Open-source IDM alternative | 1000+ sites | Multi-threaded</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge
                variant={apiStatus === "online" ? "default" : apiStatus === "offline" ? "destructive" : "secondary"}
                className="text-xs"
              >
                {apiStatus === "checking" && <Loader2 className="h-3 w-3 mr-1 animate-spin" />}
                {apiStatus === "online" && <CheckCircle2 className="h-3 w-3 mr-1" />}
                {apiStatus === "offline" && <AlertCircle className="h-3 w-3 mr-1" />}
                {apiStatus === "checking" ? "Connecting..." : apiStatus === "online" ? "API Online" : "API Offline"}
              </Badge>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-4">
            <StatsBar stats={stats} />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {apiStatus === "offline" && (
          <Card className="mb-6 border-destructive/50 bg-destructive/5">
            <CardContent className="py-4 flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-destructive shrink-0" />
              <div>
                <p className="font-medium text-sm">API Server is not running</p>
                <p className="text-xs text-muted-foreground">
                  Start the backend with: <code className="bg-muted px-1.5 py-0.5 rounded text-xs">python3 api.py</code>
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-5 mb-6">
            <TabsTrigger value="add" className="gap-1.5">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Add Download</span>
            </TabsTrigger>
            <TabsTrigger value="downloads" className="gap-1.5">
              <Download className="h-4 w-4" />
              <span className="hidden sm:inline">Downloads</span>
              {stats.active > 0 && (
                <Badge variant="default" className="h-5 w-5 p-0 text-[10px] flex items-center justify-center">
                  {stats.active}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="info" className="gap-1.5">
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">URL Info</span>
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-1.5">
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">Settings</span>
            </TabsTrigger>
            <TabsTrigger value="about" className="gap-1.5">
              <Info className="h-4 w-4" />
              <span className="hidden sm:inline">About</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="add">
            <AddDownloadTab onAdded={refresh} />
          </TabsContent>

          <TabsContent value="downloads">
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <DownloadsTab downloads={downloads} onAction={handleAction} />
            )}
          </TabsContent>

          <TabsContent value="info">
            <UrlInfoTab />
          </TabsContent>

          <TabsContent value="settings">
            <SettingsTab />
          </TabsContent>

          <TabsContent value="about">
            <AboutTab />
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t mt-8">
        <div className="max-w-6xl mx-auto px-4 py-4 text-center text-xs text-muted-foreground">
          Xdl Download Manager v2.0.0 — FastAPI + Next.js TypeScript — Open-source IDM Alternative
        </div>
      </footer>
    </div>
  );
}
