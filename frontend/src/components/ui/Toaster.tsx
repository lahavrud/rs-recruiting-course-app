import { useToast } from "@/hooks/useToast";

const variantCls: Record<string, string> = {
  success: "border-success/40 bg-card-raised text-success",
  error: "border-danger/40 bg-card-raised text-danger",
  info: "border-white/15 bg-card-raised text-white/85",
};

/**
 * Bottom-start positioned toast viewport. Mounts inside `<ToastProvider>`
 * via `<AppShell>`. Direction-aware: `inset-inline-start` resolves to the
 * physical right in our forced-RTL document, which reads naturally there.
 */
export default function Toaster() {
  const { toasts, dismiss } = useToast();
  if (toasts.length === 0) return null;

  return (
    <div
      role="region"
      aria-label="התראות"
      className="pointer-events-none fixed bottom-6 inset-inline-start-6 z-50 flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => dismiss(t.id)}
          aria-live={t.variant === "error" ? "assertive" : "polite"}
          className={[
            "pointer-events-auto max-w-sm rounded-md border px-4 py-3 text-sm font-medium",
            "shadow-lg shadow-black/40 transition hover:brightness-110",
            "text-start",
            variantCls[t.variant] ?? variantCls.info,
          ].join(" ")}
        >
          {t.message}
        </button>
      ))}
    </div>
  );
}
