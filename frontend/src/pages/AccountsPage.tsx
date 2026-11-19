import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { getAccounts } from "@/services/api";
import StatusBadge from "@/components/common/StatusBadge";
import LoadingSpinner from "@/components/common/LoadingSpinner";

export default function AccountsPage() {
  const { data: accounts, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">AWS Accounts</h1>
        <Link
          to="/accounts/connect"
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          <Plus className="h-4 w-4" />
          Connect Account
        </Link>
      </div>

      {!accounts || accounts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <p className="text-gray-500">No AWS accounts connected yet.</p>
          <Link
            to="/accounts/connect"
            className="mt-2 inline-block text-sm font-medium text-emerald-600 hover:text-emerald-700"
          >
            Connect your first account &rarr;
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {accounts.map((account) => (
            <div
              key={account.id}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-5"
            >
              <div className="flex items-center gap-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-sm font-bold text-blue-600">
                  AWS
                </div>
                <div>
                  <p className="font-semibold text-gray-900">
                    {account.account_name || account.aws_account_id}
                  </p>
                  <p className="text-sm text-gray-500">
                    {account.aws_account_id} &middot;{" "}
                    {account.regions_enabled.length} regions
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right text-sm">
                  <span className="text-gray-500">Last scan</span>
                  <p className="text-gray-700">
                    {account.last_scan_at
                      ? new Date(account.last_scan_at).toLocaleDateString()
                      : "Never"}
                  </p>
                </div>
                <StatusBadge status={account.status} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
