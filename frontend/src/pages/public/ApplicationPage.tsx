import { type ChangeEvent, type FocusEvent, type FormEvent, type ReactNode, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJob, submitApplication } from "@/services/jobs";
import type { CandidateApplicationForm, JobPublicRead } from "@/types/api";
import { inputCls, textareaCls as textareaBase } from "@/styles/forms";
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
      <label htmlFor={id} className="block text-sm text-white/50">
        {label}
        {required && <span className="ms-1 text-copper/80">*</span>}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

const textareaCls = textareaBase + " min-h-[88px]";

export default function ApplicationPage() {
  const { t } = useTranslation();
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

  function validateField(name: string, value: string): string | null {
    const v = t;
    if (name === "full_name") {
      if (!value.trim()) return v("publicJobs.application.validation.fullNameRequired");
      if (value.trim().length < 2) return v("publicJobs.application.validation.fullNameMin");
      if (value.length > 100) return v("publicJobs.application.validation.fullNameMax");
    }
    if (name === "email") {
      if (!value.trim()) return v("publicJobs.application.validation.emailRequired");
      if (value.length > 255) return v("publicJobs.application.validation.emailMax");
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(value)) return v("publicJobs.application.validation.emailInvalid");
    }
    if (name === "phone" && value.trim()) {
      const phoneRegex = /^[+\d\s()-]*$/;
      if (!phoneRegex.test(value)) return v("publicJobs.application.validation.phoneInvalid");
      if (value.replace(/\D/g, "").length < 5) return v("publicJobs.application.validation.phoneMin");
    }
    if (name === "linkedin_url" && value.trim()) {
      let parsed: URL;
      try {
        parsed = new URL(value);
      } catch {
        return v("publicJobs.application.validation.urlInvalid");
      }
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return v("publicJobs.application.validation.urlProtocol");
      }
      if (!parsed.hostname.endsWith("linkedin.com")) {
        return v("publicJobs.application.validation.urlLinkedin");
      }
    }
    const textFields = ["service_concept", "salary_expectations", "military_service_details", "transportation", "personality_strength", "personality_weakness"];
    if (textFields.includes(name) && value.length > 2000) {
      return v("publicJobs.application.validation.textMax");
    }
    return null;
  }

  function validateForm(): boolean {
    const errors: Record<string, string> = {};
    Object.entries(form).forEach(([key, value]) => {
      const error = validateField(key, value);
      if (error) errors[key] = error;
    });
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
    if (fieldErrors[name]) {
      setFieldErrors(prev => ({ ...prev, [name]: "" }));
    }
  }

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
            setJobError(t("publicJobs.application.unavailable"));
          } else {
            setJobError(t("publicJobs.application.errorLoad"));
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
  }, [jobId, navigate, t]);

  function handleResumeChange(e: ChangeEvent<HTMLInputElement>) {
    setResumeError(null);
    const file = e.target.files?.[0] ?? null;
    if (!file) {
      setResumeFile(null);
      return;
    }

    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setResumeError(t("publicJobs.application.resumeErrors.invalidExtension"));
      e.target.value = "";
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setResumeError(t("publicJobs.application.resumeErrors.fileTooBig", { maxSize: MAX_FILE_SIZE_MB }));
      e.target.value = "";
      return;
    }

    setResumeFile(file);
  }

  function clearResume() {
    setResumeFile(null);
    setResumeError(null);
    const input = document.getElementById("resume") as HTMLInputElement | null;
    if (input) input.value = "";
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!Number.isFinite(jobId)) return;

    if (!validateForm()) {
      return;
    }

    if (resumeError) {
      return;
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitApplication(jobId, form, resumeFile);
      setSuccess(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 409) {
          setSubmitError(t("publicJobs.application.errors.alreadyApplied"));
        } else if (status === 404) {
          setSubmitError(t("publicJobs.application.errors.jobUnavailable"));
        } else {
          setSubmitError(t("publicJobs.application.errors.generic"));
        }
      } else {
        setSubmitError(t("publicJobs.application.errors.generic"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (jobLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-white/30">{t("publicJobs.application.loading")}</div>
      </div>
    );
  }

  if (jobError) {
    return (
      <div className="text-center">
        <div className="rounded-lg border border-danger/20 bg-danger/10 p-6 text-sm text-danger">{jobError}</div>
        <Link
          to="/jobs"
          className="mt-6 inline-block text-sm text-white/40 transition hover:text-copper"
        >
          {t("publicJobs.application.backToJob")}
        </Link>
      </div>
    );
  }

  if (success) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("publicJobs.application.submitted")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("publicJobs.application.submittedMessage")}{" "}
            <span className="text-white/70">{job?.title}</span>.{" "}
            {t("publicJobs.application.submittedDetail")}
          </p>
          <Link
            to="/jobs"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("publicJobs.application.browseMore")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link
        to={`/jobs/${jobId}`}
        className="mb-8 inline-block text-sm text-white/35 transition hover:text-copper"
      >
        {t("publicJobs.application.backToJob")}
      </Link>

      <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("publicJobs.application.applyFor")}
      </p>
      <h1 className="mt-2 text-xl font-semibold text-white/90 sm:text-2xl">{job?.title}</h1>
      <p className="mt-1.5 text-sm text-white/40">{job?.location}</p>

      <form onSubmit={handleSubmit} className="mt-10 space-y-10" noValidate>
        {submitError && (
          <div className="rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
            {submitError}
          </div>
        )}

        <section>
          <h2 className="mb-5 border-b border-white/8 pb-3 text-sm font-semibold text-white/70">
            {t("publicJobs.application.personalSection")}
          </h2>
          <div className="space-y-4">
            <Field label={t("publicJobs.application.fullName")} id="full_name" required>
              <input
                id="full_name"
                name="full_name"
                type="text"
                required
                value={form.full_name}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder={t("publicJobs.application.placeholders.fullName")}
                autoComplete="name"
              />
              {fieldErrors.full_name && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.full_name}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.email")} id="email" required>
              <input
                id="email"
                name="email"
                type="email"
                required
                value={form.email}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder={t("publicJobs.application.placeholders.email")}
                autoComplete="email"
              />
              {fieldErrors.email && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.email}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.phone")} id="phone">
              <input
                id="phone"
                name="phone"
                type="tel"
                value={form.phone}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder={t("publicJobs.application.placeholders.phone")}
                autoComplete="tel"
              />
              {fieldErrors.phone && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.phone}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.linkedin")} id="linkedin_url">
              <input
                id="linkedin_url"
                name="linkedin_url"
                type="url"
                value={form.linkedin_url}
                onChange={handleChange}
                onBlur={handleBlur}
                className={inputCls}
                placeholder={t("publicJobs.application.placeholders.linkedin")}
              />
              {fieldErrors.linkedin_url && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.linkedin_url}</p>
              )}
            </Field>
          </div>
        </section>

        <section>
          <h2 className="mb-5 border-b border-white/8 pb-3 text-sm font-semibold text-white/70">
            {t("publicJobs.application.resumeSection")}
          </h2>
          <Field label={t("publicJobs.application.resumeUpload")} id="resume">
            {resumeFile ? (
              <div className="flex items-center gap-3 rounded-sm border border-white/10 bg-well px-3 py-2">
                <span className="flex-1 truncate text-sm text-white/65">
                  {resumeFile.name}
                </span>
                <button
                  type="button"
                  onClick={clearResume}
                  className="shrink-0 text-xs text-danger/70 transition hover:text-danger"
                >
                  {t("publicJobs.application.removeFile")}
                </button>
              </div>
            ) : (
              <input
                id="resume"
                name="resume"
                type="file"
                accept=".pdf,.doc,.docx"
                onChange={handleResumeChange}
                className="block w-full text-sm text-white/40 file:me-3 file:rounded-sm file:border-0 file:bg-copper/10 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-copper hover:file:bg-copper/20"
              />
            )}
          </Field>
          {resumeError && <p className="mt-1.5 text-xs text-danger">{resumeError}</p>}
          <p className="mt-1.5 text-xs text-white/25">
            {t("publicJobs.application.fileHint", { maxSize: MAX_FILE_SIZE_MB })}
          </p>
        </section>

        <section>
          <h2 className="mb-2 border-b border-white/8 pb-3 text-sm font-semibold text-white/70">
            {t("publicJobs.application.interviewSection")}
          </h2>
          <p className="mb-5 text-xs text-white/30">
            {t("publicJobs.application.interviewSectionHint")}
          </p>
          <div className="space-y-4">
            <Field label={t("publicJobs.application.serviceConcept")} id="service_concept">
              <textarea
                id="service_concept"
                name="service_concept"
                value={form.service_concept}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.serviceConcept")}
              />
              {fieldErrors.service_concept && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.service_concept}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.salaryExpectations")} id="salary_expectations">
              <textarea
                id="salary_expectations"
                name="salary_expectations"
                value={form.salary_expectations}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.salaryExpectations")}
              />
              {fieldErrors.salary_expectations && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.salary_expectations}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.militaryService")} id="military_service_details">
              <textarea
                id="military_service_details"
                name="military_service_details"
                value={form.military_service_details}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.militaryService")}
              />
              {fieldErrors.military_service_details && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.military_service_details}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.transportation")} id="transportation">
              <textarea
                id="transportation"
                name="transportation"
                value={form.transportation}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.transportation")}
              />
              {fieldErrors.transportation && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.transportation}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.strength")} id="personality_strength">
              <textarea
                id="personality_strength"
                name="personality_strength"
                value={form.personality_strength}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.strength")}
              />
              {fieldErrors.personality_strength && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.personality_strength}</p>
              )}
            </Field>

            <Field label={t("publicJobs.application.weakness")} id="personality_weakness">
              <textarea
                id="personality_weakness"
                name="personality_weakness"
                value={form.personality_weakness}
                onChange={handleChange}
                onBlur={handleBlur}
                className={textareaCls}
                placeholder={t("publicJobs.application.placeholders.weakness")}
              />
              {fieldErrors.personality_weakness && (
                <p className="mt-1 text-xs text-danger">{fieldErrors.personality_weakness}</p>
              )}
            </Field>
          </div>
        </section>

        <div className="border-t border-white/8 pt-8">
          <button
            type="submit"
            disabled={submitting || !!resumeError}
            className="rounded-sm bg-copper px-8 py-3 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
          >
            {submitting ? t("publicJobs.application.submittingText") : t("publicJobs.application.submitText")}
          </button>
        </div>
      </form>
    </div>
  );
}
