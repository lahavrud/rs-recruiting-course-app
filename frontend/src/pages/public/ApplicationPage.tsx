import { type ChangeEvent, type FocusEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getPublicJob, submitApplication } from "@/services/jobs";
import type { CandidateApplicationForm, JobPublicRead } from "@/types/api";
import axios from "axios";

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

const EMPTY_FORM: Omit<CandidateApplicationForm, "job_id"> = {
  full_name: "",
  email: "",
  phone: "",
  linkedin_url: "",
  service_concept: "",
  salary_expectations: "",
  military_service_details: "",
  transportation: "",
  personality_weakness: "",
  personality_strength: "",
};

interface FieldProps {
  label: string;
  id: string;
  required?: boolean;
  children: ReactNode;
}

function Field({ label, id, required, children }: FieldProps) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="ml-1 text-red-500">*</span>}
      </label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

const inputCls =
  "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none";
const textareaCls = inputCls + " resize-y min-h-[80px]";

export default function ApplicationPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id !== undefined ? Number.parseInt(id, 10) : NaN;

  const [job, setJob] = useState<JobPublicRead | null>(null);
  const [jobLoading, setJobLoading] = useState(true);
  const [jobError, setJobError] = useState<string | null>(null);

  const [form, setForm] =
    useState<Omit<CandidateApplicationForm, "job_id">>(EMPTY_FORM);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Validation rules
  function validateField(name: string, value: string): string | null {
    if (name === "full_name") {
      if (!value.trim()) return "Full name is required";
      if (value.trim().length < 2) return "Full name must be at least 2 characters";
      if (value.length > 100) return "Full name cannot exceed 100 characters";
    }
    if (name === "email") {
      if (!value.trim()) return "Email is required";
      if (value.length > 255) return "Email cannot exceed 255 characters";
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(value)) return "Please enter a valid email address";
    }
    if (name === "phone" && value.trim()) {
      const phoneRegex = /^[+\d\s()-]*$/;
      if (!phoneRegex.test(value)) return "Phone number can only contain digits, spaces, plus, hyphens, parentheses";
      if (value.replace(/\D/g, "").length < 5) return "Phone number must have at least 5 digits";
    }
    if (name === "linkedin_url" && value.trim()) {
      let parsed: URL;
      try {
        parsed = new URL(value);
      } catch {
        return "Please enter a valid URL";
      }
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return "LinkedIn URL must start with http:// or https://";
      }
      if (!parsed.hostname.endsWith("linkedin.com")) {
        return "LinkedIn URL must be a linkedin.com address";
      }
    }
    // Interview fields: optional, but limit length
    const textFields = ["service_concept", "salary_expectations", "military_service_details", "transportation", "personality_strength", "personality_weakness"];
    if (textFields.includes(name) && value.length > 2000) {
      return `This field cannot exceed 2000 characters`;
    }
    return null;
  }

  function validateForm(): boolean {
    const errors: Record<string, string> = {};
    // Validate each field in form
    Object.entries(form).forEach(([key, value]) => {
      const error = validateField(key, value);
      if (error) errors[key] = error;
    });
    // Validate resume file (if required? optional)
    // resume validation already handled separately
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleBlur(e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = e.target;
    const error = validateField(name, value);
    setFieldErrors(prev => ({ ...prev, [name]: error || "" }));
  }

  function handleChange(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    // Clear error when user starts typing
    if (fieldErrors[name]) {
      setFieldErrors(prev => ({ ...prev, [name]: "" }));
    }
  }

  // Load job details to show title in the header
  useEffect(() => {
    if (!Number.isFinite(jobId)) {
      navigate("/jobs", { replace: true });
      return;
    }

    let cancelled = false;

    async function fetchJob() {
      try {
        const data = await getPublicJob(jobId);
        if (!cancelled) setJob(data);
      } catch (err) {
        if (!cancelled) {
          if (axios.isAxiosError(err) && err.response?.status === 404) {
            setJobError("This job is no longer available.");
          } else {
            setJobError("Failed to load job details.");
          }
        }
      } finally {
        if (!cancelled) setJobLoading(false);
      }
    }

    fetchJob();
    return () => {
      cancelled = true;
    };
  }, [jobId, navigate]);



  function handleResumeChange(e: ChangeEvent<HTMLInputElement>) {
    setResumeError(null);
    const file = e.target.files?.[0] ?? null;
    if (!file) {
      setResumeFile(null);
      return;
    }

    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setResumeError("Only PDF, DOC, or DOCX files are allowed.");
      e.target.value = "";
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setResumeError(`File must be smaller than ${MAX_FILE_SIZE_MB} MB.`);
      e.target.value = "";
      return;
    }

    setResumeFile(file);
  }

  function clearResume() {
    setResumeFile(null);
    setResumeError(null);
    // Reset the file input
    const input = document.getElementById("resume") as HTMLInputElement | null;
    if (input) input.value = "";
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!Number.isFinite(jobId)) return;

    // Validate form fields
    if (!validateForm()) {
      return;
    }

    // Validate resume file (if any)
    if (resumeError) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitApplication({ ...form, job_id: jobId }, resumeFile);
      setSuccess(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        const detail = err.response?.data?.detail;
        if (status === 409) {
          setSubmitError("You have already applied to this job.");
        } else if (status === 404) {
          setSubmitError("This job is no longer available.");
        } else if (typeof detail === "string") {
          setSubmitError(detail);
        } else {
          setSubmitError("Something went wrong. Please try again.");
        }
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  // --- Loading / error states for job ---
  if (jobLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  if (jobError) {
    return (
      <div className="text-center">
        <div className="rounded-md bg-red-50 p-6 text-red-700">{jobError}</div>
        <Link
          to="/jobs"
          className="mt-6 inline-block text-sm text-blue-600 hover:underline"
        >
          ← Back to Jobs
        </Link>
      </div>
    );
  }

  // --- Success state ---
  if (success) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="rounded-lg border border-green-200 bg-green-50 p-10 text-center">
          <div className="text-4xl">✓</div>
          <h2 className="mt-4 text-xl font-semibold text-green-800">
            Application Submitted!
          </h2>
          <p className="mt-2 text-sm text-green-700">
            Thank you for applying to <span className="font-medium">{job?.title}</span>.
            We will be in touch if your profile is a good fit.
          </p>
          <Link
            to="/jobs"
            className="mt-6 block rounded-md bg-green-600 px-5 py-2 text-sm font-medium text-white hover:bg-green-700 sm:inline-block"
          >
            Browse More Jobs
          </Link>
        </div>
      </div>
    );
  }

  // --- Application form ---
  return (
    <div className="mx-auto max-w-2xl">
      {/* Back + title */}
      <Link
        to={`/jobs/${jobId}`}
        className="mb-6 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline"
      >
        ← Back to Job
      </Link>

      <h1 className="text-xl font-bold text-gray-900 sm:text-2xl">Apply — {job?.title}</h1>
      <p className="mt-1 text-sm text-gray-500">{job?.location}</p>

      <form onSubmit={handleSubmit} className="mt-8 space-y-10" noValidate>
        {/* Global error */}
        {submitError && (
          <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
            {submitError}
          </div>
        )}

        {/* ── Section 1: Personal Information ── */}
        <section>
          <h2 className="mb-4 border-b border-gray-200 pb-2 text-base font-semibold text-gray-900">
            Personal Information
          </h2>
          <div className="space-y-4">
            <Field label="Full Name" id="full_name" required>
              <input
                id="full_name"
                name="full_name"
                type="text"
                required
                value={form.full_name}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder="Jane Smith"
                autoComplete="name"
              />
              {fieldErrors.full_name && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.full_name}</p>
              )}
            </Field>

            <Field label="Email Address" id="email" required>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={form.email}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder="jane@example.com"
                autoComplete="email"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.email}</p>
              )}
            </Field>

            <Field label="Phone Number" id="phone">
              <input
                id="phone"
                name="phone"
                type="tel"
                value={form.phone}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder="+972 50 000 0000"
                autoComplete="tel"
              />
              {fieldErrors.phone && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.phone}</p>
              )}
            </Field>

            <Field label="LinkedIn URL" id="linkedin_url">
              <input
                id="linkedin_url"
                name="linkedin_url"
                type="url"
                value={form.linkedin_url}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder="https://linkedin.com/in/yourprofile"
              />
              {fieldErrors.linkedin_url && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.linkedin_url}</p>
              )}
            </Field>
          </div>
        </section>

        {/* ── Section 2: Resume ── */}
        <section>
          <h2 className="mb-4 border-b border-gray-200 pb-2 text-base font-semibold text-gray-900">
            Resume
          </h2>
          <Field label="Upload Resume" id="resume">
            {resumeFile ? (
              <div className="flex items-center gap-3 rounded-md border border-gray-300 bg-gray-50 px-3 py-2">
                <span className="flex-1 truncate text-sm text-gray-700">
                  {resumeFile.name}
                </span>
                <button
                  type="button"
                  onClick={clearResume}
                  className="shrink-0 text-xs text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              </div>
            ) : (
              <input
                id="resume"
                name="resume"
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleResumeChange}
                className="block w-full text-sm text-gray-500 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
              />
            )}
          </Field>
          {resumeError && <p className="mt-1 text-xs text-red-600">{resumeError}</p>}
          <p className="mt-1 text-xs text-gray-400">
            PDF, DOC, or DOCX — max {MAX_FILE_SIZE_MB} MB
          </p>
        </section>

        {/* ── Section 3: Interview Questions ── */}
        <section>
          <h2 className="mb-1 border-b border-gray-200 pb-2 text-base font-semibold text-gray-900">
            Interview Questions
          </h2>
          <p className="mb-4 text-xs text-gray-500">
            All fields in this section are optional.
          </p>
          <div className="space-y-4">
            <Field label="Service Concept" id="service_concept">
              <textarea
                id="service_concept"
                name="service_concept"
                value={form.service_concept}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="Describe your approach to customer service..."
              />
              {fieldErrors.service_concept && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.service_concept}</p>
              )}
            </Field>

            <Field label="Salary Expectations" id="salary_expectations">
              <textarea
                id="salary_expectations"
                name="salary_expectations"
                value={form.salary_expectations}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="What are your salary expectations?"
              />
              {fieldErrors.salary_expectations && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.salary_expectations}</p>
              )}
            </Field>

            <Field label="Military Service Details" id="military_service_details">
              <textarea
                id="military_service_details"
                name="military_service_details"
                value={form.military_service_details}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="Please describe your military service (if applicable)..."
              />
              {fieldErrors.military_service_details && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.military_service_details}</p>
              )}
            </Field>

            <Field label="Transportation" id="transportation">
              <textarea
                id="transportation"
                name="transportation"
                value={form.transportation}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="How do you plan to commute to work?"
              />
              {fieldErrors.transportation && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.transportation}</p>
              )}
            </Field>

            <Field label="Key Strength" id="personality_strength">
              <textarea
                id="personality_strength"
                name="personality_strength"
                value={form.personality_strength}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="What is your greatest professional strength?"
              />
              {fieldErrors.personality_strength && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.personality_strength}</p>
              )}
            </Field>

            <Field label="Area for Growth" id="personality_weakness">
              <textarea
                id="personality_weakness"
                name="personality_weakness"
                value={form.personality_weakness}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder="What is an area you are actively working to improve?"
              />
              {fieldErrors.personality_weakness && (
                <p className="mt-1 text-xs text-red-600">{fieldErrors.personality_weakness}</p>
              )}
            </Field>
          </div>
        </section>

        {/* Submit */}
        <div className="border-t border-gray-200 pt-6">
          <button
            type="submit"
            disabled={submitting || !!resumeError}
            className="w-full rounded-md bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {submitting ? "Submitting..." : "Submit Application"}
          </button>
        </div>
      </form>
    </div>
  );
}
