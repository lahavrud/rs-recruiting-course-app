import api from "@/services/api";
import type {
  CandidateApplicationForm,
  CandidateProfileRead,
  JobPublicRead,
} from "@/types/api";

/** Fetch all published jobs for the public job board. */
export async function getPublicJobs(): Promise<JobPublicRead[]> {
  const response = await api.get<JobPublicRead[]>("/api/public/jobs");
  return response.data;
}

/** Fetch a single published job by ID. Throws AxiosError 404 if not found. */
export async function getPublicJob(id: number): Promise<JobPublicRead> {
  const response = await api.get<JobPublicRead>(`/api/public/jobs/${id}`);
  return response.data;
}

/**
 * Submit a candidate application as multipart/form-data.
 * resume is optional — pass null if not provided.
 */
export async function submitApplication(
  form: CandidateApplicationForm,
  resume: File | null,
): Promise<CandidateProfileRead> {
  const data = new FormData();

  // Append all text fields
  data.append("job_id", String(form.job_id));
  data.append("full_name", form.full_name);
  data.append("email", form.email);
  if (form.phone) data.append("phone", form.phone);
  if (form.linkedin_url) data.append("linkedin_url", form.linkedin_url);
  if (form.service_concept) data.append("service_concept", form.service_concept);
  if (form.salary_expectations)
    data.append("salary_expectations", form.salary_expectations);
  if (form.military_service_details)
    data.append("military_service_details", form.military_service_details);
  if (form.transportation) data.append("transportation", form.transportation);
  if (form.personality_weakness)
    data.append("personality_weakness", form.personality_weakness);
  if (form.personality_strength)
    data.append("personality_strength", form.personality_strength);

  // Append resume file if provided
  if (resume) {
    data.append("resume", resume, resume.name);
  }

  const response = await api.post<CandidateProfileRead>(
    "/api/candidates/apply",
    data,
  );
  return response.data;
}
