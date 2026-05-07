import { useTranslation } from "react-i18next";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

/**
 * Error placeholder with optional retry button. Falls back to a generic
 * Hebrew message when the caller doesn't pass a specific one.
 */
export default function ErrorState({
  message,
  onRetry,
  className = "",
}: ErrorStateProps) {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className={`flex flex-col items-center justify-center rounded-xl border border-danger/30 bg-card px-6 py-16 text-center ${className}`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-widest text-danger">
        {t("common.errorEyebrow")}
      </p>
      <div className="mt-3 h-px w-8 bg-danger/40" />
      <p className="mt-5 max-w-md text-sm text-white/70">
        {message ?? t("common.genericError")}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-6 rounded-sm border border-white/20 px-4 py-2 text-sm text-white/70 hover:border-white/40 hover:text-white/90"
        >
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}
