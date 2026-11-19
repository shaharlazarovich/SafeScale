import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Cloud, Search, DollarSign, AlertTriangle, Plus } from "lucide-react";
import { getAccounts, getScans } from "@/services/api";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import StatusBadge from "@/components/common/StatusBadge";

export default function Dashboard() {
  const { data: accounts, isLoading: loadingAccounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  const { data: scans, isLoading: loadingScans } = useQuery({
    queryKey: ["scans"],
    queryFn: () => getScans(),
  });

  if (loadingAccounts || loadingScans) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const hasAccounts = accounts && accounts.length > 0;
  const completedScans = scans?.filter((s) => s.status === "completed") ?? [];
  const totalSavings = completedScans.reduce(
    (sum, s) => sum + (s.estimated_monthly_savings ?? 0),
    0,
  );
  const latestScan = scans?.[0];

  if (!hasAccounts) {
    return (
      <div className="flex flex-col items-center justify-center py-24">
        <Cloud className="mb-4 h-16 w-16 text-gray-300" />
        <h2 className="mb-2 text-xl font-semibold text-gray-800">
          Welcome to SafeScale
        </h2>
        <p className="mb-6 max-w-md text-center text-gray-500">
          Connect your first AWS account to discover how much you're overpaying
          for cloud high availability.
        </p>
        <Link
          to="/accounts/connect"
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-emerald-700"
        >
          <Plus className="h-4 w-4" />
          Connect AWS Account
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Dashboard</h1>

      <div className="mb-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          icon={Cloud}
          label="Connected Accounts"
          value={accounts?.length ?? 0}
          color="blue"
        />
        <StatCard
          icon={Search}
          label="Total Scans"
          value={scans?.length ?? 0}
          color="purple"
        />
        <StatCard
          icon={DollarSign}
          label="Monthly Savings Found"
          value={`$${totalSavings.toLocaleString()}`}
          color="emerald"
        />
        <StatCard
          icon={AlertTriangle}
          label="Eligible Resources"
          value={completedScans.reduce((s, c) => s + c.multi_az_eligible, 0)}
          color="amber"
        />
      </div>

      {latestScan && (
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">
              Latest Scan
            </h2>
            <StatusBadge status={latestScan.status} />
          </div>
          <div className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
            <div>
              <span className="text-gray-500">Resources Found</span>
              <p className="text-lg font-semibold">
                {latestScan.resources_found}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Multi-AZ Eligible</span>
              <p className="text-lg font-semibold">
                {latestScan.multi_az_eligible}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Est. Monthly Savings</span>
              <p className="text-lg font-semibold text-emerald-600">
                ${(latestScan.estimated_monthly_savings ?? 0).toLocaleString()}
              </p>
            </div>
            <div>
              <span className="text-gray-500">Duration</span>
              <p className="text-lg font-semibold">
                {latestScan.duration_seconds
                  ? `${Math.floor(latestScan.duration_seconds / 60)}m ${latestScan.duration_seconds % 60}s`
                  : "—"}
              </p>
            </div>
          </div>
          <div className="mt-4">
            <Link
              to={`/scans/${latestScan.id}`}
              className="text-sm font-medium text-emerald-600 hover:text-emerald-700"
            >
              View scan details &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  color: string;
}) {
  const bgMap: Record<string, string> = {
    blue: "bg-blue-50 text-blue-600",
    purple: "bg-purple-50 text-purple-600",
    emerald: "bg-emerald-50 text-emerald-600",
    amber: "bg-amber-50 text-amber-600",
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="mb-3 flex items-center gap-3">
        <div className={`rounded-lg p-2 ${bgMap[color]}`}>
          <Icon className="h-5 w-5" />
        </div>
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
    </div>
  );
}
