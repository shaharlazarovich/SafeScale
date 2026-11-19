import { useParams, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Pause,
  Play,
  Download,
  FileText,
  ListTree,
  CheckCircle2,
  Circle,
  Loader2,
  Clock,
  AlertCircle,
  XCircle,
  Wifi,
  WifiOff,
} from "lucide-react";
import clsx from "clsx";
import { getScan, pauseScan, resumeScan, exportScanLog } from "@/services/api";
import { useScanProgress } from "@/services/websocket";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import StatusBadge from "@/components/common/StatusBadge";
import type { PhaseProgress, AuditLogEntry, ScanSession } from "@/types";
import { useEffect, useRef } from "react";

const phaseLabels: Record<string, string> = {
  enumeration: "Resource Enumeration",
  topology_mapping: "Topology Mapping",
  ha_classification: "HA Classification",
  cost_analysis: "Cost Analysis",
  criticality_inference: "Criticality Inference",
  report_generation: "Report Generation",
  enrichment: "Enrichment (Optional)",
};

function PhaseIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-5 w-5 text-emerald-500" />;
    case "in_progress":
      return <Loader2 className="h-5 w-5 animate-spin text-blue-500" />;
    case "error":
      return <XCircle className="h-5 w-5 text-red-500" />;
    default:
      return <Circle className="h-5 w-5 text-gray-300" />;
  }
}

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const logEndRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const autoScrollRef = useRef(true);

  const { data: scan, isLoading } = useQuery({
    queryKey: ["scan", id],
    queryFn: () => getScan(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as ScanSession | undefined;
      return data?.status === "running" ? 5000 : false;
    },
  });

  const { progress, isConnected } = useScanProgress(
    scan?.status === "running" ? id : undefined,
  );

  const pauseMutation = useMutation({
    mutationFn: () => pauseScan(id!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", id] }),
  });

  const resumeMutation = useMutation({
    mutationFn: () => resumeScan(id!),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", id] }),
  });

  const handleExportLog = async () => {
    const blob = await exportScanLog(id!);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `safescale-scan-${id}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const logEntries = progress?.log_entries ?? [];

  useEffect(() => {
    if (autoScrollRef.current && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logEntries.length]);

  const handleLogScroll = () => {
    const el = logContainerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    autoScrollRef.current = atBottom;
  };

  if (isLoading || !scan) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const isRunning = scan.status === "running";
  const isPaused = scan.status === "paused";
  const isComplete = scan.status === "completed";
  const phases: PhaseProgress[] = progress?.phases ?? [];
  const overallPct = progress?.overall_pct ?? (isComplete ? 100 : 0);
  const totals = progress?.totals;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Scan</h1>
          <p className="text-sm text-gray-500">
            Scan ID: {id}
            {scan.started_at && (
              <>
                {" "}
                &middot; Started{" "}
                {new Date(scan.started_at).toLocaleString()}
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {isConnected ? (
            <span className="flex items-center gap-1 text-xs text-emerald-600">
              <Wifi className="h-3.5 w-3.5" /> Live
            </span>
          ) : isRunning ? (
            <span className="flex items-center gap-1 text-xs text-gray-400">
              <WifiOff className="h-3.5 w-3.5" /> Reconnecting...
            </span>
          ) : null}
          <StatusBadge status={scan.status} />
        </div>
      </div>

      {/* Overall progress */}
      <div className="mb-6 rounded-lg border border-gray-200 bg-white p-5">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-gray-700">Overall Progress</span>
          <span className="text-gray-500">{Math.round(overallPct)}%</span>
        </div>
        <div className="h-3 overflow-hidden rounded-full bg-gray-100">
          <div
            className={clsx(
              "h-full rounded-full transition-all duration-500",
              isComplete ? "bg-emerald-500" : "bg-blue-500",
            )}
            style={{ width: `${overallPct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Phases */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-4 font-semibold text-gray-800">Scan Phases</h2>
            <div className="space-y-3">
              {phases.map((phase) => (
                <div key={phase.phase} className="flex items-start gap-3">
                  <PhaseIcon status={phase.status} />
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-gray-800">
                        {phaseLabels[phase.phase] ?? phase.phase}
                      </span>
                      {phase.duration_seconds != null && (
                        <span className="text-xs text-gray-400">
                          {phase.duration_seconds < 60
                            ? `${phase.duration_seconds}s`
                            : `${Math.floor(phase.duration_seconds / 60)}m ${phase.duration_seconds % 60}s`}
                        </span>
                      )}
                    </div>
                    {phase.status === "in_progress" && (
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-gray-100">
                        <div
                          className="h-full rounded-full bg-blue-400 transition-all"
                          style={{ width: `${phase.progress_pct}%` }}
                        />
                      </div>
                    )}
                    {Object.values(phase.details).length > 0 && (
                      <div className="mt-1.5 space-y-0.5">
                        {Object.values(phase.details).map((sub) => (
                          <div
                            key={sub.label}
                            className="flex items-center gap-2 text-xs text-gray-500"
                          >
                            <PhaseIcon status={sub.status} />
                            <span>
                              {sub.label}
                              {sub.items_found > 0 && ` — ${sub.items_found} found`}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Live log */}
          <div className="rounded-lg border border-gray-200 bg-white">
            <div className="flex items-center justify-between border-b border-gray-100 px-5 py-3">
              <h2 className="text-sm font-semibold text-gray-800">Live Log</h2>
              <span className="text-xs text-gray-400">
                {autoScrollRef.current
                  ? "Auto-scrolling"
                  : "Scroll paused — scroll to bottom to resume"}
              </span>
            </div>
            <div
              ref={logContainerRef}
              onScroll={handleLogScroll}
              className="h-64 overflow-y-auto bg-gray-950 px-4 py-3 font-mono text-xs"
            >
              {logEntries.map((entry, i) => (
                <LogLine key={i} entry={entry} />
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>

        {/* Sidebar: totals + actions */}
        <div className="space-y-4">
          {/* Running totals */}
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 font-semibold text-gray-800">Running Totals</h2>
            <dl className="space-y-2.5 text-sm">
              <TotalRow
                label="Resources Discovered"
                value={totals?.resources_discovered ?? scan.resources_found}
              />
              <TotalRow
                label="Multi-AZ Eligible"
                value={totals?.multi_az_eligible ?? scan.multi_az_eligible}
              />
              <TotalRow
                label="Regions with Resources"
                value={totals?.regions_with_resources ?? scan.regions_scanned}
              />
              <TotalRow
                label="Dependencies Mapped"
                value={totals?.dependencies_mapped ?? 0}
              />
              <TotalRow
                label="Zombies Found"
                value={totals?.zombies_found ?? 0}
              />
              <div className="border-t border-gray-100 pt-2">
                <TotalRow
                  label="Est. Monthly Savings"
                  value={
                    totals?.estimated_savings != null
                      ? `$${totals.estimated_savings.toLocaleString()}`
                      : scan.estimated_monthly_savings != null
                        ? `$${scan.estimated_monthly_savings.toLocaleString()}`
                        : "Calculating..."
                  }
                  highlight
                />
              </div>
            </dl>
          </div>

          {/* Actions */}
          <div className="rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="mb-3 font-semibold text-gray-800">Actions</h2>
            <div className="space-y-2">
              {isRunning && (
                <button
                  onClick={() => pauseMutation.mutate()}
                  disabled={pauseMutation.isPending}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  <Pause className="h-4 w-4" /> Pause Scan
                </button>
              )}
              {isPaused && (
                <button
                  onClick={() => resumeMutation.mutate()}
                  disabled={resumeMutation.isPending}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
                >
                  <Play className="h-4 w-4" /> Resume Scan
                </button>
              )}
              <button
                onClick={handleExportLog}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                <Download className="h-4 w-4" /> Export Log
              </button>
              {isComplete && (
                <>
                  <Link
                    to={`/scans/${id}/resources`}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    <ListTree className="h-4 w-4" /> View Resources
                  </Link>
                  <Link
                    to={`/scans/${id}/log`}
                    className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    <FileText className="h-4 w-4" /> View Full Log
                  </Link>
                </>
              )}
            </div>
          </div>

          {/* Savings summary (when complete) */}
          {isComplete && scan.estimated_monthly_savings != null && (
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5">
              <h2 className="mb-3 font-semibold text-emerald-900">
                Savings Summary
              </h2>
              <dl className="space-y-2 text-sm">
                <TotalRow
                  label="Monthly Cloud Bill"
                  value={`$${(scan.total_monthly_cost ?? 0).toLocaleString()}`}
                />
                <TotalRow
                  label="Eligible Spend"
                  value={`$${(scan.eligible_spend ?? 0).toLocaleString()}`}
                />
                <TotalRow
                  label="Est. Monthly Savings"
                  value={`$${scan.estimated_monthly_savings.toLocaleString()}`}
                  highlight
                />
                <TotalRow
                  label="Est. Annual Savings"
                  value={`$${(scan.estimated_monthly_savings * 12).toLocaleString()}`}
                  highlight
                />
              </dl>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TotalRow({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string | number;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-gray-500">{label}</dt>
      <dd
        className={clsx(
          "font-semibold",
          highlight ? "text-emerald-700" : "text-gray-900",
        )}
      >
        {value}
      </dd>
    </div>
  );
}

function LogLine({ entry }: { entry: AuditLogEntry }) {
  const ts = new Date(entry.timestamp).toLocaleTimeString();

  const severityColor: Record<string, string> = {
    info: "text-gray-400",
    warning: "text-amber-400",
    error: "text-red-400",
    debug: "text-gray-600",
  };

  return (
    <div className="flex gap-2 leading-5">
      <span className="shrink-0 text-gray-600">{ts}</span>
      <span className={clsx("shrink-0", severityColor[entry.severity] ?? "text-gray-400")}>
        [{entry.phase ?? "SYS"}]
      </span>
      <span className="text-gray-300">{entry.message}</span>
    </div>
  );
}
