import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, Search } from "lucide-react";
import clsx from "clsx";
import { getScanLog, exportScanLog } from "@/services/api";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import type { ScanPhase, AuditLogSeverity, ScanLogParams } from "@/types";

const severityStyles: Record<string, string> = {
  info: "text-blue-400",
  warning: "text-amber-400",
  error: "text-red-400",
  debug: "text-gray-500",
};

const severityBg: Record<string, string> = {
  info: "",
  warning: "bg-amber-950/20",
  error: "bg-red-950/30",
  debug: "",
};

export default function AuditLogPage() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(1);
  const [filterPhase, setFilterPhase] = useState("");
  const [filterService, setFilterService] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");

  const params: ScanLogParams = {
    page,
    page_size: 100,
    ...(filterPhase && { phase: filterPhase as ScanPhase }),
    ...(filterService && { service: filterService }),
    ...(filterSeverity && { severity: filterSeverity as AuditLogSeverity }),
    ...(searchQuery && { search: searchQuery }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["scan-log", id, params],
    queryFn: () => getScanLog(id!, params),
    enabled: !!id,
  });

  const handleExport = async () => {
    const blob = await exportScanLog(id!);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `safescale-scan-${id}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchQuery(searchInput);
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / 100) : 1;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <Link
            to={`/scans/${id}`}
            className="mb-2 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
          >
            <ArrowLeft className="h-4 w-4" /> Back to scan
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500">
            {data?.total ?? 0} log entries
          </p>
        </div>
        <button
          onClick={handleExport}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          <Download className="h-4 w-4" /> Export JSONL
        </button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select
          value={filterPhase}
          onChange={(e) => {
            setFilterPhase(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Phases</option>
          <option value="enumeration">Enumeration</option>
          <option value="topology_mapping">Topology Mapping</option>
          <option value="ha_classification">HA Classification</option>
          <option value="cost_analysis">Cost Analysis</option>
          <option value="criticality_inference">Criticality Inference</option>
          <option value="report_generation">Report Generation</option>
        </select>
        <select
          value={filterService}
          onChange={(e) => {
            setFilterService(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Services</option>
          <option value="rds">RDS</option>
          <option value="elasticache">ElastiCache</option>
          <option value="eks">EKS</option>
          <option value="ec2">EC2</option>
          <option value="ebs">EBS</option>
          <option value="ecs">ECS</option>
          <option value="opensearch">OpenSearch</option>
        </select>
        <select
          value={filterSeverity}
          onChange={(e) => {
            setFilterSeverity(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Severity</option>
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
          <option value="debug">Debug</option>
        </select>
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search log..."
              className="rounded-lg border border-gray-300 py-1.5 pl-8 pr-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-200"
          >
            Search
          </button>
        </form>
      </div>

      {isLoading ? (
        <div className="flex h-64 items-center justify-center">
          <LoadingSpinner size="lg" />
        </div>
      ) : (
        <>
          {/* Log viewer */}
          <div className="overflow-hidden rounded-lg border border-gray-200">
            <div className="overflow-x-auto bg-gray-950 font-mono text-xs">
              {data?.items.map((entry) => {
                const ts = new Date(entry.timestamp).toLocaleTimeString(
                  "en-US",
                  { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" },
                );
                return (
                  <div
                    key={entry.id}
                    className={clsx(
                      "flex gap-3 border-b border-gray-900 px-4 py-1 hover:bg-gray-800/50",
                      severityBg[entry.severity],
                    )}
                  >
                    <span className="shrink-0 text-gray-600">{ts}</span>
                    <span
                      className={clsx(
                        "w-16 shrink-0 text-right uppercase",
                        severityStyles[entry.severity],
                      )}
                    >
                      {entry.severity}
                    </span>
                    <span className="w-24 shrink-0 text-cyan-400">
                      {entry.phase ?? "system"}
                    </span>
                    <span className="w-16 shrink-0 text-purple-400">
                      {entry.service ?? ""}
                    </span>
                    <span className="text-gray-300">{entry.message}</span>
                    {entry.duration_ms != null && (
                      <span className="ml-auto shrink-0 text-gray-600">
                        {entry.duration_ms}ms
                      </span>
                    )}
                  </div>
                );
              })}
              {(!data || data.items.length === 0) && (
                <div className="px-4 py-8 text-center text-gray-500">
                  No log entries found
                </div>
              )}
            </div>
          </div>

          {/* Pagination */}
          {data && totalPages > 1 && (
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-gray-500">
                Page {page} of {totalPages} ({data.total} entries)
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                  className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-100 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages}
                  className="rounded border border-gray-300 px-3 py-1 hover:bg-gray-100 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
