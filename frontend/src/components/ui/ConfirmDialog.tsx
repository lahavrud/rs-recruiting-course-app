import { useTranslation } from "react-i18next";
import Dialog from "./Dialog";

interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "primary" | "danger";
  onConfirm: () => void | Promise<void>;
  isPending?: boolean;
}

/**
 * Confirmation modal that replaces `window.confirm(...)`. The confirm
 * action can be sync or async; `isPending` lets the caller disable the
 * button while a request is in flight.
 */
export default function ConfirmDialog({
  open,
  onOpenChange,
  title,
  message,
  confirmLabel,
  cancelLabel,
  variant = "primary",
  onConfirm,
  isPending = false,
}: ConfirmDialogProps) {
  const { t } = useTranslation();
  const confirmText = confirmLabel ?? t("common.confirm");
  const cancelText = cancelLabel ?? t("common.cancel");

  const confirmCls =
    variant === "danger"
      ? "rounded-sm bg-danger px-4 py-2 text-sm font-medium text-white hover:brightness-110 disabled:opacity-60"
      : "rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60";

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={message}
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/60 hover:border-white/40 hover:text-white/90"
            disabled={isPending}
          >
            {cancelText}
          </button>
          <button
            type="button"
            onClick={() => void onConfirm()}
            className={confirmCls}
            disabled={isPending}
          >
            {isPending ? t("common.loading") : confirmText}
          </button>
        </>
      }
    />
  );
}
