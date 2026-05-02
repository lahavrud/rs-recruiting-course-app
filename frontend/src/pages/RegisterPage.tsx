import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { register } from "@/services/auth";
import { useAuth } from "@/hooks/useAuth";
import Logo from "@/components/ui/Logo";
import SignatureCanvas, { type SignatureCanvasRef } from "@/components/ui/SignatureCanvas";
import { inputCls } from "@/styles/forms";
import axios from "axios";

function useValidation() {
  const { t } = useTranslation();
  return {
    validateEmail(v: string): string {
      if (!v.trim()) return t("auth.register.validation.emailRequired");
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v))
        return t("auth.register.validation.emailInvalid");
      return "";
    },
    validatePassword(v: string): string {
      if (!v) return t("auth.register.validation.passwordRequired");
      if (v.length < 8) return t("auth.register.validation.passwordMin");
      if (!/[A-Z]/.test(v)) return t("auth.register.validation.passwordUppercase");
      if (!/[a-z]/.test(v)) return t("auth.register.validation.passwordLowercase");
      if (!/\d/.test(v)) return t("auth.register.validation.passwordDigit");
      if (!/[^A-Za-z0-9]/.test(v)) return t("auth.register.validation.passwordSpecial");
      return "";
    },
    validateConfirm(v: string, pw: string): string {
      if (!v) return t("auth.register.validation.confirmRequired");
      if (v !== pw) return t("auth.register.validation.confirmMismatch");
      return "";
    },
    validateCompanyName(v: string): string {
      if (!v.trim()) return t("auth.register.validation.companyNameRequired");
      if (v.length > 100) return t("auth.register.validation.companyNameMax");
      return "";
    },
    validateCompanyId(v: string): string {
      if (!v.trim()) return t("auth.register.validation.companyIdRequired");
      if (!/^\d{9}$/.test(v)) return t("auth.register.validation.companyIdInvalid");
      return "";
    },
    validateContactFirstName(v: string): string {
      if (!v.trim()) return t("auth.register.validation.contactFirstNameRequired");
      return "";
    },
    validateContactLastName(v: string): string {
      if (!v.trim()) return t("auth.register.validation.contactLastNameRequired");
      return "";
    },
    validateMobilePhone(v: string): string {
      if (!v.trim()) return t("auth.register.validation.mobilePhoneRequired");
      if (!/^05[0-9]\d{7}$/.test(v.replace(/[-\s]/g, "")))
        return t("auth.register.validation.mobilePhoneInvalid");
      return "";
    },
    validateLogo(f: File | null): string {
      if (!f) return t("auth.register.validation.logoRequired");
      return "";
    },
    validateSignature(isEmpty: boolean): string {
      if (isEmpty) return t("auth.register.validation.signatureRequired");
      return "";
    },
  };
}

interface FormState {
  email: string;
  password: string;
  confirm: string;
  companyName: string;
  companyId: string;
  contactFirstName: string;
  contactLastName: string;
  contactMobilePhone: string;
  contactLandlinePhone: string;
}

const EMPTY: FormState = {
  email: "",
  password: "",
  confirm: "",
  companyName: "",
  companyId: "",
  contactFirstName: "",
  contactLastName: "",
  contactMobilePhone: "",
  contactLandlinePhone: "",
};

export default function RegisterPage() {
  const { t } = useTranslation();
  const val = useValidation();
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token");

  const [form, setForm] = useState<FormState>(EMPTY);
  const [fieldErrors, setFieldErrors] = useState<
    Partial<FormState & { logo: string; signature: string }>
  >({});
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [agreementOpen, setAgreementOpen] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const sigCanvasRef = useRef<SignatureCanvasRef>(null);

  useEffect(() => {
    if (agreementOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [agreementOpen]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  if (!inviteToken) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void px-4">
        <div className="w-full max-w-md rounded-xl border border-white/10 bg-card p-8 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-lg text-warning">
            ✕
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth.register.noToken.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth.register.noToken.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth.register.noToken.backToLogin")}
          </Link>
        </div>
      </div>
    );
  }

  function set(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (fieldErrors[field]) setFieldErrors((prev) => ({ ...prev, [field]: "" }));
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    set(e.target.name as keyof FormState, e.target.value);
  }

  function handleBlur(e: ChangeEvent<HTMLInputElement>) {
    const { name, value } = e.target;
    const err = getFieldError(name as keyof FormState, value);
    setFieldErrors((prev) => ({ ...prev, [name]: err }));
  }

  function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setLogoFile(file);
    if (file) setFieldErrors((prev) => ({ ...prev, logo: "" }));
  }

  function getFieldError(field: keyof FormState, value: string): string {
    switch (field) {
      case "email":
        return val.validateEmail(value);
      case "password":
        return val.validatePassword(value);
      case "confirm":
        return val.validateConfirm(value, form.password);
      case "companyName":
        return val.validateCompanyName(value);
      case "companyId":
        return val.validateCompanyId(value);
      case "contactFirstName":
        return val.validateContactFirstName(value);
      case "contactLastName":
        return val.validateContactLastName(value);
      case "contactMobilePhone":
        return val.validateMobilePhone(value);
      default:
        return "";
    }
  }

  function validateAll(): boolean {
    const errors: Partial<FormState & { logo: string; signature: string }> = {
      email: val.validateEmail(form.email),
      password: val.validatePassword(form.password),
      confirm: val.validateConfirm(form.confirm, form.password),
      companyName: val.validateCompanyName(form.companyName),
      companyId: val.validateCompanyId(form.companyId),
      contactFirstName: val.validateContactFirstName(form.contactFirstName),
      contactLastName: val.validateContactLastName(form.contactLastName),
      contactMobilePhone: val.validateMobilePhone(form.contactMobilePhone),
      logo: val.validateLogo(logoFile),
      signature: val.validateSignature(sigCanvasRef.current?.isEmpty() ?? true),
    };
    setFieldErrors(errors);
    return Object.values(errors).every((e) => !e);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validateAll()) return;

    const dataUrl = sigCanvasRef.current!.toDataURL();
    // Strip the "data:image/png;base64," prefix — backend expects raw base64
    const sigBase64 = dataUrl.split(",")[1] ?? "";

    const fd = new FormData();
    fd.append("email", form.email.trim());
    fd.append("password", form.password);
    fd.append("company_name", form.companyName.trim());
    fd.append("company_id", form.companyId.trim());
    fd.append("contact_first_name", form.contactFirstName.trim());
    fd.append("contact_last_name", form.contactLastName.trim());
    fd.append("contact_mobile_phone", form.contactMobilePhone.trim());
    if (form.contactLandlinePhone.trim()) {
      fd.append("contact_landline_phone", form.contactLandlinePhone.trim());
    }
    fd.append("agreement_signature", sigBase64);
    fd.append("logo", logoFile!);

    setSubmitting(true);
    setSubmitError(null);
    try {
      await register(fd, inviteToken!);
      setSuccess(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 422) {
          // Extract the first validation error message and show it on the relevant field
          const detail = err.response?.data?.detail;
          const errors = Array.isArray(detail) ? detail : [];
          const passwordError = errors.find(
            (e: { loc?: string[] }) => e.loc?.includes("password"),
          );
          if (passwordError) {
            setFieldErrors((prev) => ({ ...prev, password: passwordError.msg }));
          } else {
            setSubmitError(t("auth.register.errors.failed"));
          }
        } else if (status === 429) {
          setSubmitError(t("auth.register.errors.tooManyAttempts"));
        } else if (status === 400) {
          const detail = (err.response?.data?.detail ?? "") as string;
          if (
            detail.toLowerCase().includes("invite") ||
            detail.toLowerCase().includes("token")
          ) {
            setSubmitError(t("auth.register.errors.invalidToken"));
          } else {
            setSubmitError(t("auth.register.errors.emailExists"));
          }
        } else if (status === 409) {
          setSubmitError(t("auth.register.errors.emailExists"));
        } else {
          setSubmitError(t("auth.register.errors.failed"));
        }
      } else {
        setSubmitError(t("auth.register.errors.unexpected"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
        <div className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth.register.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth.register.success.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth.register.success.backToLogin")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-void px-4 py-10 md:py-14">
      <div className="mx-auto max-w-4xl">
        {/* Header */}
        <div className="mb-8 flex items-center gap-3">
          <Logo size={32} />
          <div>
            <h1 className="text-xl font-semibold text-white/90">{t("auth.register.title")}</h1>
            <p className="text-xs text-white/40">{t("auth.register.subtitle")}</p>
          </div>
        </div>

        {submitError && (
          <div className="mb-6 rounded-lg border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
            {submitError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {/* ── Left panel: company + contact ── */}
            <div className="space-y-5">
              {/* Company details */}
              <div className="rounded-xl border border-white/8 border-t-copper/40 bg-card p-6">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                  {t("auth.register.companySection")}
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.companyName")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="companyName"
                      type="text"
                      required
                      maxLength={100}
                      value={form.companyName}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.companyNamePlaceholder")}
                      autoComplete="organization"
                    />
                    {fieldErrors.companyName && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.companyName}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.companyIdLabel")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="companyId"
                      type="text"
                      required
                      maxLength={9}
                      value={form.companyId}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.companyIdPlaceholder")}
                      dir="ltr"
                    />
                    {fieldErrors.companyId && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.companyId}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.logoLabel")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      ref={logoInputRef}
                      type="file"
                      accept="image/*"
                      onChange={handleLogoChange}
                      className="mt-1 block w-full cursor-pointer rounded-sm border border-white/10 bg-well px-3 py-2 text-sm text-white/60 file:mr-4 file:rounded-sm file:border-0 file:bg-copper/20 file:px-3 file:py-1 file:text-xs file:font-medium file:text-copper hover:file:bg-copper/30"
                    />
                    {logoFile && (
                      <p className="mt-1 text-xs text-white/30">{logoFile.name}</p>
                    )}
                    {fieldErrors.logo && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.logo}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Contact person */}
              <div className="rounded-xl border border-white/8 bg-card p-6">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                  {t("auth.register.contactSection", "פרטי איש קשר")}
                </p>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm text-white/50">
                        {t("auth.register.contactFirstName")}{" "}
                        <span className="text-copper/80">*</span>
                      </label>
                      <input
                        name="contactFirstName"
                        type="text"
                        required
                        maxLength={100}
                        value={form.contactFirstName}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        className={`mt-1 ${inputCls}`}
                        placeholder={t("auth.register.contactFirstNamePlaceholder")}
                        autoComplete="given-name"
                      />
                      {fieldErrors.contactFirstName && (
                        <p className="mt-1 text-xs text-danger">{fieldErrors.contactFirstName}</p>
                      )}
                    </div>
                    <div>
                      <label className="block text-sm text-white/50">
                        {t("auth.register.contactLastName")}{" "}
                        <span className="text-copper/80">*</span>
                      </label>
                      <input
                        name="contactLastName"
                        type="text"
                        required
                        maxLength={100}
                        value={form.contactLastName}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        className={`mt-1 ${inputCls}`}
                        placeholder={t("auth.register.contactLastNamePlaceholder")}
                        autoComplete="family-name"
                      />
                      {fieldErrors.contactLastName && (
                        <p className="mt-1 text-xs text-danger">{fieldErrors.contactLastName}</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.contactMobilePhone")}{" "}
                      <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="contactMobilePhone"
                      type="tel"
                      required
                      maxLength={15}
                      value={form.contactMobilePhone}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.contactMobilePhonePlaceholder")}
                      autoComplete="tel"
                      dir="ltr"
                    />
                    {fieldErrors.contactMobilePhone && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.contactMobilePhone}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.contactLandlinePhone")}
                    </label>
                    <input
                      name="contactLandlinePhone"
                      type="tel"
                      maxLength={15}
                      value={form.contactLandlinePhone}
                      onChange={handleChange}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.contactLandlinePhonePlaceholder")}
                      dir="ltr"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* ── Right panel: account + agreement + submit ── */}
            <div className="flex flex-col gap-5">
              {/* Account credentials */}
              <div className="rounded-xl border border-white/8 bg-card p-6">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                  {t("auth.register.accountSection")}
                </p>
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.emailLabel")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="email"
                      type="email"
                      required
                      maxLength={255}
                      value={form.email}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.emailPlaceholder")}
                      autoComplete="email"
                      dir="ltr"
                    />
                    {fieldErrors.email && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.email}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.passwordLabel")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="password"
                      type="password"
                      required
                      value={form.password}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.passwordPlaceholder")}
                      autoComplete="new-password"
                    />
                    {fieldErrors.password && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.password}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm text-white/50">
                      {t("auth.register.confirmLabel")} <span className="text-copper/80">*</span>
                    </label>
                    <input
                      name="confirm"
                      type="password"
                      required
                      value={form.confirm}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      className={`mt-1 ${inputCls}`}
                      placeholder={t("auth.register.confirmPlaceholder")}
                      autoComplete="new-password"
                    />
                    {fieldErrors.confirm && (
                      <p className="mt-1 text-xs text-danger">{fieldErrors.confirm}</p>
                    )}
                  </div>
                </div>
              </div>

              {/* Legal agreement + signature */}
              <div className="flex-1 rounded-xl border border-white/8 bg-card p-6">
                <div className="mb-4 flex items-center justify-between">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
                    {t("auth.register.agreementSection")}
                  </p>
                  <button
                    type="button"
                    onClick={() => setAgreementOpen(true)}
                    className="flex items-center gap-1 rounded-sm border border-white/15 px-2.5 py-1 text-[11px] text-white/50 transition hover:border-copper/40 hover:text-copper"
                  >
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4" />
                    </svg>
                    {t("auth.register.agreementReadFull")}
                  </button>
                </div>

                {/* Teaser — first ~3 lines of the service section */}
                <div className="mb-5 rounded-lg border border-white/6 bg-card-raised px-4 py-3">
                  <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-white/30">
                    {t("auth.register.agreementSectionService")}
                  </p>
                  <p className="line-clamp-3 text-xs leading-relaxed text-white/40">
                    {t("auth.register.agreementTextService")}
                  </p>
                  <p className="mt-2 mb-1 text-[10px] font-medium uppercase tracking-wider text-white/30">
                    {t("auth.register.agreementSectionPrivacy")}
                  </p>
                  <p className="line-clamp-2 text-xs leading-relaxed text-white/40">
                    {t("auth.register.agreementTextPrivacy")}
                  </p>
                  <button
                    type="button"
                    onClick={() => setAgreementOpen(true)}
                    className="mt-2 text-xs text-copper/70 transition hover:text-copper"
                  >
                    {t("auth.register.agreementReadFull")} ←
                  </button>
                </div>

                {/* Signature */}
                <p className="mb-1 text-[10px] font-medium text-white/35">
                  {t("auth.register.agreementSignLabel")}
                </p>
                <div className="mt-3">
                  <label className="block text-sm text-white/50">
                    {t("auth.register.signatureLabel")}{" "}
                    <span className="text-copper/80">*</span>
                  </label>
                  <p className="mb-2 mt-0.5 text-xs text-white/30">
                    {t("auth.register.signatureHint")}
                  </p>
                  <SignatureCanvas
                    ref={sigCanvasRef}
                    hasError={!!fieldErrors.signature}
                    onBegin={() => setFieldErrors((prev) => ({ ...prev, signature: "" }))}
                  />
                  {fieldErrors.signature && (
                    <p className="mt-1 text-xs text-danger">{fieldErrors.signature}</p>
                  )}
                </div>
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={submitting}
                className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
              >
                {submitting ? t("auth.register.submittingText") : t("auth.register.submitText")}
              </button>
            </div>
          </div>
        </form>

        <p className="mt-6 text-center text-sm text-white/35">
          {t("auth.register.haveAccount")}{" "}
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth.register.loginLink")}
          </Link>
        </p>
      </div>

      {/* Agreement full-screen modal */}
      {agreementOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-void/90 p-4 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setAgreementOpen(false); }}
        >
          <div className="flex max-h-[90vh] w-full max-w-2xl flex-col rounded-2xl border border-white/10 border-t-copper/40 bg-card shadow-2xl">
            {/* Modal header */}
            <div className="flex items-center justify-between border-b border-white/8 px-6 py-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
                  RS Recruiting
                </p>
                <h2 className="mt-0.5 text-base font-semibold text-white/90">
                  {t("auth.register.agreementModalTitle")}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setAgreementOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-full border border-white/15 text-white/50 transition hover:border-white/30 hover:text-white/80"
                aria-label={t("auth.register.agreementClose")}
              >
                ✕
              </button>
            </div>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin]">
              {/* Service agreement */}
              <section className="mb-6">
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-copper/80">
                  {t("auth.register.agreementSectionService")}
                </h3>
                <p className="text-sm leading-7 text-white/60">
                  {t("auth.register.agreementTextService")}
                </p>
              </section>

              <div className="my-5 border-t border-white/8" />

              {/* Privacy clause */}
              <section>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-widest text-copper/80">
                  {t("auth.register.agreementSectionPrivacy")}
                </h3>
                <div className="space-y-3 text-sm leading-7 text-white/60">
                  {t("auth.register.agreementTextPrivacy")
                    .split("\n\n")
                    .map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                </div>
              </section>
            </div>

            {/* Modal footer */}
            <div className="flex items-center justify-between border-t border-white/8 px-6 py-4">
              <p className="text-xs text-white/35">
                {t("auth.register.agreementSignLabel")}
              </p>
              <button
                type="button"
                onClick={() => setAgreementOpen(false)}
                className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
              >
                {t("auth.register.agreementClose")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
