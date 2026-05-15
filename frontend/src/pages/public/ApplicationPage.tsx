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
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import type { CandidateApplicationForm, JobPublicRead } from "@/types/api";
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
  personality_weakness: "",
  personality_strength: "",
};

const STEP_1_FIELDS = ["full_name", "email", "phone", "linkedin_url"] as const;
const STEP_3_FIELDS = [
  "service_concept",
  "salary_expectations",
  "personality_strength",
  "personality_weakness",
] as const;

const textareaCls = textareaBase + " min-h-[96px]";

// ── Reusable field wrapper ────────────────────────────────────────────────

interface FieldProps {
  label: string;
  id: string;
  required?: boolean;
  optional?: boolean;
  children: ReactNode;
}

function Field({ label, id, required, optional, children }: FieldProps) {
  const { t } = useTranslation();
  return (
    <div data-field={id}>
      <label
        htmlFor={id}
        className="flex items-center gap-1.5 text-xs text-white/55"
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

  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);

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
      if (!resumeFile) {
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
    if (!privacyAccepted) {
      errors.privacy = t("publicJobs.application.validation.privacyRequired");
      ok = false;
    } else {
      delete errors.privacy;
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

  // Lock body scroll when privacy modal is open
  useEffect(() => {
    document.body.style.overflow = privacyOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [privacyOpen]);

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
    if (httpStatus === 409) {
      return t("publicJobs.application.errors.alreadyApplied");
    }
    if (httpStatus === 404) {
      return t("publicJobs.application.errors.jobUnavailable");
    }
    if (httpStatus === 400) {
      const detail = err.response?.data?.detail;
      if (detail === "privacy_consent_required") {
        return t("publicJobs.application.validation.privacyRequired");
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

    setSubmitting(true);
    setSubmitError(null);

    try {
      await submitApplication(jobId, form, resumeFile);
      setSuccess(true);
    } catch (err) {
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

  // ── Main render ─────────────────────────────────────────────────────────

  const stepHint =
    step === 1
      ? t("publicJobs.application.identityStepHint")
      : step === 2
        ? t("publicJobs.application.resumeStepHint")
        : null;

  return (
    <div className="mx-auto max-w-2xl px-6 pt-24 pb-24">
      {job && (
        <SeoHead
          title={`${t("publicJobs.application.applyFor")} ${job.title}`}
          description={`${t("publicJobs.application.applyFor")} ${job.title} ב-RS Recruiting.`}
          canonical={`${SITE_URL}/jobs/${jobId}/apply`}
        />
      )}

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
      <div className="mb-5 flex items-start justify-between gap-4 rounded-xl border border-white/8 bg-card p-4">
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
        <span className="shrink-0 rounded-full bg-success/10 px-2.5 py-0.5 text-[10px] font-medium text-success">
          {t("publicJobs.board.open")}
        </span>
      </div>

      <Stepper step={step} maxStep={maxStep} onJump={jumpTo} />

      <form onSubmit={handleFormSubmit} className="mt-8 space-y-6" noValidate>
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
            />
          )}
          {step === 2 && (
            <ResumeStep
              file={resumeFile}
              error={resumeError}
              onFile={ingestResume}
              onPick={handleResumeChange}
              onClear={clearResume}
            />
          )}
          {step === 3 && (
            <QuestionsStep
              form={form}
              fieldErrors={fieldErrors}
              onChange={handleChange}
              onBlur={handleBlur}
              privacyAccepted={privacyAccepted}
              onPrivacyChange={setPrivacyAccepted}
              onPrivacyOpen={() => setPrivacyOpen(true)}
            />
          )}
        </div>

        <StepNav
          step={step}
          submitting={submitting}
          privacyAccepted={privacyAccepted}
          onBack={handleBack}
          onNext={handleNext}
        />
      </form>

      {privacyOpen && (
        <PrivacyModal onClose={() => setPrivacyOpen(false)} />
      )}
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
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="space-y-4">
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
  onFile,
  onPick,
  onClear,
}: {
  file: File | null;
  error: string | null;
  onFile: (f: File | null) => void;
  onPick: (e: ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
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

  return (
    <div>
      {file ? (
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
}: {
  form: Omit<CandidateApplicationForm, "job_id">;
  fieldErrors: Record<string, string>;
  onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  onBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
  privacyAccepted: boolean;
  onPrivacyChange: (v: boolean) => void;
  onPrivacyOpen: () => void;
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
        name: "personality_strength",
        label: t("publicJobs.application.strength"),
        ph: t("publicJobs.application.placeholders.strength"),
      },
      {
        name: "personality_weakness",
        label: t("publicJobs.application.weakness"),
        ph: t("publicJobs.application.placeholders.weakness"),
      },
    ];
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-copper/20 bg-copper/5 p-4">
        <p className="text-xs leading-relaxed text-white/65">
          {t("publicJobs.application.questionsStepBanner")}
        </p>
      </div>

      {fields.map(({ name, label, ph }) => {
        const value = form[name] ?? "";
        const count = value.length;
        const over = count > TEXT_FIELD_MAX;
        return (
          <Field key={name} label={label} id={name} optional>
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

      {/* Privacy consent */}
      <div
        className={`rounded-xl border p-4 transition-colors ${
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
            aria-label="סגור"
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
  onBack,
  onNext,
}: {
  step: Step;
  submitting: boolean;
  privacyAccepted: boolean;
  onBack: () => void;
  onNext: () => void;
}) {
  const { t } = useTranslation();
  const isFinal = step === TOTAL_STEPS;
  return (
    <div className="sticky bottom-0 -mx-4 mt-4 border-t border-white/8 bg-page/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-page/80 sm:-mx-6 sm:px-6">
      <div className="flex items-center justify-between gap-3">
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
            disabled={submitting || !privacyAccepted}
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-50"
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
            className="rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("publicJobs.application.steps.continue")}
          </button>
        )}
      </div>
    </div>
  );
}
