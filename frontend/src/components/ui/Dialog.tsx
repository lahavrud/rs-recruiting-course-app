import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

type Size = "sm" | "md" | "lg";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  /** Footer slot — typically action buttons. */
  footer?: ReactNode;
  size?: Size;
}

const sizeCls: Record<Size, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
};

/**
 * Centered modal built on Radix Dialog. Inherits `dir="rtl"` from `<html>`,
 * traps focus, and closes on Escape / overlay click. Used for both the
 * `<ConfirmDialog>` and entity detail modals in the per-page polish PRs.
 */
export default function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  size = "md",
}: DialogProps) {
  const { t } = useTranslation();
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm" />
        <RadixDialog.Content
          // Suppress Radix's default auto-focus on the first focusable child.
          // It tends to land on a destructive button (delete) in detail
          // modals, which both reads as urgency and shows the red focus ring
          // immediately on open. Radix still focuses the Content wrapper for
          // screen readers; users tab from there.
          onOpenAutoFocus={(e) => e.preventDefault()}
          className={[
            "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2",
            "rounded-xl border border-white/8 bg-card-raised p-6 text-white/85 shadow-2xl shadow-black/60",
            "max-h-[calc(100vh-2rem)] overflow-y-auto",
            sizeCls[size],
          ].join(" ")}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <RadixDialog.Title className="font-display text-xl text-white">
                {title}
              </RadixDialog.Title>
              {description && (
                <RadixDialog.Description className="mt-1 text-sm text-white/60">
                  {description}
                </RadixDialog.Description>
              )}
            </div>
            <RadixDialog.Close
              aria-label={t("common.close")}
              className="shrink-0 rounded-sm p-1 text-white/30 transition hover:bg-white/8 hover:text-white/70 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white/30"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" className="size-4" aria-hidden="true">
                <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
              </svg>
            </RadixDialog.Close>
          </div>
          {children && <div className="mt-4">{children}</div>}
          {footer && (
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2 *:flex-1 *:whitespace-nowrap">{footer}</div>
          )}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
