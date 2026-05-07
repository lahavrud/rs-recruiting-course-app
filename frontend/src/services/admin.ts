/**
 * Admin API service.
 * All endpoints require ADMIN role JWT.
 */
import api from "@/services/api";
import type { CursorPage } from "@/hooks/useInfiniteList";
import type {
  ActiveCompanyRead,
  ApprovedCompanyRead,
  ApplicationRead,
  ApplicationStatusUpdate,
  ApplicationWithDetails,
  ApplicationStatus,
  CandidateProfileRead,
  CandidateProfileUpdate,
  CompanyProfileAdminCreate,
  CompanyProfileAdminUpdate,
  CompanyProfileRead,
  InviteTokenCreate,
  InviteTokenRead,
  JobAdminCreate,
  JobRead,
  JobStatus,
  JobUpdate,
  PendingCompanyRead,
} from "@/types/api";

// ── Companies ────────────────────────────────────────────────────────────────

export async function createInvite(data: InviteTokenCreate): Promise<InviteTokenRead> {
  const res = await api.post<InviteTokenRead>("/api/admin/companies/invite", data);
  return res.data;
}

export interface InvitesListParams {
  cursor?: string | null;
  limit?: number;
}

export async function getInvites(
  params?: InvitesListParams,
): Promise<CursorPage<InviteTokenRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<InviteTokenRead>>(
    "/api/admin/companies/invites",
    { params: query },
  );
  return res.data;
}

export async function revokeInvite(tokenId: number): Promise<void> {
  await api.delete(`/api/admin/companies/invites/${tokenId}`);
}

export async function resendInvite(tokenId: number): Promise<void> {
  await api.post(`/api/admin/companies/invites/${tokenId}/resend`);
}

export interface PendingCompaniesParams {
  cursor?: string | null;
  limit?: number;
}

export async function getPendingCompanies(
  params?: PendingCompaniesParams,
): Promise<CursorPage<PendingCompanyRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<PendingCompanyRead>>(
    "/api/admin/companies/pending",
    { params: query },
  );
  return res.data;
}

export async function approveCompany(userId: number): Promise<ApprovedCompanyRead> {
  const res = await api.post<ApprovedCompanyRead>(
    `/api/admin/companies/${userId}/approve`,
  );
  return res.data;
}

export async function rejectCompany(userId: number): Promise<void> {
  await api.post(`/api/admin/companies/${userId}/reject`);
}

export interface ActiveCompaniesParams {
  cursor?: string | null;
  limit?: number;
}

export async function getActiveCompanies(
  params?: ActiveCompaniesParams,
): Promise<CursorPage<ActiveCompanyRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<ActiveCompanyRead>>("/api/admin/companies", {
    params: query,
  });
  return res.data;
}

export async function deleteCompany(userId: number): Promise<void> {
  await api.delete(`/api/admin/companies/${userId}`);
}

export async function adminCreateCompany(
  body: CompanyProfileAdminCreate,
): Promise<CompanyProfileRead> {
  const res = await api.post<CompanyProfileRead>("/api/admin/companies", body);
  return res.data;
}

export async function getCompanyProfile(
  profileId: number,
): Promise<CompanyProfileRead> {
  const res = await api.get<CompanyProfileRead>(
    `/api/admin/companies/profile/${profileId}`,
  );
  return res.data;
}

export async function updateCompanyProfile(
  profileId: number,
  body: CompanyProfileAdminUpdate,
): Promise<CompanyProfileRead> {
  const res = await api.put<CompanyProfileRead>(
    `/api/admin/companies/profile/${profileId}`,
    body,
  );
  return res.data;
}

// ── Jobs ─────────────────────────────────────────────────────────────────────

export async function getPendingJobs(): Promise<JobRead[]> {
  const res = await api.get<JobRead[]>("/api/admin/jobs/pending");
  return res.data;
}

export async function approveJob(jobId: number): Promise<JobRead> {
  const res = await api.post<JobRead>(`/api/admin/jobs/${jobId}/approve`);
  return res.data;
}

export async function rejectJob(jobId: number): Promise<void> {
  await api.post(`/api/admin/jobs/${jobId}/reject`);
}

export async function contactJob(jobId: number, note: string): Promise<void> {
  await api.post(`/api/admin/jobs/${jobId}/contact`, { admin_note: note });
}

export interface JobListParams {
  status?: JobStatus;
  cursor?: string | null;
  limit?: number;
}

export async function getJobs(params?: JobListParams): Promise<CursorPage<JobRead>> {
  const query: Record<string, string | number> = {};
  if (params?.status) query.status = params.status;
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<JobRead>>("/api/admin/jobs", {
    params: query,
  });
  return res.data;
}

export async function getJob(id: number): Promise<JobRead> {
  const res = await api.get<JobRead>(`/api/admin/jobs/${id}`);
  return res.data;
}

export async function createJob(body: JobAdminCreate): Promise<JobRead> {
  const res = await api.post<JobRead>("/api/admin/jobs", body);
  return res.data;
}

export async function updateJob(id: number, body: JobUpdate): Promise<JobRead> {
  const res = await api.put<JobRead>(`/api/admin/jobs/${id}`, body);
  return res.data;
}

export async function deleteJob(id: number): Promise<void> {
  await api.delete(`/api/admin/jobs/${id}`);
}

// ── Applications ─────────────────────────────────────────────────────────────

export interface ApplicationListParams {
  status?: ApplicationStatus;
  job_id?: number;
  candidate_id?: number;
  cursor?: string | null;
  limit?: number;
}

export async function getApplications(
  params?: ApplicationListParams,
): Promise<CursorPage<ApplicationWithDetails>> {
  const query: Record<string, string | number> = {};
  if (params?.status) query.status = params.status;
  if (params?.job_id != null) query.job_id = params.job_id;
  if (params?.candidate_id != null) query.candidate_id = params.candidate_id;
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<ApplicationWithDetails>>(
    "/api/admin/applications",
    { params: query },
  );
  return res.data;
}

export async function updateApplicationNotes(
  appId: number,
  adminNotes: string | null,
): Promise<ApplicationRead> {
  const res = await api.put<ApplicationRead>(`/api/admin/applications/${appId}/notes`, {
    admin_notes: adminNotes,
  });
  return res.data;
}

export async function updateApplicationStatus(
  appId: number,
  body: ApplicationStatusUpdate,
): Promise<ApplicationRead> {
  const res = await api.put<ApplicationRead>(
    `/api/admin/applications/${appId}/status`,
    body,
  );
  return res.data;
}

export async function deleteApplication(appId: number): Promise<void> {
  await api.delete(`/api/admin/applications/${appId}`);
}

// ── Candidates ────────────────────────────────────────────────────────────────

export interface CandidateListParams {
  cursor?: string | null;
  limit?: number;
}

export async function getCandidates(
  params?: CandidateListParams,
): Promise<CursorPage<CandidateProfileRead>> {
  const query: Record<string, string | number> = {};
  if (params?.cursor) query.cursor = params.cursor;
  if (params?.limit != null) query.limit = params.limit;
  const res = await api.get<CursorPage<CandidateProfileRead>>("/api/admin/candidates", {
    params: query,
  });
  return res.data;
}

export async function getCandidate(id: number): Promise<CandidateProfileRead> {
  const res = await api.get<CandidateProfileRead>(`/api/admin/candidates/${id}`);
  return res.data;
}

export async function updateCandidate(
  id: number,
  body: CandidateProfileUpdate,
): Promise<CandidateProfileRead> {
  const res = await api.put<CandidateProfileRead>(`/api/admin/candidates/${id}`, body);
  return res.data;
}

export async function deleteCandidate(id: number): Promise<void> {
  await api.delete(`/api/admin/candidates/${id}`);
}

export async function fetchResumeBlob(fileKey: string): Promise<Blob> {
  const res = await api.get<Blob>(`/api/resumes/${fileKey}`, {
    responseType: "blob",
  });
  return res.data;
}
