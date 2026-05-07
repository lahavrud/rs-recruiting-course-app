interface TableSkeletonProps {
  rows?: number;
  columns?: number;
  className?: string;
}

/**
 * Pulse-row placeholder for list pages, matched to the visual rhythm of
 * the row layout — no spinner. Caller passes `rows` to roughly match the
 * height of a fully populated viewport.
 */
export default function TableSkeleton({
  rows = 6,
  columns = 4,
  className = "",
}: TableSkeletonProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="טוען"
      className={`overflow-hidden rounded-xl border border-white/8 bg-card ${className}`}
    >
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div
          key={rowIdx}
          className={[
            "flex items-center gap-4 px-6 py-4",
            rowIdx > 0 ? "border-t border-white/5" : "",
          ].join(" ")}
        >
          {Array.from({ length: columns }).map((__, colIdx) => (
            <div
              key={colIdx}
              className="h-3 flex-1 animate-pulse rounded-sm bg-white/5"
              style={{ animationDelay: `${(rowIdx * columns + colIdx) * 30}ms` }}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
