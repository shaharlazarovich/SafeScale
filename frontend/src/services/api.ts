import axios from "axios";
import type {
  CloudAccount,
  ScanSession,
  DiscoveredResource,
  AuditLogEntry,
  ConnectionTestResult,
  CreateAccountPayload,
  PaginatedResponse,
  ScanResourcesParams,
  ScanLogParams,
} from "@/types";

const client = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

export async function getAccounts(): Promise<CloudAccount[]> {
  const { data } = await client.get<CloudAccount[]>("/accounts");
  return data;
}

export async function getAccount(accountId: string): Promise<CloudAccount> {
  const { data } = await client.get<CloudAccount>(`/accounts/${accountId}`);
  return data;
}

export async function createAccount(
  payload: CreateAccountPayload,
): Promise<CloudAccount> {
  const { data } = await client.post<CloudAccount>("/accounts", payload);
  return data;
}

export async function testConnection(
  accountId: string,
): Promise<ConnectionTestResult> {
  const { data } = await client.post<ConnectionTestResult>(
    `/accounts/${accountId}/test-connection`,
  );
  return data;
}

export async function getScans(accountId?: string): Promise<ScanSession[]> {
  const params = accountId ? { account_id: accountId } : undefined;
  const { data } = await client.get<ScanSession[]>("/scans", { params });
  return data;
}

export async function getScan(scanId: string): Promise<ScanSession> {
  const { data } = await client.get<ScanSession>(`/scans/${scanId}`);
  return data;
}

export async function startScan(accountId: string): Promise<ScanSession> {
  const { data } = await client.post<ScanSession>("/scans", {
    account_id: accountId,
  });
  return data;
}

export async function pauseScan(scanId: string): Promise<ScanSession> {
  const { data } = await client.post<ScanSession>(`/scans/${scanId}/pause`);
  return data;
}

export async function resumeScan(scanId: string): Promise<ScanSession> {
  const { data } = await client.post<ScanSession>(`/scans/${scanId}/resume`);
  return data;
}

export async function cancelScan(scanId: string): Promise<ScanSession> {
  const { data } = await client.post<ScanSession>(`/scans/${scanId}/cancel`);
  return data;
}

export async function getScanResources(
  scanId: string,
  params?: ScanResourcesParams,
): Promise<PaginatedResponse<DiscoveredResource>> {
  const { data } = await client.get<PaginatedResponse<DiscoveredResource>>(
    `/scans/${scanId}/resources`,
    { params },
  );
  return data;
}

export async function getScanLog(
  scanId: string,
  params?: ScanLogParams,
): Promise<PaginatedResponse<AuditLogEntry>> {
  const { data } = await client.get<PaginatedResponse<AuditLogEntry>>(
    `/scans/${scanId}/log`,
    { params },
  );
  return data;
}

export async function exportScanLog(scanId: string): Promise<Blob> {
  const { data } = await client.get(`/scans/${scanId}/log/export`, {
    responseType: "blob",
  });
  return data;
}
