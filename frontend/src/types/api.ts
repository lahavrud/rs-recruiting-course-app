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
  company_id: string;
  address: string;
  contact_email: string;
  contact_first_name: string;
  contact_last_name: string;
  contact_mobile_phone: string;
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
  contact_email: string;
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
  contact_email?: string;
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

export interface JobRequirementItem {
  text: string;
}

export const JOB_SHORT_DESC_MAX = 140;
export const JOB_TAG_MAX_LEN = 30;
export const JOB_TAG_MAX_COUNT = 6;
export const JOB_REQ_TEXT_MAX = 200;
export const JOB_REQ_MIN_COUNT = 3;
export const JOB_REQ_MAX_COUNT = 15;

export interface JobRead {
  id: number;
  company_id: number;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  status: JobStatus;
  created_at: string;
  updated_at: string;
}

export interface JobCreate {
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  location: string;
  salary_min: number;
  salary_max: number;
}

export interface JobUpdate {
  title?: string;
  short_description?: string;
  description?: string;
  requirements?: JobRequirementItem[];
  tags?: string[];
  location?: string;
  /** NOT NULL in DB — backend rejects explicit null. Omit to leave unchanged. */
  salary_min?: number;
  /** NOT NULL in DB — backend rejects explicit null. Omit to leave unchanged. */
  salary_max?: number;
  status?: JobStatus;
}

/** Mirrors backend JobAdminCreate schema. */
export interface JobAdminCreate {
  company_id: number;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured?: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  status?: JobStatus;
}

/** Mirrors backend JobAdminUpdate — extends JobUpdate with is_featured. */
export interface JobAdminUpdate extends JobUpdate {
  is_featured?: boolean;
}

// --- Public Jobs ---

/** Mirrors backend JobPublicRead schema. Status is omitted (only PUBLISHED returned). */
export interface JobPublicRead {
  id: number;
  title: string;
  short_description: string;
  description: string;
  requirements: JobRequirementItem[];
  tags: string[];
  is_featured: boolean;
  location: string;
  salary_min: number;
  salary_max: number;
  created_at: string;
}

// --- Candidates ---

/** Mirrors backend CandidateProfileRead schema. */
export interface CandidateProfileRead {
  id: number;
  full_name: string;
  email: string;
  phone: string;
  resume_path: string | null;
  linkedin_url: string | null;
  created_at: string;
}

/** Mirrors backend CandidateProfileUpdate (partial — all fields optional). */
export interface CandidateProfileUpdate {
  full_name?: string;
  email?: string;
  /** NOT NULL in DB — backend rejects explicit null. Omit to leave unchanged. */
  phone?: string;
  resume_path?: string | null;
  linkedin_url?: string | null;
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
  growth_area: string;
  strength: string;
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
  /** Null for profiles created directly by admins (no user account yet). */
  user: UserRead | null;
  company_profile: CompanyProfileRead;
}

// --- Applications ---

export interface ApplicationRead {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  service_concept: string | null;
  salary_expectations: string | null;
  strength: string | null;
  growth_area: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationWithDetails {
  id: number;
  job_id: number;
  candidate_id: number;
  status: ApplicationStatus;
  admin_notes: string | null;
  service_concept: string | null;
  salary_expectations: string | null;
  strength: string | null;
  growth_area: string | null;
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
  PENDING: "PENDING",
  USED: "USED",
  EXPIRED: "EXPIRED",
  REVOKED: "REVOKED",
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
