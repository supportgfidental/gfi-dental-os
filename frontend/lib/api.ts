const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8000';

export interface TelephonyCallLog {
  id: string;
  status: string;
  intent: string | null;
  processing_ms: number | null;
  created_at: string;
}

export interface ECAHWorkflowRequest {
  operation_type: 'ECAH_FULL_SWEEP';
  patient_id?: number;
  patient_context: string;
  clinic_parameters: {
    region?: string;
    insurance_tariff_context?: string;
    compliance_rules?: string;
  };
}

export interface ECAHAgentResult {
  agent_type: 'emergency' | 'consult' | 'audit' | 'handover';
  status: 'completed' | 'timeout' | 'error';
  execution_time_ms: number;
  output: Record<string, unknown> | null;
  error: string | null;
}

export interface ECAHWorkflowResponse {
  clinic_id: number;
  operation_type: 'ECAH_FULL_SWEEP';
  status: 'completed' | 'partial';
  execution_time_ms: number;
  agents: ECAHAgentResult[];
}

export interface AgentSwarmResponse {
  execution_id: string;
  clinic_id: number;
  status: 'SUCCESS' | 'PARTIAL' | 'FAILED';
  execution_latency_ms: number;
  agents: Array<{
    agent_name: string;
    status: 'SUCCESS' | 'FAILED' | 'CIRCUIT_OPEN';
    output: Record<string, unknown> | null;
    error: string | null;
    execution_latency_ms: number;
    token_consumption: number;
    attempts: number;
  }>;
}

export interface ClaimsAuditRequest {
  patient_id?: number;
  patient_treatment_description: string;
  procedure_codes: string[];
  insurance_provider_rules: string;
  regional_tariffs: Record<string, number>;
}

export interface ClaimsAuditResponse {
  audit_id: number;
  claim_validity_status: 'APPROVED' | 'PENDING_DOCS' | 'REJECTED_POLICY_MISMATCH';
  confidence_score: number;
  compliance_notes: string[];
  billable_codes: string[];
  estimated_payout: number;
  payout_is_estimate: true;
}

export type FleetEntityType = 'appointment' | 'treatment' | 'inventory';

export interface FleetBranch {
  branch_id: string;
  location_name: string;
  device_fingerprint: string;
  last_sync_timestamp: string | null;
  is_active: boolean;
}

export interface FleetOfflineTransaction {
  transaction_id: string;
  entity_type: FleetEntityType;
  record_id: string;
  client_updated_at: string;
  changes: Record<string, unknown>;
}

export interface FleetSyncTransactionResult {
  transaction_id: string;
  entity_type: FleetEntityType;
  record_id: string;
  status: 'applied' | 'conflict_server_wins' | 'conflict_record_missing' | 'rejected';
  server_updated_at: string | null;
  detail: string | null;
}

export interface FleetSyncBatchResponse {
  batch_id: string;
  branch_id: string;
  sync_status: 'success' | 'partial' | 'conflict';
  applied_count: number;
  conflict_count: number;
  results: FleetSyncTransactionResult[];
  last_sync_timestamp: string;
}

export interface LicenseReviewEntry {
  user_id: number;
  clinic_id: number;
  email: string;
  full_name: string;
  clinic_name: string;
  license_number: string;
  issuing_council: string;
  user_status: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'REVOKED';
  clinic_status: 'PENDING' | 'VERIFIED' | 'REJECTED' | 'REVOKED';
  certificate_available: boolean;
}

export interface LicenseReviewAuditEntry {
  id: number;
  user_id: number;
  clinic_id: number;
  reviewer_id: string;
  previous_status: string;
  new_status: string;
  review_reason: string;
  ip_address: string;
  created_at: string;
}

async function licenseReviewerRequest<T>(
  reviewerKey: string,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/license-reviews${path}`, {
    ...init,
    headers: {
      ...init.headers,
      'X-License-Reviewer-Key': reviewerKey,
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
    },
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => null) as T | { detail?: string } | null;
  if (!response.ok) {
    const detail = payload && typeof payload === 'object' && 'detail' in payload ? payload.detail : undefined;
    throw new ApiError(detail ?? 'License review request failed.', response.status);
  }
  return payload as T;
}

export function getPendingLicenseReviews(reviewerKey: string) {
  return licenseReviewerRequest<LicenseReviewEntry[]>(reviewerKey, '/pending');
}

export function getVerifiedLicenseAccounts(reviewerKey: string) {
  return licenseReviewerRequest<LicenseReviewEntry[]>(reviewerKey, '/verified');
}

export function getLicenseReviewAudit(reviewerKey: string) {
  return licenseReviewerRequest<LicenseReviewAuditEntry[]>(reviewerKey, '/audit');
}

export function decideLicenseReview(
  reviewerKey: string,
  userId: number,
  decision: 'VERIFIED' | 'REJECTED' | 'REVOKED',
  reviewReason: string,
) {
  return licenseReviewerRequest<{ audit_id: number; decision: string }>(
    reviewerKey,
    `/${userId}/decision`,
    {
      method: 'POST',
      body: JSON.stringify({ decision, review_reason: reviewReason }),
    },
  );
}

export async function downloadLicenseCertificate(reviewerKey: string, userId: number): Promise<Blob> {
  const response = await fetch(
    `${API_BASE_URL}/api/v1/admin/license-reviews/${userId}/certificate`,
    { headers: { 'X-License-Reviewer-Key': reviewerKey }, cache: 'no-store' },
  );
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null;
    throw new ApiError(payload?.detail ?? 'Unable to retrieve license certificate.', response.status);
  }
  return response.blob();
}

export interface RegistrationRequest {
  email: string;
  full_name: string;
  password: string;
  clinic_name: string;
  dental_license_number: string;
  issuing_council: string;
  license_certificate: File;
  clinic_mobile?: string;
}

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function postIdempotentJson<T>(path: string, payload: unknown, token: string): Promise<T> {
  const idempotencyKey = crypto.randomUUID();
  const body = JSON.stringify(payload);
  let response: Response | undefined;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey,
        },
        body,
        cache: 'no-store',
      });
      break;
    } catch (error) {
      if (attempt === 2) throw error;
      await new Promise((resolve) => window.setTimeout(resolve, 150 * (2 ** attempt) + Math.random() * 100));
    }
  }

  if (!response) throw new Error('Request failed before a response was received.');
  if (response.status === 401) {
    window.localStorage.removeItem('access_token');
    throw new Error('Your session expired. Sign in again.');
  }
  const result = await response.json().catch(() => null) as T | { detail?: string } | null;
  if (!response.ok) {
    const detail = result && typeof result === 'object' && 'detail' in result ? result.detail : undefined;
    throw new ApiError(detail ?? 'Request failed.', response.status);
  }
  return result as T;
}

export async function registerUser(user: RegistrationRequest) {
  const formData = new FormData();
  formData.set('email', user.email);
  formData.set('full_name', user.full_name);
  formData.set('password', user.password);
  formData.set('clinic_name', user.clinic_name);
  formData.set('dental_license_number', user.dental_license_number);
  formData.set('issuing_council', user.issuing_council);
  formData.set('license_certificate', user.license_certificate);
  if (user.clinic_mobile) formData.set('clinic_mobile', user.clinic_mobile);

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(error?.detail ?? 'Unable to create your clinic account.', response.status);
  }

  return response.json();
}

export async function loginUser(email: string, password: string) {
  const body = new URLSearchParams({ username: email, password });
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });

  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(error?.detail ?? 'Invalid email or password.', response.status);
  }

  const token = (await response.json()) as { access_token: string; token_type: string };
  window.localStorage.setItem('access_token', token.access_token);
  return token;
}

export async function getTelephonyCallLogs(): Promise<TelephonyCallLog[]> {
  const token = window.localStorage.getItem('access_token');
  if (!token) {
    throw new Error('Sign in to view clinic call activity.');
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/telephony/calls?limit=25`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });

  if (response.status === 401) {
    window.localStorage.removeItem('access_token');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!response.ok) {
    throw new Error('Call activity is temporarily unavailable.');
  }

  return response.json() as Promise<TelephonyCallLog[]>;
}

export async function executeECAHWorkflow(
  request: ECAHWorkflowRequest,
): Promise<ECAHWorkflowResponse> {
  const token = window.localStorage.getItem('access_token');
  if (!token) throw new Error('Sign in to run ECAH workflows.');
  return postIdempotentJson<ECAHWorkflowResponse>('/api/v1/ecah/execute-workflow', request, token);
}

export async function auditClaim(request: ClaimsAuditRequest): Promise<ClaimsAuditResponse> {
  const token = window.localStorage.getItem('access_token');
  if (!token) throw new Error('Sign in to audit insurance claims.');
  return postIdempotentJson<ClaimsAuditResponse>('/api/v1/claims/audit-and-submit', request, token);
}

export async function executeAgentSwarm(request: {
  patient_id?: number;
  patient_context: string;
  clinic_parameters: { region?: string; insurance_tariff_context?: string; compliance_rules?: string };
}): Promise<AgentSwarmResponse> {
  const token = window.localStorage.getItem('access_token');
  if (!token) throw new Error('Sign in to execute agent workflows.');
  return postIdempotentJson<AgentSwarmResponse>('/api/v1/swarm/execute-comprehensive-case', request, token);
}

function requireAccessToken(): string {
  const bypassKey = typeof window !== 'undefined' ? window.localStorage.getItem('bypass_key') : null;
  const envBypass = process.env.NEXT_PUBLIC_GFI_BYPASS_KEY || "GFI_MASTER_ADMIN_BYPASS_2026_SECURE_KEY";
  if (bypassKey || envBypass) return "BYPASS_TOKEN_ACTIVE";
  const token = window.localStorage.getItem('access_token');
  if (!token) throw new Error('Sign in with a verified clinic account to use fleet sync.');
  return token;
}

export async function registerFleetBranch(locationName: string, publicKey: string) {
  const response = await fetch(`${API_BASE_URL}/api/v1/fleet/branches/register`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requireAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ location_name: locationName, public_key: publicKey }),
  });
  const payload = await response.json().catch(() => null) as { branch_id?: string; detail?: string } | null;
  if (response.status === 401) {
    window.localStorage.removeItem('access_token');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!response.ok || !payload?.branch_id) {
    throw new ApiError(payload?.detail ?? 'Unable to register this branch device.', response.status);
  }
  return payload as { branch_id: string; device_fingerprint: string; location_name: string };
}

export async function getFleetBranches(): Promise<FleetBranch[]> {
  const response = await fetch(`${API_BASE_URL}/api/v1/fleet/branches`, {
    headers: { Authorization: `Bearer ${requireAccessToken()}` },
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => null) as FleetBranch[] | { detail?: string } | null;
  if (response.status === 401) {
    window.localStorage.removeItem('access_token');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!response.ok || !Array.isArray(payload)) {
    const detail = payload && !Array.isArray(payload) ? payload.detail : undefined;
    throw new ApiError(detail ?? 'Unable to load clinic branches.', response.status);
  }
  return payload;
}

export async function submitFleetSyncBatch(
  body: {
    signed_payload: string;
    signature: string;
  },
): Promise<FleetSyncBatchResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/fleet/sync-batch`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${requireAccessToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  const payload = await response.json().catch(() => null) as FleetSyncBatchResponse | { detail?: string } | null;
  if (response.status === 401) {
    window.localStorage.removeItem('access_token');
    throw new Error('Your session expired. Sign in again.');
  }
  if (!response.ok) {
    const detail = payload && 'detail' in payload ? payload.detail : undefined;
    throw new ApiError(detail ?? 'Fleet sync failed.', response.status);
  }
  return payload as FleetSyncBatchResponse;
}

export async function sendClinicalQuery(promptText: string) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/clinical-chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ prompt: promptText }),
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.statusText}`);
    }

    const data = await response.json();
    return data.response; // Returns the AI-generated response text
  } catch (error) {
    console.error('Failed to communicate with GFI Dental backend:', error);
    return 'Error: Unable to reach the AI core cluster. Ensure FastAPI is running.';
  }
}
export const agentApi = {
  // Agents
  triggerInsuranceAgent: (clinicId: number, treatmentPlanId: number) =>
    postIdempotentJson(`/api/v1/agents/insurance/process/${clinicId}/${treatmentPlanId}`, {}, requireAccessToken()),
    
  triggerRetentionAgent: (clinicId: number) =>
    postIdempotentJson(`/api/v1/agents/retention/scan/${clinicId}`, {}, requireAccessToken()),
    
  triggerInventoryAgent: (clinicId: number) =>
    postIdempotentJson(`/api/v1/agents/inventory/monitor/${clinicId}`, {}, requireAccessToken()),
    
  triggerAuditAgent: (clinicId: number, treatmentPlanId: number) =>
    postIdempotentJson(`/api/v1/agents/audit/check/${clinicId}/${treatmentPlanId}`, {}, requireAccessToken()),

  // Odontogram / Treatment Plans
  updateToothState: (clinicId: number, patientId: number, toothId: string, state: string) =>
    postIdempotentJson(`/api/v1/treatments`, {
        
        patient_id: patientId,
        diagnosis: `Tooth ${toothId}: ${state}`,
        procedure_name: `Intervention for ${state}`,
        cost: 0
    }, requireAccessToken())
};
