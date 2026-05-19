import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getInviteMetadata, register } from "@/services/auth";
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
    validateAddress(v: string): string {
      if (!v.trim()) return t("auth.register.validation.addressRequired");
      if (v.length > 200) return t("auth.register.validation.addressMax");
      return "";
    },
    validatePrivacy(accepted: boolean): string {
      if (!accepted) return t("auth.register.validation.privacyRequired");
      return "";
    },
    validateTerms(accepted: boolean): string {
      if (!accepted) return t("auth.register.validation.termsRequired");
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
  address: string;
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
  address: "",
  contactFirstName: "",
  contactLastName: "",
  contactMobilePhone: "",
  contactLandlinePhone: "",
};

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs text-white/45">{label}</label>
      {children}
      {error && <p className="mt-1 text-xs text-danger">{error}</p>}
    </div>
  );
}

export default function RegisterPage() {
  const { t } = useTranslation();
  const val = useValidation();
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("token");

  const [step, setStep] = useState<1 | 2>(1);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [privacyAccepted, setPrivacyAccepted] = useState(false);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<
    Partial<
      FormState & {
        logo: string;
        signature: string;
        privacy: string;
        terms: string;
      }
    >
  >({});
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(() => !!inviteToken);
  const [tokenInvalid, setTokenInvalid] = useState(false);
  const [emailPreFilled, setEmailPreFilled] = useState(false);
  const logoInputRef = useRef<HTMLInputElement>(null);
  const sigCanvasRef = useRef<SignatureCanvasRef>(null);

  useEffect(() => {
    if (!inviteToken) return;
    getInviteMetadata(inviteToken)
      .then((meta) => {
        setForm((prev) => ({ ...prev, email: meta.email ?? prev.email }));
        if (meta.email) setEmailPreFilled(true);
      })
      .catch(() => setTokenInvalid(true))
      .finally(() => setMetadataLoading(false));
  }, [inviteToken]);

  useEffect(() => {
    if (contractOpen || termsOpen || privacyOpen)
      document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [contractOpen, termsOpen, privacyOpen]);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  if (!inviteToken || tokenInvalid) {
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

  if (metadataLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void">
        <p className="text-sm text-white/30">{t("common.loading")}</p>
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
    let err = "";
    switch (name as keyof FormState) {
      case "email": err = val.validateEmail(value); break;
      case "password": err = val.validatePassword(value); break;
      case "confirm": err = val.validateConfirm(value, form.password); break;
      case "companyName": err = val.validateCompanyName(value); break;
      case "companyId": err = val.validateCompanyId(value); break;
      case "address": err = val.validateAddress(value); break;
      case "contactFirstName": err = val.validateContactFirstName(value); break;
      case "contactLastName": err = val.validateContactLastName(value); break;
      case "contactMobilePhone": err = val.validateMobilePhone(value); break;
    }
    setFieldErrors((prev) => ({ ...prev, [name]: err }));
  }

  function handleLogoChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setLogoFile(file);
    if (file) setFieldErrors((prev) => ({ ...prev, logo: "" }));
  }

  function validateStep1(): boolean {
    const errors: Partial<FormState & { logo: string }> = {
      companyName: val.validateCompanyName(form.companyName),
      companyId: val.validateCompanyId(form.companyId),
      address: val.validateAddress(form.address),
      contactFirstName: val.validateContactFirstName(form.contactFirstName),
      contactLastName: val.validateContactLastName(form.contactLastName),
      contactMobilePhone: val.validateMobilePhone(form.contactMobilePhone),
      email: val.validateEmail(form.email),
      password: val.validatePassword(form.password),
      confirm: val.validateConfirm(form.confirm, form.password),
      logo: val.validateLogo(logoFile),
    };
    setFieldErrors(errors);
    return Object.values(errors).every((e) => !e);
  }

  function validateStep2(): boolean {
    const errors = {
      signature: val.validateSignature(sigCanvasRef.current?.isEmpty() ?? true),
      terms: val.validateTerms(termsAccepted),
      privacy: val.validatePrivacy(privacyAccepted),
    };
    setFieldErrors((prev) => ({ ...prev, ...errors }));
    return Object.values(errors).every((e) => !e);
  }

  function handleNext() {
    if (validateStep1()) {
      setSubmitError(null);
      setStep(2);
      window.scrollTo(0, 0);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validateStep2()) return;

    const dataUrl = sigCanvasRef.current!.toDataURL();
    const sigBase64 = dataUrl.split(",")[1] ?? "";

    const fd = new FormData();
    fd.append("email", form.email.trim());
    fd.append("password", form.password);
    fd.append("company_name", form.companyName.trim());
    fd.append("company_id", form.companyId.trim());
    fd.append("address", form.address.trim());
    fd.append("contact_first_name", form.contactFirstName.trim());
    fd.append("contact_last_name", form.contactLastName.trim());
    fd.append("contact_mobile_phone", form.contactMobilePhone.trim());
    if (form.contactLandlinePhone.trim())
      fd.append("contact_landline_phone", form.contactLandlinePhone.trim());
    fd.append("agreement_signature", sigBase64);
    fd.append("privacy_accepted", String(privacyAccepted));
    fd.append("terms_accepted", String(termsAccepted));
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
          const detail = err.response?.data?.detail;
          const errors = Array.isArray(detail) ? detail : [];
          const pwErr = errors.find((e: { loc?: string[] }) => e.loc?.includes("password"));
          if (pwErr) setFieldErrors((prev) => ({ ...prev, password: pwErr.msg }));
          else setSubmitError(t("auth.register.errors.failed"));
        } else if (status === 429) {
          setSubmitError(t("auth.register.errors.tooManyAttempts"));
        } else if (status === 400) {
          setSubmitError(t("auth.register.errors.invalidToken"));
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
    <div className="min-h-screen bg-void px-4 py-10">
      <div className="mx-auto max-w-xl">

        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Logo size={28} />
          <div>
            <h1 className="text-lg font-semibold text-white/85">{t("auth.register.title")}</h1>
            <p className="text-xs text-white/35">{t("auth.register.subtitle")}</p>
          </div>
        </div>

        {/* Step indicator */}
        <div className="mb-6 flex items-center gap-2">
          <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${step === 1 ? "bg-copper text-white" : "bg-copper/20 text-copper"}`}>
            {step === 2 ? "✓" : "1"}
          </div>
          <div className="h-px flex-1 bg-white/10" />
          <div className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${step === 2 ? "bg-copper text-white" : "bg-white/8 text-white/25"}`}>
            2
          </div>
        </div>

        {submitError && (
          <div className="mb-5 rounded-lg border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
            {submitError}
          </div>
        )}

        {/* ── STEP 1: Details ── */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                {t("auth.register.companySection")}
              </p>
              <div className="space-y-3">
                <Field label={`${t("auth.register.companyName")} *`} error={fieldErrors.companyName}>
                  <input
                    name="companyName" type="text" required maxLength={100}
                    value={form.companyName} onChange={handleChange} onBlur={handleBlur}
                    className={inputCls} placeholder="Acme בע״מ"
                    autoComplete="organization"
                  />
                </Field>

                <div className="grid grid-cols-2 gap-3">
                  <Field label={`${t("auth.register.companyIdLabel")} *`} error={fieldErrors.companyId}>
                    <input
                      name="companyId" type="text" required maxLength={9}
                      value={form.companyId} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder="123456789" dir="ltr"
                    />
                  </Field>
                  <Field label={`${t("auth.register.addressLabel")} *`} error={fieldErrors.address}>
                    <input
                      name="address" type="text" required maxLength={200}
                      value={form.address} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder={t("auth.register.addressPlaceholder")}
                      autoComplete="street-address"
                    />
                  </Field>
                </div>

                <Field label={`${t("auth.register.logoLabel")} *`} error={fieldErrors.logo}>
                  <input
                    ref={logoInputRef} type="file" accept="image/*"
                    onChange={handleLogoChange}
                    className="mt-0.5 block w-full cursor-pointer rounded-sm border border-white/10 bg-well px-3 py-2 text-xs text-white/50 file:ml-3 file:rounded-sm file:border-0 file:bg-copper/20 file:px-2.5 file:py-1 file:text-[11px] file:font-medium file:text-copper hover:file:bg-copper/30"
                  />
                </Field>
              </div>
            </div>

            <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                {t("auth.register.contactSection", "איש קשר")}
              </p>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <Field label={`${t("auth.register.contactFirstName")} *`} error={fieldErrors.contactFirstName}>
                    <input
                      name="contactFirstName" type="text" required maxLength={100}
                      value={form.contactFirstName} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder={t("auth.register.contactFirstNamePlaceholder")}
                      autoComplete="given-name"
                    />
                  </Field>
                  <Field label={`${t("auth.register.contactLastName")} *`} error={fieldErrors.contactLastName}>
                    <input
                      name="contactLastName" type="text" required maxLength={100}
                      value={form.contactLastName} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder={t("auth.register.contactLastNamePlaceholder")}
                      autoComplete="family-name"
                    />
                  </Field>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <Field label={`${t("auth.register.contactMobilePhone")} *`} error={fieldErrors.contactMobilePhone}>
                    <input
                      name="contactMobilePhone" type="tel" required maxLength={15}
                      value={form.contactMobilePhone} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder={t("auth.register.contactMobilePhonePlaceholder")}
                      autoComplete="tel" dir="ltr"
                    />
                  </Field>
                  <Field label={t("auth.register.contactLandlinePhone")}>
                    <input
                      name="contactLandlinePhone" type="tel" maxLength={15}
                      value={form.contactLandlinePhone} onChange={handleChange}
                      className={inputCls} placeholder={t("auth.register.contactLandlinePhonePlaceholder")}
                      dir="ltr"
                    />
                  </Field>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-white/8 bg-card px-5 py-5">
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-widest text-copper">
                {t("auth.register.accountSection")}
              </p>
              <div className="space-y-3">
                <Field label={`${t("auth.register.emailLabel")} *`} error={fieldErrors.email}>
                  <input
                    name="email" type="email" required maxLength={255}
                    value={form.email} onChange={handleChange} onBlur={handleBlur}
                    readOnly={emailPreFilled}
                    className={`${inputCls} ${emailPreFilled ? "cursor-not-allowed opacity-60" : ""}`}
                    placeholder={t("auth.register.emailPlaceholder")}
                    autoComplete="email" dir="ltr"
                  />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label={`${t("auth.register.passwordLabel")} *`} error={fieldErrors.password}>
                    <input
                      name="password" type="password" required
                      value={form.password} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder="••••••••"
                      autoComplete="new-password"
                    />
                  </Field>
                  <Field label={`${t("auth.register.confirmLabel")} *`} error={fieldErrors.confirm}>
                    <input
                      name="confirm" type="password" required
                      value={form.confirm} onChange={handleChange} onBlur={handleBlur}
                      className={inputCls} placeholder="••••••••"
                      autoComplete="new-password"
                    />
                  </Field>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={handleNext}
              className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold"
            >
              {t("auth.register.nextStep")} ←
            </button>
          </div>
        )}

        {/* ── STEP 2: Legal ── */}
        {step === 2 && (
          <form onSubmit={handleSubmit} noValidate>
            <div className="space-y-4">
              <div className="rounded-xl border border-white/8 bg-card px-5 py-5 space-y-3">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
                  {t("auth.register.agreementSection")}
                </p>

                {/* Contract */}
                <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-white/60">
                      {t("auth.register.agreementSectionService")}
                    </p>
                    <button
                      type="button" onClick={() => setContractOpen(true)}
                      className="text-[11px] text-copper/70 transition hover:text-copper"
                    >
                      {t("auth.register.agreementReadFull")}
                    </button>
                  </div>
                  <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
                    <p className="text-xs leading-relaxed text-white/30">
                      {t("auth.register.agreementTextService")}
                    </p>
                  </div>
                </div>

                {/* Site Terms of Service */}
                <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-white/60">
                      {t("auth.register.agreementSectionSiteTerms")}
                    </p>
                    <button
                      type="button" onClick={() => setTermsOpen(true)}
                      className="text-[11px] text-copper/70 transition hover:text-copper"
                    >
                      {t("auth.register.agreementReadFull")}
                    </button>
                  </div>
                  <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
                    <p className="text-xs leading-relaxed text-white/30">
                      {t("auth.register.agreementTextSiteTermsPreview")}
                    </p>
                  </div>
                  <label className="mt-3 flex cursor-pointer items-center gap-2.5 text-sm text-white/60">
                    <input
                      type="checkbox"
                      checked={termsAccepted}
                      onChange={(e) => {
                        setTermsAccepted(e.target.checked);
                        if (e.target.checked)
                          setFieldErrors((prev) => ({ ...prev, terms: "" }));
                      }}
                      className="accent-copper"
                    />
                    {t("auth.register.termsCheckboxLabel")}
                  </label>
                  {fieldErrors.terms && (
                    <p className="mt-1 text-xs text-danger">{fieldErrors.terms}</p>
                  )}
                </div>

                {/* Privacy */}
                <div className="rounded-lg border border-white/6 bg-card-raised px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-medium text-white/60">
                      {t("auth.register.agreementSectionPrivacy")}
                    </p>
                    <button
                      type="button" onClick={() => setPrivacyOpen(true)}
                      className="text-[11px] text-copper/70 transition hover:text-copper"
                    >
                      {t("auth.register.agreementReadFull")}
                    </button>
                  </div>
                  <div className="mt-2 max-h-20 overflow-y-auto [scrollbar-width:thin]">
                    <p className="text-xs leading-relaxed text-white/30">
                      {t("auth.register.agreementTextPrivacyPreview")}
                    </p>
                  </div>
                  <label className="mt-3 flex cursor-pointer items-center gap-2.5 text-sm text-white/60">
                    <input
                      type="checkbox"
                      checked={privacyAccepted}
                      onChange={(e) => {
                        setPrivacyAccepted(e.target.checked);
                        if (e.target.checked)
                          setFieldErrors((prev) => ({ ...prev, privacy: "" }));
                      }}
                      className="accent-copper"
                    />
                    {t("auth.register.privacyCheckboxLabel")}
                  </label>
                  {fieldErrors.privacy && (
                    <p className="mt-1 text-xs text-danger">{fieldErrors.privacy}</p>
                  )}
                </div>

                {/* Signature */}
                <div>
                  <p className="mb-2 text-xs text-white/45">
                    {t("auth.register.signatureLabel")} <span className="text-copper/60">*</span>
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

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => { setStep(1); setSubmitError(null); }}
                  className="flex-1 rounded-sm border border-white/15 px-4 py-2.5 text-sm text-white/55 transition hover:border-white/30 hover:text-white/80"
                >
                  → {t("auth.register.backStep")}
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-[2] rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {submitting ? t("auth.register.submittingText") : t("auth.register.submitText")}
                </button>
              </div>
            </div>
          </form>
        )}

        <p className="mt-6 text-center text-xs text-white/30">
          {t("auth.register.haveAccount")}{" "}
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth.register.loginLink")}
          </Link>
        </p>
      </div>

      {/* Contract modal */}
      {contractOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setContractOpen(false); }}
        >
          <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
              <h2 className="text-sm font-medium text-white/80">
                {t("auth.register.agreementSectionService")}
              </h2>
              <button
                type="button" onClick={() => setContractOpen(false)}
                className="text-white/40 transition hover:text-white/70"
                aria-label={t("auth.register.agreementClose")}
              >✕</button>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
              {t("auth.register.agreementTextService")
                .split("\n\n")
                .map((para, i) => (
                  <p key={i} className="text-sm leading-7 text-white/55">{para}</p>
                ))}
            </div>
            <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">
              <button
                type="button" onClick={() => setContractOpen(false)}
                className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
              >
                {t("auth.register.agreementClose")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Site Terms modal */}
      {termsOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setTermsOpen(false); }}
        >
          <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
              <h2 className="text-sm font-medium text-white/80">
                {t("auth.register.agreementSectionSiteTerms")}
              </h2>
              <button
                type="button" onClick={() => setTermsOpen(false)}
                className="text-white/40 transition hover:text-white/70"
                aria-label={t("auth.register.agreementClose")}
              >✕</button>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
              {t("auth.register.agreementTextSiteTerms")
                .split("\n\n")
                .map((para, i) => (
                  <p key={i} className="text-sm leading-7 text-white/55">{para}</p>
                ))}
            </div>
            <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">
              <button
                type="button"
                onClick={() => {
                  setTermsAccepted(true);
                  setFieldErrors((prev) => ({ ...prev, terms: "" }));
                  setTermsOpen(false);
                }}
                className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
              >
                {t("auth.register.termsAcceptButton")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Privacy modal */}
      {privacyOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={(e) => { if (e.target === e.currentTarget) setPrivacyOpen(false); }}
        >
          <div className="flex max-h-[88vh] w-full max-w-xl flex-col rounded-xl border border-white/10 bg-card shadow-2xl">
            <div className="flex shrink-0 items-center justify-between border-b border-white/8 px-5 py-3.5">
              <h2 className="text-sm font-medium text-white/80">
                {t("auth.register.agreementSectionPrivacy")}
              </h2>
              <button
                type="button" onClick={() => setPrivacyOpen(false)}
                className="text-white/40 transition hover:text-white/70"
                aria-label={t("auth.register.agreementClose")}
              >✕</button>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4 [scrollbar-width:thin]">
              {t("auth.register.agreementTextPrivacy")
                .split("\n\n")
                .map((para, i) => (
                  <p key={i} className="text-sm leading-7 text-white/55">{para}</p>
                ))}
            </div>
            <div className="shrink-0 border-t border-white/8 px-5 py-3 text-left">
              <button
                type="button"
                onClick={() => {
                  setPrivacyAccepted(true);
                  setFieldErrors((prev) => ({ ...prev, privacy: "" }));
                  setPrivacyOpen(false);
                }}
                className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold"
              >
                {t("auth.register.privacyAcceptButton")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
