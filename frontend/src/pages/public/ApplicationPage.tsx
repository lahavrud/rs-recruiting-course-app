import {
  type ChangeEvent,
  type DragEvent,
  type FocusEvent,
  type FormEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJob, submitApplication } from "@/services/jobs";
import { trackEvent } from "@/utils/analytics";
import { getMe as getCandidateMe } from "@/services/candidate";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import type { CandidateApplicationForm, JobPublicRead } from "@/types/api";
import { UserRole } from "@/types/api";
import { useAuth } from "@/hooks/useAuth";
import { inputCls, textareaCls as textareaBase } from "@/styles/forms";
import axios from "axios";

const ALLOWED_EXTENSIONS = [".pdf", ".doc", ".docx"];
const MAX_FILE_SIZE_MB = 10;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;
const TEXT_FIELD_MAX = 2000;

const TOTAL_STEPS = 3;
type Step = 1 | 2 | 3;

const EMPTY_FORM: Omit<CandidateApplicationForm, "job_id"> = {
  full_name: "",
  email: "",
  phone: "",
  linkedin_url: "",
  service_concept: "",
  salary_expectations: "",
  growth_area: "",
  strength: "",
};

const STEP_1_FIELDS = ["full_name", "email", "phone", "linkedin_url"] as const;
const STEP_3_FIELDS = [
  "service_concept",
  "salary_expectations",
  "strength",
  "growth_area",
] as const;

const textareaCls = textareaBase + " min-h-[96px]";

// ── Reusable field wrapper ────────────────────────────────────────────────

interface FieldProps {
  label: string;
  id: string;
  required?: boolean;
  optional?: boolean;
  className?: string;
  children: ReactNode;
}

function Field({ label, id, required, optional, className, children }: FieldProps) {
  const { t } = useTranslation();
  return (
    <div data-field={id} className={className}>
      <label
        htmlFor={id}
        className="flex items-center gap-1.5 text-xs text-white/55 sm:text-sm"
      >
        <span>{label}</span>
        {required && <span className="text-copper/80">*</span>}
        {optional && (
          <span className="text-[10px] text-white/30">
            ({t("common.optional")})
          </span>
        )}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────

export default function ApplicationPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const jobId = id !== undefined ? Number.parseInt(id, 10) : NaN;

  const { user } = useAuth();
  // Logged-in candidate: their session email is the canonical email — the
  // backend ignores the form field, and we hide consent + the claim toggle
  // since consent was captured at activation (Sprint 11 / #605, #606).
  const isLoggedInCandidate = user?.role === UserRole.CANDIDATE;

  const [job, setJob] = useState<JobPublicRead | null>(null);
  const [jobLoading, setJobLoading] = useState(true);
  const [jobError, setJobError] = useState<string | null>(null);

  const [form, setForm] = useState<Omit<CandidateApplicationForm, "job_id">>(() =>
    isLoggedInCandidate ? { ...EMPTY_FORM, email: user!.email } : EMPTY_FORM,
  );
  // Anonymous-only claim toggle: when checked we send password +
  // password_confirm with the apply submission.
  const [claimAccount, setClaimAccount] = useState(false);
  const [claimPassword, setClaimPassword] = useState("");
  const [claimPasswordConfirm, setClaimPasswordConfirm] = useState("");
  const [claimError, setClaimError] = useState<string | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);
  // Sprint 11 PR B: logged-in candidates can apply with their existing
  // profile-resume snapshot (no re-upload). When this is set and the user
  // hasn't picked a new file, we submit without a `resume` part and the
  // backend reuses `CandidateProfile.resume_path`.
  const [savedResumeFilename, setSavedResumeFilename] = useState<string | null>(
    null,
  );
  const [profilePrefilled, setProfilePrefilled] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);

  // Wizard state — track current step + the highest step reached so the
  // stepper only lets candidates jump back to steps they've completed.
  const [step, setStep] = useState<Step>(1);
  const [maxStep, setMaxStep] = useState<Step>(1);

  // ── Validation ──────────────────────────────────────────────────────────

  function validateField(name: string, value: string): string | null {
    if (name === "full_name") {
      if (!value.trim())
        return t("publicJobs.application.validation.fullNameRequired");
      if (value.trim().length < 2)
        return t("publicJobs.application.validation.fullNameMin");
      if (value.length > 100)
        return t("publicJobs.application.validation.fullNameMax");
    }
    if (name === "email") {
      if (!value.trim())
        return t("publicJobs.application.validation.emailRequired");
      if (value.length > 255)
        return t("publicJobs.application.validation.emailMax");
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(value))
        return t("publicJobs.application.validation.emailInvalid");
    }
    if (name === "phone") {
      if (!value.trim())
        return t("publicJobs.application.validation.phoneRequired");
      const phoneRegex = /^[+\d\s()-]*$/;
      if (!phoneRegex.test(value))
        return t("publicJobs.application.validation.phoneInvalid");
      // Israeli mobile: exactly 10 digits starting with 05 after stripping
      // spaces/dashes/parens. Matches backend `_validate_phone_value`.
      const digits = value.replace(/\D/g, "");
      if (!/^05\d{8}$/.test(digits))
        return t("publicJobs.application.validation.phoneFormat");
    }
    if (name === "linkedin_url" && value.trim()) {
      let parsed: URL;
      try {
        parsed = new URL(value);
      } catch {
        return t("publicJobs.application.validation.urlInvalid");
      }
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        return t("publicJobs.application.validation.urlProtocol");
      }
      if (!parsed.hostname.endsWith("linkedin.com")) {
        return t("publicJobs.application.validation.urlLinkedin");
      }
    }
    if (
      (STEP_3_FIELDS as readonly string[]).includes(name) &&
      value.length > TEXT_FIELD_MAX
    ) {
      return t("publicJobs.application.validation.textMax");
    }
    return null;
  }

  function validateStep(target: Step): boolean {
    const errors: Record<string, string> = { ...fieldErrors };
    let ok = true;

    if (target === 1) {
      for (const name of STEP_1_FIELDS) {
        const err = validateField(name, form[name] ?? "");
        if (err) {
          errors[name] = err;
          ok = false;
        } else {
          delete errors[name];
        }
      }
      setFieldErrors(errors);
      return ok;
    }

    if (target === 2) {
      // A new upload OR the saved-profile-resume affordance both satisfy
      // the "every live application has a resume" backend rule.
      if (!resumeFile && !savedResumeFilename) {
        setResumeError(t("publicJobs.application.resumeErrors.required"));
        return false;
      }
      if (resumeError) return false;
      return true;
    }

    // Step 3 fields are optional — only validate maxlen + consent.
    for (const name of STEP_3_FIELDS) {
      const err = validateField(name, form[name] ?? "");
      if (err) {
        errors[name] = err;
        ok = false;
      } else {
        delete errors[name];
      }
    }
    // Consent only validated on the anonymous path — logged-in candidates
    // already accepted at activation time (Sprint 11 / #605).
    if (!isLoggedInCandidate) {
      if (!privacyAccepted) {
        errors.privacy = t("publicJobs.application.validation.privacyRequired");
        ok = false;
      } else {
        delete errors.privacy;
      }
      if (!termsAccepted) {
        errors.terms = t("publicJobs.application.validation.termsRequired");
        ok = false;
      } else {
        delete errors.terms;
      }
    } else {
      delete errors.privacy;
      delete errors.terms;
    }
    setFieldErrors(errors);
    return ok;
  }

  function handleBlur(e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = e.target;
    const error = validateField(name, value);
    setFieldErrors((prev) => ({ ...prev, [name]: error || "" }));
  }

  function handleChange(e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
    if (fieldErrors[name]) {
      setFieldErrors((prev) => ({ ...prev, [name]: "" }));
    }
  }

  // Lock body scroll when any legal modal is open
  useEffect(() => {
    document.body.style.overflow = privacyOpen || termsOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [privacyOpen, termsOpen]);

  // ── Job fetch ───────────────────────────────────────────────────────────

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

  // Logged-in candidate: prefill identity + autofill fields from
  // /api/candidate/me so they don't retype data they already gave us. If
  // the profile already has a resume_path, expose the "use saved resume"
  // affordance — submitting without a new file lets the backend reuse the
  // existing snapshot (PR B / backend resume_required fallback).
  useEffect(() => {
    if (!isLoggedInCandidate) return;
    let cancelled = false;
    (async () => {
      try {
        const me = await getCandidateMe();
        if (cancelled) return;
        setForm((prev) => ({
          ...prev,
          full_name: me.full_name || prev.full_name,
          email: me.email,
          phone: me.phone ?? prev.phone,
          linkedin_url: me.linkedin_url ?? prev.linkedin_url,
        }));
        if (me.resume_path) {
          setSavedResumeFilename(me.resume_path.split("/").pop() ?? "resume");
        }
        setProfilePrefilled(true);
      } catch {
        // Non-fatal — the form still works without prefill. The candidate
        // can type their data manually.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isLoggedInCandidate]);

  useEffect(() => {
    if (!job) return;
    trackEvent("apply_start", { job_id: job.id, job_title: job.title });
  }, [job]);

  // ── Resume handling (drag-drop + click) ─────────────────────────────────

  function ingestResume(file: File | null) {
    setResumeError(null);
    if (!file) {
      setResumeFile(null);
      return;
    }
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setResumeError(
        t("publicJobs.application.resumeErrors.invalidExtension"),
      );
      return;
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setResumeError(
        t("publicJobs.application.resumeErrors.fileTooBig", {
          maxSize: MAX_FILE_SIZE_MB,
        }),
      );
      return;
    }
    setResumeFile(file);
  }

  function handleResumeChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    ingestResume(file);
    // Reset the input so the same file can be re-picked after a remove.
    e.target.value = "";
  }

  function clearResume() {
    setResumeFile(null);
    setResumeError(null);
  }

  // ── Step navigation ─────────────────────────────────────────────────────

  function handleNext() {
    if (!validateStep(step)) return;
    const next = Math.min(step + 1, TOTAL_STEPS) as Step;
    setStep(next);
    if (next > maxStep) setMaxStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function handleBack() {
    if (step > 1) {
      setStep((s) => (s - 1) as Step);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  }

  function jumpTo(target: Step) {
    if (target === step || target > maxStep) return;
    // Backward jumps are always free — the user can edit any reached step.
    if (target < step) {
      setStep(target);
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    // Forward jumps must clear validation for every intermediate step;
    // otherwise the candidate could re-break a field on step 1, click
    // step 3 in the stepper, and skip past the invalid state.
    for (let s = step; s < target; s++) {
      if (!validateStep(s as Step)) {
        setStep(s as Step);
        window.scrollTo({ top: 0, behavior: "smooth" });
        return;
      }
    }
    setStep(target);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // The form's onSubmit is ONLY allowed to perform the real network submit,
  // and only when we're on the final step. Any other submit-shaped event
  // (a stray Enter keypress, a future button that forgets type="button",
  // an implicit single-control form submission, etc.) is swallowed. This
  // is intentional belt-and-braces: a previous version routed non-final
  // submits through handleNext, which caused the wizard to surprise-submit
  // when transitioning between steps.
  function handleFormSubmit(e: FormEvent) {
    e.preventDefault();
    if (step !== TOTAL_STEPS) return;
    void doFinalSubmit();
  }

  /**
   * Pull a useful message out of a FastAPI error. Returns a Hebrew message
   * that mentions the offending field when we can identify one, so
   * candidates aren't stuck on a generic "something went wrong" toast.
   */
  function describeServerError(err: unknown): string {
    if (!axios.isAxiosError(err)) {
      return t("publicJobs.application.errors.generic");
    }
    const httpStatus = err.response?.status;
    const detail = err.response?.data?.detail;
    if (httpStatus === 409) {
      const code = typeof detail === "object" ? detail?.error_code : null;
      // already_applied_editable is handled by the caller (redirect to edit
      // page); only the locked + email-collision cases need a string here.
      if (code === "already_applied_locked") {
        return t("publicJobs.application.errors.alreadyApplied");
      }
      if (code === "email_already_registered") {
        return t("publicJobs.application.errors.emailAlreadyRegistered");
      }
      return t("publicJobs.application.errors.alreadyApplied");
    }
    if (httpStatus === 404) {
      return t("publicJobs.application.errors.jobUnavailable");
    }
    if (httpStatus === 400) {
      if (detail === "privacy_consent_required") {
        return t("publicJobs.application.validation.privacyRequired");
      }
      if (detail === "terms_consent_required") {
        return t("publicJobs.application.validation.termsRequired");
      }
      if (detail === "passwords_do_not_match") {
        return t("publicJobs.application.validation.passwordMismatch");
      }
      return t("publicJobs.application.errors.generic");
    }
    return t("publicJobs.application.errors.generic");
  }

  async function doFinalSubmit() {
    if (!Number.isFinite(jobId)) return;
    // Hard guard — submitting from anywhere other than the final step is a
    // bug. Bail out instead of POSTing a half-filled application.
    if (step !== TOTAL_STEPS) return;
    // Re-validate everything before final submit.
    if (!validateStep(1)) {
      setStep(1);
      return;
    }
    if (!validateStep(2)) {
      setStep(2);
      return;
    }
    if (!validateStep(3)) return;

    // Client-side guard for the claim password fields before the multipart
    // submission. The backend re-validates on the same source-of-truth.
    if (!isLoggedInCandidate && claimAccount) {
      if (claimPassword !== claimPasswordConfirm) {
        setClaimError(t("publicJobs.application.validation.passwordMismatch"));
        return;
      }
      if (claimPassword.length < 8) {
        setClaimError(t("publicJobs.application.validation.passwordMin"));
        return;
      }
      setClaimError(null);
    }

    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitApplication(jobId, form, resumeFile, {
        password:
          !isLoggedInCandidate && claimAccount && claimPassword
            ? claimPassword
            : null,
      });
      trackEvent("apply_submit", { job_id: jobId, job_title: job?.title ?? "" });
      setSuccess(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      // 409 already_applied_editable carries an application_id — redirect
      // the candidate straight to their existing application's editor (lands
      // in #610). For now navigate to the placeholder candidate-applications
      // route; if it 404s, the message in submitError still informs them.
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response?.data?.detail;
        if (
          detail &&
          typeof detail === "object" &&
          detail.error_code === "already_applied_editable" &&
          typeof detail.application_id === "number"
        ) {
          navigate(`/candidate/applications/${detail.application_id}`);
          return;
        }
      }
      setSubmitError(describeServerError(err));
    } finally {
      setSubmitting(false);
    }
  }

  // ── Early returns ───────────────────────────────────────────────────────

  if (jobLoading) {
    return (
      <div className="flex justify-center py-24">
        <div className="text-white/30">
          {t("publicJobs.application.loading")}
        </div>
      </div>
    );
  }

  if (jobError) {
    return (
      <div className="text-center">
        <div className="rounded-lg border border-danger/20 bg-danger/10 p-6 text-sm text-danger">
          {jobError}
        </div>
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
      <div className="flex min-h-screen items-center justify-center px-6 py-8">
      <div className="w-full max-w-2xl">
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
          {claimAccount && (
            <p className="mt-4 rounded-lg border border-copper/20 bg-copper/5 px-4 py-3 text-sm leading-relaxed text-white/65">
              {t("publicJobs.application.claim.accountCreated")}
            </p>
          )}
          <Link
            to="/jobs"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("publicJobs.application.browseMore")}
          </Link>
        </div>
      </div>
      </div>
    );
  }

  // ── Main render ─────────────────────────────────────────────────────────

  const stepHint =
    step === 1
      ? t("publicJobs.application.identityStepHint")
      : step === 2
        ? t("publicJobs.application.resumeStepHint")
        : null;

  return (
    /* full-width bg; StepNav siblings here are sticky-until-parent-ends */
    <div className="flex min-h-screen flex-col bg-page">
    <div className="flex-1 overflow-auto">
    <div className="mx-auto max-w-2xl px-6 pt-24 pb-8">
      <SeoHead
        title={
          job
            ? `${t("publicJobs.application.applyFor")} ${job.title}`
            : t("publicJobs.application.applyFor")
        }
        description={`${t("publicJobs.application.applyFor")}${job ? ` ${job.title}` : ""} ב-RS Recruiting.`}
        canonical={`${SITE_URL}/jobs/${jobId}/apply`}
        noIndex
      />

      <Link
        to={`/jobs/${jobId}`}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-white/35 transition hover:text-copper"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-4"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        {t("publicJobs.application.backToJob")}
      </Link>

      {/* Compact job header */}
      <div className="mb-8 flex items-start justify-between gap-4 rounded-xl border border-white/8 bg-card p-5 sm:p-6">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
            {t("publicJobs.application.applyFor")}
          </p>
          <h1 className="mt-1 truncate text-lg font-semibold text-white/90 sm:text-xl">
            {job?.title}
          </h1>
          {job?.location && (
            <p className="mt-0.5 flex items-center gap-1.5 text-xs text-white/40">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                className="size-3 shrink-0"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M8 1.5A4.5 4.5 0 0 0 3.5 6c0 2.625 3.375 7.5 4.5 7.5S12.5 8.625 12.5 6A4.5 4.5 0 0 0 8 1.5ZM8 7.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"
                  clipRule="evenodd"
                />
              </svg>
              {job.location}
            </p>
          )}
        </div>

      </div>

      <Stepper step={step} maxStep={maxStep} onJump={jumpTo} />

      <form id="apply-form" onSubmit={handleFormSubmit} className="mt-8 space-y-6" noValidate>
        {isLoggedInCandidate && profilePrefilled && (
          <div className="flex items-center gap-2 rounded-lg border border-copper/20 bg-copper/5 px-3 py-2 text-xs text-white/70">
            <span className="rounded-sm bg-copper/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-copper">
              {t("publicJobs.application.prefilledTag")}
            </span>
            <span className="truncate">
              {t("publicJobs.application.prefilledHint", { email: user!.email })}
            </span>
          </div>
        )}

        {submitError && (
          <div className="rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
            {submitError}
          </div>
        )}

        {stepHint && (
          <p className="text-sm leading-relaxed text-white/45">{stepHint}</p>
        )}

        <div key={step} className="page-enter">
          {step === 1 && (
            <IdentityStep
              form={form}
              fieldErrors={fieldErrors}
              onChange={handleChange}
              onBlur={handleBlur}
              emailReadOnly={isLoggedInCandidate}
            />
          )}
          {step === 2 && (
            <ResumeStep
              file={resumeFile}
              error={resumeError}
              savedResumeFilename={savedResumeFilename}
              onFile={ingestResume}
              onPick={handleResumeChange}
              onClear={clearResume}
              onClearSaved={() => setSavedResumeFilename(null)}
            />
          )}
          {step === 3 && (
            <>
              <QuestionsStep
                form={form}
                fieldErrors={fieldErrors}
                onChange={handleChange}
                onBlur={handleBlur}
                privacyAccepted={privacyAccepted}
                onPrivacyChange={setPrivacyAccepted}
                onPrivacyOpen={() => setPrivacyOpen(true)}
                termsAccepted={termsAccepted}
                onTermsChange={setTermsAccepted}
                onTermsOpen={() => setTermsOpen(true)}
                hideConsent={isLoggedInCandidate}
              />
              {!isLoggedInCandidate && (
                <ClaimAccountSection
                  enabled={claimAccount}
                  onToggle={setClaimAccount}
                  password={claimPassword}
                  onPasswordChange={setClaimPassword}
                  passwordConfirm={claimPasswordConfirm}
                  onPasswordConfirmChange={setClaimPasswordConfirm}
                  error={claimError}
                />
              )}
            </>
          )}
        </div>

      </form>


      {privacyOpen && (
        <PrivacyModal onClose={() => { setPrivacyAccepted(true); setPrivacyOpen(false); }} />
      )}
      {termsOpen && (
        <TermsModal onClose={() => { setTermsAccepted(true); setTermsOpen(false); }} />
      )}
    </div>
    </div>

    {/* StepNav — sticky bottom-0 INSIDE bg-page div, so it naturally stops
        at the footer (sticky can't extend past its parent's bounds).
        Full-width because it's inside the full-width bg-page wrapper.      */}
    <StepNav
      step={step}
      submitting={submitting}
      privacyAccepted={isLoggedInCandidate ? true : privacyAccepted}
      termsAccepted={isLoggedInCandidate ? true : termsAccepted}
      onBack={handleBack}
      onNext={handleNext}
    />
    </div>
  );
}

// ── Stepper ──────────────────────────────────────────────────────────────

function Stepper({
  step,
  maxStep,
  onJump,
}: {
  step: Step;
  maxStep: Step;
  onJump: (s: Step) => void;
}) {
  const { t } = useTranslation();
  const labels: [Step, string][] = [
    [1, t("publicJobs.application.steps.identity")],
    [2, t("publicJobs.application.steps.resume")],
    [3, t("publicJobs.application.steps.questions")],
  ];
  return (
    <div>
      <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">
        {t("publicJobs.application.steps.indicator", {
          current: step,
          total: TOTAL_STEPS,
        })}
      </p>
      {/* Step 1 sits at the visual start of the row — in RTL that means
          the right side. Hebrew labels render naturally. */}
      <ol className="flex items-center gap-2">
        {labels.map(([n, label], i) => {
          const isActive = n === step;
          const isComplete = n < step;
          const isReachable = n <= maxStep;
          return (
            <li
              key={n}
              className="flex flex-1 items-center gap-2 first:ms-0 last:me-0"
            >
              <button
                type="button"
                disabled={!isReachable}
                onClick={() => onJump(n)}
                aria-current={isActive ? "step" : undefined}
                className={[
                  "group flex flex-1 items-center gap-2 rounded-full border px-2.5 py-1.5 text-xs transition",
                  isActive
                    ? "border-copper bg-copper/15 text-white"
                    : isComplete
                      ? "border-copper/30 text-white/70 hover:border-copper/60 hover:bg-copper/10"
                      : "border-white/10 text-white/35",
                  !isReachable && "cursor-default",
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                <span
                  className={[
                    "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                    isActive
                      ? "bg-copper text-white"
                      : isComplete
                        ? "bg-copper/80 text-white"
                        : "bg-white/8 text-white/50",
                  ].join(" ")}
                >
                  {isComplete ? (
                    <svg
                      viewBox="0 0 16 16"
                      fill="currentColor"
                      className="size-3"
                      aria-hidden="true"
                    >
                      <path
                        fillRule="evenodd"
                        d="M14.78 4.22a.75.75 0 0 1 0 1.06l-7 7a.75.75 0 0 1-1.06 0l-3.5-3.5a.75.75 0 1 1 1.06-1.06L7.25 10.69l6.47-6.47a.75.75 0 0 1 1.06 0Z"
                        clipRule="evenodd"
                      />
                    </svg>
                  ) : (
                    n
                  )}
                </span>
                <span className="truncate font-medium">{label}</span>
              </button>
              {i < labels.length - 1 && (
                <span
                  aria-hidden="true"
                  className={`h-px flex-1 transition-colors ${
                    isComplete ? "bg-copper/40" : "bg-white/8"
                  }`}
                />
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

// ── Step 1: Identity ─────────────────────────────────────────────────────

function IdentityStep({
  form,
  fieldErrors,
  onChange,
  onBlur,
  emailReadOnly = false,
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  emailReadOnly?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-4 sm:grid-cols-2 sm:gap-x-6 sm:gap-y-5">
      <Field
        label={t("publicJobs.application.fullName")}
        id="full_name"
        required
      >
        <input
          id="full_name"
          name="full_name"
          type="text"
          required
          value={form.full_name}
          onChange={onChange}
          onBlur={onBlur}
          className={inputCls}
          placeholder={t("publicJobs.application.placeholders.fullName")}
          autoComplete="name"
          aria-invalid={!!fieldErrors.full_name}
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
          onChange={onChange}
          onBlur={onBlur}
          className={inputCls}
          placeholder={t("publicJobs.application.placeholders.email")}
          autoComplete="email"
          aria-invalid={!!fieldErrors.email}
          readOnly={emailReadOnly}
          aria-readonly={emailReadOnly}
          title={
            emailReadOnly
              ? t("publicJobs.application.emailLockedHint")
              : undefined
          }
        />
        {fieldErrors.email && (
          <p className="mt-1 text-xs text-danger">{fieldErrors.email}</p>
        )}
      </Field>

      <Field label={t("publicJobs.application.phone")} id="phone" required>
        <input
          id="phone"
          name="phone"
          type="tel"
          value={form.phone}
          onChange={onChange}
          onBlur={onBlur}
          className={inputCls}
          placeholder={t("publicJobs.application.placeholders.phone")}
          autoComplete="tel"
          aria-invalid={!!fieldErrors.phone}
        />
        {fieldErrors.phone && (
          <p className="mt-1 text-xs text-danger">{fieldErrors.phone}</p>
        )}
      </Field>

      <Field
        label={t("publicJobs.application.linkedin")}
        id="linkedin_url"
        optional
        className="sm:col-span-2"
      >
        <input
          id="linkedin_url"
          name="linkedin_url"
          type="url"
          value={form.linkedin_url}
          onChange={onChange}
          onBlur={onBlur}
          className={inputCls}
          placeholder={t("publicJobs.application.placeholders.linkedin")}
          aria-invalid={!!fieldErrors.linkedin_url}
        />
        {fieldErrors.linkedin_url && (
          <p className="mt-1 text-xs text-danger">{fieldErrors.linkedin_url}</p>
        )}
      </Field>
    </div>
  );
}

// ── Step 2: Resume ───────────────────────────────────────────────────────

function ResumeStep({
  file,
  error,
  savedResumeFilename,
  onFile,
  onPick,
  onClear,
  onClearSaved,
}: {
  file: File | null;
  error: string | null;
  savedResumeFilename: string | null;
  onFile: (f: File | null) => void;
  onPick: (e: ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
  onClearSaved: () => void;
}) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragging, setDragging] = useState(false);

  function onDragOver(e: DragEvent<HTMLButtonElement>) {
    e.preventDefault();
    if (!dragging) setDragging(true);
  }
  function onDragLeave() {
    setDragging(false);
  }
  function onDrop(e: DragEvent<HTMLButtonElement>) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files?.[0] ?? null;
    onFile(dropped);
  }

  // Logged-in candidate w/ a profile resume on file and no new pick yet —
  // show the "use saved resume" card so submitting w/o an upload reuses
  // it server-side (no extra storage cost, no re-upload).
  const showSavedResume = !file && savedResumeFilename;

  return (
    <div>
      {showSavedResume ? (
        <div className="flex items-center gap-3 rounded-xl border border-copper/30 bg-card-raised p-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-copper/15 text-copper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="size-5"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6"
              />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white/85">
              {savedResumeFilename}
            </p>
            <p className="mt-0.5 text-xs text-white/40">
              {t("publicJobs.application.resumeSavedHint")}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onClearSaved();
              inputRef.current?.click();
            }}
            className="shrink-0 rounded-sm border border-white/15 px-3 py-1.5 text-xs text-white/65 transition hover:border-copper/50 hover:text-copper"
          >
            {t("publicJobs.application.resumeReplace")}
          </button>
        </div>
      ) : file ? (
        <div className="flex items-center gap-3 rounded-xl border border-copper/30 bg-card-raised p-4">
          <span className="flex size-10 shrink-0 items-center justify-center rounded-md bg-copper/15 text-copper">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="size-5"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Zm0 0v6h6"
              />
            </svg>
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-white/85">
              {file.name}
            </p>
            <p className="mt-0.5 text-xs text-white/40">
              {t("publicJobs.application.fileSizeBytes", {
                kb: Math.round(file.size / 1024).toLocaleString("he-IL"),
              })}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              onClear();
              inputRef.current?.click();
            }}
            className="shrink-0 rounded-sm border border-white/15 px-3 py-1.5 text-xs text-white/65 transition hover:border-copper/50 hover:text-copper"
          >
            {t("publicJobs.application.resumeReplace")}
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          aria-label={t("publicJobs.application.resumeUpload")}
          className={[
            "flex w-full flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors duration-200",
            dragging
              ? "border-copper bg-copper/10"
              : "border-white/15 bg-card hover:border-copper/40 hover:bg-card-raised",
          ].join(" ")}
        >
          <span
            className={`flex size-12 items-center justify-center rounded-full border transition-colors ${
              dragging
                ? "border-copper bg-copper/20 text-copper"
                : "border-copper/30 bg-copper/10 text-copper"
            }`}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              className="size-5"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 16V4m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
              />
            </svg>
          </span>
          <span className="text-sm font-medium text-white/80">
            {t("publicJobs.application.resumeDropPrompt")}
          </span>
          <span className="text-xs text-white/45">
            {t("publicJobs.application.resumeDropAlt")}
          </span>
        </button>
      )}

      <input
        ref={inputRef}
        id="resume"
        name="resume"
        type="file"
        accept=".pdf,.doc,.docx"
        onChange={onPick}
        className="sr-only"
      />

      {error && <p className="mt-3 text-xs text-danger">{error}</p>}
      <p className="mt-3 text-xs text-white/30">
        {t("publicJobs.application.fileHint", { maxSize: MAX_FILE_SIZE_MB })}
      </p>
    </div>
  );
}

// ── Step 3: Optional questions ───────────────────────────────────────────

function QuestionsStep({
  form,
  fieldErrors,
  onChange,
  onBlur,
  privacyAccepted,
  onPrivacyChange,
  onPrivacyOpen,
  termsAccepted,
  onTermsChange,
  onTermsOpen,
  hideConsent = false,
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  privacyAccepted: boolean;
  onPrivacyChange: (v: boolean) => void;
  onPrivacyOpen: () => void;
  termsAccepted: boolean;
  onTermsChange: (v: boolean) => void;
  onTermsOpen: () => void;
  hideConsent?: boolean;
}) {
  const { t } = useTranslation();
  const fields: Array<{ name: keyof typeof form; label: string; ph: string }> =
    [
      {
        name: "service_concept",
        label: t("publicJobs.application.serviceConcept"),
        ph: t("publicJobs.application.placeholders.serviceConcept"),
      },
      {
        name: "salary_expectations",
        label: t("publicJobs.application.salaryExpectations"),
        ph: t("publicJobs.application.placeholders.salaryExpectations"),
      },
      {
        name: "strength",
        label: t("publicJobs.application.strength"),
        ph: t("publicJobs.application.placeholders.strength"),
      },
      {
        name: "growth_area",
        label: t("publicJobs.application.growthArea"),
        ph: t("publicJobs.application.placeholders.growthArea"),
      },
    ];
  return (
    <div className="grid gap-5 sm:grid-cols-2">
      <div className="rounded-lg border border-copper/20 bg-copper/5 p-4 sm:col-span-2">
        <p className="text-xs leading-relaxed text-white/65">
          {t("publicJobs.application.questionsStepBanner")}
        </p>
      </div>

      {fields.map(({ name, label, ph }) => {
        const value = form[name] ?? "";
        const count = value.length;
        const over = count > TEXT_FIELD_MAX;
        const isHalf = name === "strength" || name === "growth_area";
        return (
          <Field key={name} label={label} id={name} optional className={isHalf ? "sm:col-span-1" : "sm:col-span-2"}>
            <textarea
              id={name}
              name={name}
              value={value}
              onChange={onChange}
              onBlur={onBlur}
              className={textareaCls}
              placeholder={ph}
              maxLength={TEXT_FIELD_MAX}
              aria-invalid={!!fieldErrors[name]}
            />
            <div className="mt-1 flex items-start justify-between gap-2">
              <span className="text-xs text-danger">
                {fieldErrors[name] ?? ""}
              </span>
              <span
                className={`shrink-0 text-[11px] tabular-nums ${
                  over ? "text-danger" : "text-white/30"
                }`}
              >
                {t("publicJobs.application.charCount", {
                  count,
                  max: TEXT_FIELD_MAX,
                })}
              </span>
            </div>
          </Field>
        );
      })}

      {/* Consent blocks are hidden for logged-in candidates — consent was
          captured at activation time (Sprint 11 / #605). */}
      {!hideConsent && (
      <>
      {/* Site Terms of Service consent — spans full width of the 2-col grid */}
      <div
        className={`sm:col-span-2 rounded-xl border p-4 transition-colors ${
          fieldErrors.terms
            ? "border-danger/40 bg-danger/5"
            : "border-white/10 bg-card"
        }`}
      >
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("publicJobs.application.termsConsentTitle")}
        </p>
        <p className="mt-2 text-xs leading-relaxed text-white/55">
          {t("publicJobs.application.termsConsentPreview")}
        </p>
        <button
          type="button"
          onClick={onTermsOpen}
          className="mt-1 text-xs text-copper/80 underline-offset-2 hover:text-copper hover:underline"
        >
          {t("publicJobs.application.termsConsentReadFull")}
        </button>
        <label className="mt-3 flex cursor-pointer items-start gap-2.5">
          <input
            type="checkbox"
            checked={termsAccepted}
            onChange={(e) => onTermsChange(e.target.checked)}
            className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
            aria-describedby={fieldErrors.terms ? "terms-error" : undefined}
          />
          <span className="text-sm text-white/80">
            {t("publicJobs.application.termsConsentCheckbox")}
          </span>
        </label>
        {fieldErrors.terms && (
          <p id="terms-error" className="mt-2 text-xs text-danger">
            {fieldErrors.terms}
          </p>
        )}
      </div>

      {/* Privacy consent — spans full width of the 2-col grid */}
      <div
        className={`sm:col-span-2 rounded-xl border p-4 transition-colors ${
          fieldErrors.privacy
            ? "border-danger/40 bg-danger/5"
            : "border-white/10 bg-card"
        }`}
      >
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("publicJobs.application.privacyConsentTitle")}
        </p>
        <p className="mt-2 text-xs leading-relaxed text-white/55">
          {t("publicJobs.application.privacyConsentPreview")}
        </p>
        <button
          type="button"
          onClick={onPrivacyOpen}
          className="mt-1 text-xs text-copper/80 underline-offset-2 hover:text-copper hover:underline"
        >
          {t("publicJobs.application.privacyConsentReadFull")}
        </button>
        <label className="mt-3 flex cursor-pointer items-start gap-2.5">
          <input
            type="checkbox"
            checked={privacyAccepted}
            onChange={(e) => onPrivacyChange(e.target.checked)}
            className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
            aria-describedby={fieldErrors.privacy ? "privacy-error" : undefined}
          />
          <span className="text-sm text-white/80">
            {t("publicJobs.application.privacyConsentCheckbox")}
          </span>
        </label>
        {fieldErrors.privacy && (
          <p id="privacy-error" className="mt-2 text-xs text-danger">
            {fieldErrors.privacy}
          </p>
        )}
      </div>
      </>
      )}
    </div>
  );
}

function ClaimAccountSection({
  enabled,
  onToggle,
  password,
  onPasswordChange,
  passwordConfirm,
  onPasswordConfirmChange,
  error,
}: {
  enabled: boolean;
  onToggle: (v: boolean) => void;
  password: string;
  onPasswordChange: (v: string) => void;
  passwordConfirm: string;
  onPasswordConfirmChange: (v: string) => void;
  error: string | null;
}) {
  const { t } = useTranslation();
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  function validatePassword(val: string): string | null {
    if (val && val.length < 8) return t("publicJobs.application.validation.passwordMin");
    return null;
  }

  function validateConfirm(val: string, pw: string): string | null {
    if (val && val !== pw) return t("publicJobs.application.validation.passwordMismatch");
    return null;
  }

  return (
    <div className="sm:col-span-2 mt-3 rounded-xl border border-white/10 bg-card p-4">
      <label className="flex cursor-pointer items-start gap-2.5">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onToggle(e.target.checked)}
          className="mt-0.5 size-4 shrink-0 cursor-pointer accent-copper"
        />
        <span className="text-sm text-white/80">
          {t("publicJobs.application.claim.toggle")}
        </span>
      </label>
      <p className="mt-1 ms-7 text-xs text-white/50">
        {t("publicJobs.application.claim.description")}
      </p>

      {enabled && (
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <label
              htmlFor="claim_password"
              className="block text-xs text-white/55"
            >
              {t("publicJobs.application.claim.passwordLabel")}
            </label>
            <input
              id="claim_password"
              name="claim_password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                onPasswordChange(e.target.value);
                if (passwordError) setPasswordError(null);
                if (confirmError && passwordConfirm) setConfirmError(validateConfirm(passwordConfirm, e.target.value));
              }}
              onBlur={(e) => setPasswordError(validatePassword(e.target.value))}
              aria-invalid={!!passwordError}
              className={`mt-1 ${inputCls}`}
            />
            {passwordError && (
              <p className="mt-1 text-xs text-danger">{passwordError}</p>
            )}
          </div>
          <div>
            <label
              htmlFor="claim_password_confirm"
              className="block text-xs text-white/55"
            >
              {t("publicJobs.application.claim.passwordConfirmLabel")}
            </label>
            <input
              id="claim_password_confirm"
              name="claim_password_confirm"
              type="password"
              autoComplete="new-password"
              value={passwordConfirm}
              onChange={(e) => {
                onPasswordConfirmChange(e.target.value);
                if (confirmError) setConfirmError(null);
              }}
              onBlur={(e) => setConfirmError(validateConfirm(e.target.value, password))}
              aria-invalid={!!confirmError}
              className={`mt-1 ${inputCls}`}
            />
            {confirmError && (
              <p className="mt-1 text-xs text-danger">{confirmError}</p>
            )}
          </div>
          {error && (
            <p className="text-xs text-danger sm:col-span-2">{error}</p>
          )}
        </div>
      )}
    </div>
  );
}

// ── Privacy policy modal ──────────────────────────────────────────────────

function PrivacyModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  return createPortal(
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
          <h2 className="text-sm font-medium text-white/80">
            {t("publicJobs.application.privacyConsentTitle")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-white/40 transition hover:text-white/70"
            aria-label={t("common.close")}
          >
            ✕
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
          {t("auth.register.agreementTextPrivacy")
            .split("\n\n")
            .map((para, i) => (
              <p key={i} className="text-sm leading-7 text-white/55">
                {para}
              </p>
            ))}
        </div>
        <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// ── Site Terms of Service modal ──────────────────────────────────────────

function TermsModal({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  return createPortal(
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
        <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
          <h2 className="text-sm font-medium text-white/80">
            {t("publicJobs.application.termsConsentTitle")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-white/40 transition hover:text-white/70"
            aria-label={t("common.close")}
          >
            ✕
          </button>
        </div>
        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
          {t("auth.register.agreementTextSiteTerms")
            .split("\n\n")
            .map((para, i) => (
              <p key={i} className="text-sm leading-7 text-white/55">
                {para}
              </p>
            ))}
        </div>
        <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">
          <button
            type="button"
            onClick={onClose}
            className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// ── Sticky bottom nav ────────────────────────────────────────────────────

function StepNav({
  step,
  submitting,
  privacyAccepted,
  termsAccepted,
  onBack,
  onNext,
}: {
  step: Step;
  submitting: boolean;
  privacyAccepted: boolean;
  termsAccepted: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const isFinal = step === TOTAL_STEPS;
  // Sticky bottom-0 — works as sibling of content inside min-h-screen flex-col.
  // Naturally stops before the footer (sticky can't extend past its parent).
  return (
    <div className="sticky bottom-0 z-40 border-t border-white/8 bg-page/96 px-6 py-3 backdrop-blur-md">
      <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={step === 1}
          className="rounded-sm border border-white/15 px-4 py-2 text-sm text-white/65 transition hover:border-white/35 hover:text-white/90 disabled:cursor-not-allowed disabled:opacity-30"
        >
          {t("publicJobs.application.steps.back")}
        </button>
        {isFinal ? (
          // Distinct `key` from the Continue button — guarantees React mounts
          // a fresh DOM node rather than reusing the same <button> and just
          // flipping `type` from "button" to "submit". Without this, an
          // in-flight pointer sequence on the old Continue button could land
          // on the now-submit button after the step transition and trigger
          // an unwanted form submission.
          <button
            key="step-final-submit"
            type="submit"
            form="apply-form"
            disabled={submitting || !privacyAccepted || !termsAccepted}
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50 sm:px-8 sm:py-3 sm:text-base"
          >
            {submitting
              ? t("publicJobs.application.submittingText")
              : t("publicJobs.application.submitText")}
          </button>
        ) : (
          <button
            key="step-continue"
            type="button"
            onClick={(e) => {
              // Defensive: block any onward propagation that could in theory
              // reach the form and trigger a submit handler in the same tick.
              e.preventDefault();
              e.stopPropagation();
              onNext();
            }}
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold sm:px-8 sm:py-3 sm:text-base"
          >
            {t("publicJobs.application.steps.continue")}
          </button>
        )}
      </div>
    </div>
  );
}
