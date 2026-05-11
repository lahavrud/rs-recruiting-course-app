import { type ChangeEvent, type FormEvent, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { useAuth } from "@/hooks/useAuth";
import { resetPassword } from "@/services/auth";
import Logo from "@/components/ui/Logo";
import { inputCls } from "@/styles/forms";

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState({ password: "", confirm: "" });
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [tokenRejected, setTokenRejected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  function validatePassword(v: string): string {
    if (!v) return t("auth.resetPassword.validation.passwordRequired");
    if (v.length < 8) return t("auth.resetPassword.validation.passwordMin");
    if (!/[A-Z]/.test(v)) return t("auth.resetPassword.validation.passwordUppercase");
    if (!/[a-z]/.test(v)) return t("auth.resetPassword.validation.passwordLowercase");
    if (!/\d/.test(v)) return t("auth.resetPassword.validation.passwordDigit");
    if (!/[^A-Za-z0-9]/.test(v))
      return t("auth.resetPassword.validation.passwordSpecial");
    return "";
  }

  function validateConfirm(v: string, pw: string): string {
    if (!v) return t("auth.resetPassword.validation.confirmRequired");
    if (v !== pw) return t("auth.resetPassword.validation.confirmMismatch");
    return "";
  }

  function handlePasswordChange(e: ChangeEvent<HTMLInputElement>) {
    setPassword(e.target.value);
    if (fieldErrors.password)
      setFieldErrors((prev) => ({ ...prev, password: "" }));
  }

  function handleConfirmChange(e: ChangeEvent<HTMLInputElement>) {
    setConfirm(e.target.value);
    if (fieldErrors.confirm)
      setFieldErrors((prev) => ({ ...prev, confirm: "" }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const errors = {
      password: validatePassword(password),
      confirm: validateConfirm(confirm, password),
    };
    setFieldErrors(errors);
    if (errors.password || errors.confirm) return;

    setSubmitting(true);
    setError(null);
    try {
      await resetPassword(token!, password);
      setSuccess(true);
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const status = err.response?.status;
        if (status === 400) setTokenRejected(true);
        else if (status === 429) setError(t("auth.resetPassword.errors.tooManyAttempts"));
        else if (status === 422) {
          const detail = err.response?.data?.detail;
          const errs = Array.isArray(detail) ? detail : [];
          const pwErr = errs.find((e: { loc?: string[] }) =>
            e.loc?.includes("new_password"),
          );
          if (pwErr)
            setFieldErrors((prev) => ({ ...prev, password: pwErr.msg }));
          else setError(t("auth.resetPassword.errors.failed"));
        } else setError(t("auth.resetPassword.errors.failed"));
      } else {
        setError(t("auth.resetPassword.errors.unexpected"));
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!token || tokenRejected) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
        <div className="w-full max-w-md rounded-xl border border-warning/30 bg-card p-10 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-lg text-warning">
            ✕
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth.resetPassword.invalidToken.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth.resetPassword.invalidToken.message")}
          </p>
          <Link
            to="/forgot-password"
            className="mt-7 inline-block rounded-sm border border-white/20 px-6 py-2.5 text-sm text-white/60 transition hover:border-white/40 hover:text-white/90"
          >
            {t("auth.resetPassword.invalidToken.requestNew")}
          </Link>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
        <div className="w-full max-w-md rounded-xl border border-success/20 bg-success/8 p-10 text-center">
          <div className="flex justify-center">
            <Logo size={32} />
          </div>
          <div className="mx-auto mt-6 flex h-12 w-12 items-center justify-center rounded-full border border-success/30 bg-success/10 text-lg text-success">
            ✓
          </div>
          <h2 className="mt-5 text-lg font-semibold text-white/90">
            {t("auth.resetPassword.success.title")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-white/50">
            {t("auth.resetPassword.success.message")}
          </p>
          <Link
            to="/login"
            className="mt-7 inline-block rounded-sm bg-copper px-6 py-2.5 text-sm font-medium text-white transition hover:bg-gold"
          >
            {t("auth.resetPassword.success.loginButton")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-void px-4 py-8">
      <div className="w-full max-w-sm space-y-8 rounded-xl border border-white/10 border-t-copper/50 bg-card sm:max-w-md">
        <div className="px-6 pt-8 text-center sm:px-8">
          <div className="flex justify-center">
            <Logo size={36} />
          </div>
          <h1 className="mt-4 text-lg font-semibold text-white/85">
            {t("auth.resetPassword.title")}
          </h1>
          <p className="mt-2 text-sm text-white/45">
            {t("auth.resetPassword.subtitle")}
          </p>
        </div>

        <form className="space-y-5 px-6 sm:px-8" onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="rounded-lg border border-danger/20 bg-danger/10 p-3 text-sm text-danger">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="password" className="block text-sm text-white/50">
              {t("auth.resetPassword.passwordLabel")}
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              value={password}
              onChange={handlePasswordChange}
              onBlur={(e) =>
                setFieldErrors((prev) => ({
                  ...prev,
                  password: validatePassword(e.target.value),
                }))
              }
              className={`mt-1 ${inputCls}`}
              autoComplete="new-password"
            />
            {fieldErrors.password && (
              <p className="mt-1 text-xs text-danger">{fieldErrors.password}</p>
            )}
          </div>

          <div>
            <label htmlFor="confirm" className="block text-sm text-white/50">
              {t("auth.resetPassword.confirmLabel")}
            </label>
            <input
              id="confirm"
              name="confirm"
              type="password"
              required
              value={confirm}
              onChange={handleConfirmChange}
              onBlur={(e) =>
                setFieldErrors((prev) => ({
                  ...prev,
                  confirm: validateConfirm(e.target.value, password),
                }))
              }
              className={`mt-1 ${inputCls}`}
              autoComplete="new-password"
            />
            {fieldErrors.confirm && (
              <p className="mt-1 text-xs text-danger">{fieldErrors.confirm}</p>
            )}
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-sm bg-copper px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gold focus:outline-none disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting
              ? t("auth.resetPassword.submittingText")
              : t("auth.resetPassword.submitText")}
          </button>
        </form>

        <p className="px-6 pb-8 text-center text-sm text-white/35 sm:px-8">
          <Link to="/login" className="text-copper transition hover:text-gold">
            {t("auth.resetPassword.backToLogin")}
          </Link>
        </p>
      </div>
    </div>
  );
}
