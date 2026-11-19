import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Cloud,
  FileCode,
  ClipboardList,
  Building2,
  Check,
  ArrowRight,
  ArrowLeft,
  Loader2,
  AlertCircle,
} from "lucide-react";
import clsx from "clsx";
import { createAccount, testConnection, startScan } from "@/services/api";
import type { ConnectionMethod, ConnectionCheck } from "@/types";

const STEPS = ["Method", "Credentials", "Test", "Complete"];

export default function ConnectAccountPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [method, setMethod] = useState<ConnectionMethod | null>(null);
  const [awsAccountId, setAwsAccountId] = useState("");
  const [accountName, setAccountName] = useState("");
  const [roleArn, setRoleArn] = useState("");
  const [externalId, setExternalId] = useState("");
  const [accountId, setAccountId] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<ConnectionCheck[] | null>(
    null,
  );

  const createMutation = useMutation({
    mutationFn: () =>
      createAccount({
        aws_account_id: awsAccountId,
        account_name: accountName || undefined,
        iam_role_arn: roleArn,
        external_id: externalId,
      }),
    onSuccess: (account) => {
      setAccountId(account.id);
      testMutation.mutate(account.id);
    },
  });

  const testMutation = useMutation({
    mutationFn: (id: string) => testConnection(id),
    onSuccess: (result) => {
      setTestResults(result.checks);
      setStep(2);
    },
  });

  const scanMutation = useMutation({
    mutationFn: (id: string) => startScan(id),
    onSuccess: (scan) => {
      navigate(`/scans/${scan.id}`);
    },
  });

  const handleCredentialsSubmit = () => {
    createMutation.mutate();
  };

  const methods: {
    id: ConnectionMethod;
    icon: React.ComponentType<{ className?: string }>;
    label: string;
    desc: string;
    recommended?: boolean;
  }[] = [
    {
      id: "cloudformation",
      icon: Cloud,
      label: "CloudFormation",
      desc: "One-click deploy. Creates a read-only IAM role.",
      recommended: true,
    },
    {
      id: "terraform",
      icon: FileCode,
      label: "Terraform / OpenTofu",
      desc: "Copy our module into your IaC. Same permissions.",
    },
    {
      id: "manual",
      icon: ClipboardList,
      label: "Manual IAM Setup",
      desc: "Step-by-step instructions for creating the role.",
    },
    {
      id: "organizations",
      icon: Building2,
      label: "AWS Organizations",
      desc: "Deploy across all accounts via StackSet.",
    },
  ];

  const allTestsPassed =
    testResults != null && testResults.every((c) => c.status === "success");

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold text-gray-900">
        Connect AWS Account
      </h1>
      <p className="mb-8 text-gray-500">
        Read-only access. We never modify your infrastructure during the scan.
      </p>

      {/* Stepper */}
      <div className="mb-10 flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className={clsx(
                "flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium",
                i < step
                  ? "bg-emerald-500 text-white"
                  : i === step
                    ? "bg-emerald-100 text-emerald-700 ring-2 ring-emerald-500"
                    : "bg-gray-100 text-gray-400",
              )}
            >
              {i < step ? <Check className="h-4 w-4" /> : i + 1}
            </div>
            <span
              className={clsx(
                "text-sm",
                i <= step ? "text-gray-800" : "text-gray-400",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 && (
              <div
                className={clsx(
                  "mx-2 h-px w-8",
                  i < step ? "bg-emerald-400" : "bg-gray-200",
                )}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step 0: Choose method */}
      {step === 0 && (
        <div className="space-y-3">
          {methods.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                setMethod(m.id);
                setStep(1);
              }}
              className={clsx(
                "flex w-full items-center gap-4 rounded-lg border p-4 text-left transition-colors hover:border-emerald-300 hover:bg-emerald-50/50",
                method === m.id
                  ? "border-emerald-400 bg-emerald-50"
                  : "border-gray-200 bg-white",
              )}
            >
              <m.icon className="h-6 w-6 text-gray-500" />
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-gray-800">{m.label}</span>
                  {m.recommended && (
                    <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-medium text-emerald-700">
                      Recommended
                    </span>
                  )}
                </div>
                <p className="text-sm text-gray-500">{m.desc}</p>
              </div>
              <ArrowRight className="h-4 w-4 text-gray-400" />
            </button>
          ))}
        </div>
      )}

      {/* Step 1: Enter credentials */}
      {step === 1 && (
        <div className="space-y-5 rounded-lg border border-gray-200 bg-white p-6">
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              AWS Account ID
            </label>
            <input
              type="text"
              value={awsAccountId}
              onChange={(e) => setAwsAccountId(e.target.value)}
              placeholder="123456789012"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Account Name{" "}
              <span className="text-gray-400">(optional)</span>
            </label>
            <input
              type="text"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
              placeholder="Production, Staging, etc."
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              IAM Role ARN
            </label>
            <input
              type="text"
              value={roleArn}
              onChange={(e) => setRoleArn(e.target.value)}
              placeholder="arn:aws:iam::123456789012:role/SafeScaleDiscovery"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              External ID
            </label>
            <input
              type="text"
              value={externalId}
              onChange={(e) => setExternalId(e.target.value)}
              placeholder="safescale-xxxxxxxx"
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500"
            />
          </div>

          {createMutation.isError && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              <AlertCircle className="h-4 w-4" />
              Failed to create account. Please check your inputs.
            </div>
          )}

          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setStep(0)}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <button
              onClick={handleCredentialsSubmit}
              disabled={
                !awsAccountId ||
                !roleArn ||
                !externalId ||
                createMutation.isPending ||
                testMutation.isPending
              }
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {createMutation.isPending || testMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Testing
                  connection...
                </>
              ) : (
                <>
                  Test Connection <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Test results */}
      {step === 2 && testResults && (
        <div className="space-y-5">
          <div className="rounded-lg border border-gray-200 bg-white p-6">
            <h3 className="mb-4 font-semibold text-gray-800">
              Connection Test Results
            </h3>
            <div className="space-y-2">
              {testResults.map((check) => (
                <div
                  key={check.service}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm odd:bg-gray-50"
                >
                  <span className="text-gray-700">{check.service}</span>
                  <span
                    className={clsx(
                      "font-medium",
                      check.status === "success" && "text-emerald-600",
                      check.status === "partial" && "text-amber-600",
                      check.status === "failed" && "text-red-600",
                    )}
                  >
                    {check.status === "success" && "✓ Success"}
                    {check.status === "partial" && "⚠ Partial"}
                    {check.status === "failed" && "✗ Failed"}
                    {check.message && (
                      <span className="ml-2 font-normal text-gray-400">
                        — {check.message}
                      </span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <button
              onClick={() => setStep(1)}
              className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
            >
              <ArrowLeft className="h-4 w-4" /> Back
            </button>
            <button
              onClick={() => setStep(3)}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            >
              {allTestsPassed ? "Continue" : "Continue Anyway"}{" "}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Complete */}
      {step === 3 && (
        <div className="rounded-lg border border-gray-200 bg-white p-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
            <Check className="h-7 w-7 text-emerald-600" />
          </div>
          <h3 className="mb-2 text-lg font-semibold text-gray-800">
            Account Connected!
          </h3>
          <p className="mb-6 text-gray-500">
            Ready to discover how much you can save. Start your first audit scan
            now.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => navigate("/accounts")}
              className="rounded-lg border border-gray-300 px-5 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
            >
              View Accounts
            </button>
            <button
              onClick={() => accountId && scanMutation.mutate(accountId)}
              disabled={!accountId || scanMutation.isPending}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {scanMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Starting...
                </>
              ) : (
                <>
                  Start Audit Scan <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
