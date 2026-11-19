import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { getScanResources } from "@/services/api";
import DataTable, { type Column } from "@/components/common/DataTable";
import StatusBadge from "@/components/common/StatusBadge";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import type {
  DiscoveredResource,
  HAClassification,
  ConfidenceLevel,
  ScanResourcesParams,
} from "@/types";

export default function ScanResourcesPage() {
  const { id } = useParams<{ id: string }>();
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState("estimated_savings");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [filterService, setFilterService] = useState("");
  const [filterClassification, setFilterClassification] = useState("");
  const [filterConfidence, setFilterConfidence] = useState("");

  const params: ScanResourcesParams = {
    page,
    page_size: 25,
    sort_by: sortBy,
    sort_dir: sortDir,
    ...(filterService && { service: filterService }),
    ...(filterClassification && {
      ha_classification: filterClassification as HAClassification,
    }),
    ...(filterConfidence && {
      confidence: filterConfidence as ConfidenceLevel,
    }),
  };

  const { data, isLoading } = useQuery({
    queryKey: ["scan-resources", id, params],
    queryFn: () => getScanResources(id!, params),
    enabled: !!id,
  });

  const columns: Column<DiscoveredResource>[] = [
    {
      key: "resource_name",
      header: "Name / ARN",
      sortable: true,
      render: (r) => (
        <div>
          <p className="font-medium text-gray-900">
            {r.resource_name || r.arn.split(":").pop()}
          </p>
          <p className="truncate text-xs text-gray-400" title={r.arn}>
            {r.arn}
          </p>
        </div>
      ),
    },
    {
      key: "service",
      header: "Service",
      sortable: true,
      render: (r) => (
        <span className="text-sm text-gray-700">{r.service}</span>
      ),
    },
    {
      key: "region",
      header: "Region / AZ",
      sortable: true,
      render: (r) => (
        <div className="text-sm">
          <p className="text-gray-700">{r.region}</p>
          {r.availability_zone && (
            <p className="text-xs text-gray-400">{r.availability_zone}</p>
          )}
        </div>
      ),
    },
    {
      key: "is_multi_az",
      header: "Multi-AZ",
      render: (r) => (
        <span className={r.is_multi_az ? "text-amber-600" : "text-gray-400"}>
          {r.is_multi_az ? "Yes" : "No"}
        </span>
      ),
    },
    {
      key: "ha_classification",
      header: "Classification",
      sortable: true,
      render: (r) => <StatusBadge status={r.ha_classification} size="sm" />,
    },
    {
      key: "monthly_cost",
      header: "Monthly Cost",
      sortable: true,
      render: (r) =>
        r.monthly_cost != null ? (
          <span className="text-gray-700">
            ${r.monthly_cost.toLocaleString()}
          </span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: "estimated_savings",
      header: "Est. Savings",
      sortable: true,
      render: (r) =>
        r.estimated_savings != null && r.estimated_savings > 0 ? (
          <span className="font-medium text-emerald-600">
            ${r.estimated_savings.toLocaleString()}
            {r.savings_pct != null && (
              <span className="ml-1 text-xs text-gray-400">
                ({r.savings_pct}%)
              </span>
            )}
          </span>
        ) : (
          <span className="text-gray-400">—</span>
        ),
    },
    {
      key: "confidence",
      header: "Confidence",
      sortable: true,
      render: (r) => <StatusBadge status={r.confidence} size="sm" />,
    },
    {
      key: "criticality_tier",
      header: "Tier",
      sortable: true,
      render: (r) => (
        <span className="text-sm capitalize text-gray-600">
          {r.criticality_tier.replace("tier", "Tier ")}
        </span>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4">
        <Link
          to={`/scans/${id}`}
          className="mb-2 flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4" /> Back to scan
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">
          Discovered Resources
        </h1>
        <p className="text-sm text-gray-500">
          {data?.total ?? 0} resources found
        </p>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
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
          <option value="elb">ELB</option>
        </select>
        <select
          value={filterClassification}
          onChange={(e) => {
            setFilterClassification(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Classifications</option>
          <option value="eligible">Eligible</option>
          <option value="ineligible_builtin">Ineligible (Built-in)</option>
          <option value="ineligible_tier1">Ineligible (Tier-1)</option>
          <option value="partial">Partial</option>
        </select>
        <select
          value={filterConfidence}
          onChange={(e) => {
            setFilterConfidence(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
        >
          <option value="">All Confidence</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <DataTable
        columns={columns}
        data={data?.items ?? []}
        keyExtractor={(r) => r.id}
        page={page}
        pageSize={25}
        total={data?.total}
        onPageChange={setPage}
        sortBy={sortBy}
        sortDir={sortDir}
        onSortChange={(key, dir) => {
          setSortBy(key);
          setSortDir(dir);
        }}
      />
    </div>
  );
}
