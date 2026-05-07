/**
 * TypeScript types mirroring backend schemas (src/schemas.py + src/enums.py).
 *
 * Uses `as const` objects instead of enums — required by TS 6.0
 * with erasableSyntaxOnly enabled (enums emit runtime code).
 */

// --- Enums (const objects + union types) ---

export const UserRole = {
  ADMIN: "ADMIN",
  COMPANY: "COMPANY",
} as const;
export type UserRole = (typeof UserRole)[keyof typeof UserRole];

export const JobStatus = {
  PENDING_APPROVAL: "PENDING_APPROVAL",
  PUBLISHED: "PUBLISHED",
  CLOSED: "CLOSED",
} as const;
export type JobStatus = (typeof JobStatus)[keyof typeof JobStatus];

export const ApplicationStatus = {
  NEW: "NEW",
  APPROVED_BY_ADMIN: "APPROVED_BY_ADMIN",
  REJECTED: "REJECTED",
  HIRED: "HIRED",
} as const;
export type ApplicationStatus =
  (typeof ApplicationStatus)[keyof typeof ApplicationStatus];

// --- Auth ---

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CompanyProfileCreate {
  name: string;
  company_id: string;
  contact_first_name: string;
  contact_last_name: string;
  contact_mobile_phone: string;
  contact_landline_phone?: string | null;
}

// --- Users ---

export interface UserRead {
  id: number;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface CompanyProfileRead {
  id: number;
  /** Null when the profile was created directly by an admin without a user account. */
  user_id: number | null;
  name: string;
  logo_url: string | null;
  company_id: string | null;
  address: string | null;
  contact_first_name: string | null;
  contact_last_name: string | null;
  contact_mobile_phone: string | null;
  contact_landline_phone: string | null;
  agreement_signed_at: string | null;
  privacy_accepted_at: string | null;
  created_at: string;
}

/** Mirrors backend CompanyProfileAdminCreate schema. */
export interface CompanyProfileAdminCreate {
  name: string;
  company_id: string;
  address: string;
  contact_first_name: string;
  contact_last_name: string;
  contact_mobile_phone: string;
  contact_landline_phone?: string | null;
}

/** Mirrors backend CompanyProfileAdminUpdate (all fields optional). */
export interface CompanyProfileAdminUpdate {
  name?: string;
  company_id?: string;
  address?: string;
  contact_first_name?: string;
  contact_last_name?: string;
  contact_mobile_phone?: string;
  contact_landline_phone?: string | null;
}

export interface UserWithCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
}

// --- JWT Payload (decoded client-side) ---

export interface JwtPayload {
  sub: string; // user id
  email: string;
  role: UserRole;
  exp: number;
}

// --- Jobs (authenticated) ---

export interface JobRead {
  id: number;
  company_id: number;
  title: string;
  description: string;
  requirements: string;
  location: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
}

export interface JobCreate {
  title: string;
  description: string;
  requirements: string;
  location: string;
}

export interface JobUpdate {
  title?: string;
  description?: string;
  requirements?: string;
  location?: string;
  status?: JobStatus;
}

/** Mirrors backend JobAdminCreate schema. */
export interface JobAdminCreate {
  company_id: number;
  title: string;
  description: string;
  requirements: string;
  location: string;
  status?: JobStatus;
}

// --- Public Jobs ---

/** Mirrors backend JobPublicRead schema. Status is omitted (only PUBLISHED returned). */
export interface JobPublicRead {
  id: number;
  title: string;
  description: string;
  requirements: string;
  location: string;
  created_at: string;
}

// --- Candidates ---

/** Mirrors backend CandidateProfileRead schema. */
export interface CandidateProfileRead {
  id: number;
  full_name: string;
  email: string;
  phone: string | null;
  resume_path: string | null;
  linkedin_url: string | null;
  service_concept: string | null;
  salary_expectations: string | null;
  personality_weakness: string | null;
  personality_strength: string | null;
  created_at: string;
}

/** Mirrors backend CandidateProfileUpdate (partial — all fields optional). */
export interface CandidateProfileUpdate {
  full_name?: string;
  email?: string;
  phone?: string | null;
  resume_path?: string | null;
  linkedin_url?: string | null;
  service_concept?: string | null;
  salary_expectations?: string | null;
  personality_weakness?: string | null;
  personality_strength?: string | null;
}

/**
 * Form input shape for the application form.
 * Submitted as multipart/form-data to POST /api/candidates/apply.
 */
export interface CandidateApplicationForm {
  job_id: number;
  full_name: string;
  email: string;
  phone: string;
  linkedin_url: string;
  // Interview questions
  service_concept: string;
  salary_expectations: string;
  personality_weakness: string;
  personality_strength: string;
  // File — handled separately as File | null
}

// --- Admin: Companies ---

export interface PendingCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
}

export interface ApprovedCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
}

export interface ActiveCompanyRead {
  user: UserRead;
  company_profile: CompanyProfileRead;
}

// --- Applications ---

export interface ApplicationRead {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationWithDetails {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
  job: JobRead;
  candidate: CandidateProfileRead;
}

export interface ApplicationStatusUpdate {
  status: ApplicationStatus;
  admin_notes?: string | null;
}

// --- Health ---

export interface HealthResponse {
  status: string;
  environment: string;
}

// --- Invite Tokens ---

export const InviteTokenStatus = {
  PENDING: "pending",
  USED: "used",
  EXPIRED: "expired",
  REVOKED: "revoked",
} as const;
export type InviteTokenStatus =
  (typeof InviteTokenStatus)[keyof typeof InviteTokenStatus];

export interface InviteTokenCreate {
  email: string;
}

export interface InviteTokenRead {
  id: number;
  token: string;
  email: string;
  company_name: string | null;
  contact_first_name: string | null;
  contact_last_name: string | null;
  note: string | null;
  status: InviteTokenStatus;
  created_by_admin_id: number;
  created_at: string;
  expires_at: string;
  used_at: string | null;
}

export interface InviteMetadataPublic {
  email: string;
}
