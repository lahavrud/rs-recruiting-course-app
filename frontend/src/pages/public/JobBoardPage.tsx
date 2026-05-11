import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJobs } from "@/services/jobs";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import SearchInput from "@/components/ui/SearchInput";
import RangeSlider from "@/components/ui/RangeSlider";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import type { JobPublicRead } from "@/types/api";

const SALARY_STEP = 500;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatSalaryShort(n: number): string {
  return `${n.toLocaleString("he-IL")} ₪`;
}

/** Compact card-style salary: "12,000–15,000 ₪", "מ-12,000 ₪", or "עד 15,000 ₪". */
function formatCardSalary(min: number | null, max: number | null): string | null {
  if (min == null && max == null) return null;
  const fmt = (n: number) => n.toLocaleString("he-IL");
  if (min != null && max != null) return `${fmt(min)}–${fmt(max)} ₪`;
  if (min != null) return `מ-${fmt(min)} ₪`;
  return `עד ${fmt(max!)} ₪`;
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "…";
}

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-copper/35 bg-copper/12 py-1 ps-3 pe-1 text-xs font-medium text-copper">
      <span className="max-w-[14rem] truncate">{label}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`${t("common.clear")} ${label}`}
        className="inline-flex size-5 shrink-0 items-center justify-center rounded-full text-copper/80 transition hover:bg-copper/20 hover:text-copper"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className="size-3"
          aria-hidden="true"
        >
          <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06L6.94 8l-4.72 4.72a.75.75 0 1 0 1.06 1.06L8 9.06l4.72 4.72a.75.75 0 1 0 1.06-1.06L9.06 8l4.72-4.72a.75.75 0 0 0-1.06-1.06L8 6.94 3.28 2.22Z" />
        </svg>
      </button>
    </span>
  );
}

function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-white/5 bg-card p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-white/8" />
          <div className="h-3 w-1/3 rounded bg-white/5" />
        </div>
        <div className="h-5 w-12 shrink-0 rounded-full bg-white/5" />
      </div>
      <div className="mt-4 space-y-2">
        <div className="h-3 rounded bg-white/5" />
        <div className="h-3 w-5/6 rounded bg-white/5" />
        <div className="h-3 w-4/6 rounded bg-white/5" />
      </div>
      <div className="mt-5 h-3 w-1/4 rounded bg-white/4" />
    </div>
  );
}

interface SalaryBounds {
  min: number;
  max: number;
}

const SALARY_FALLBACK: SalaryBounds = { min: 0, max: 50000 };

function getSalaryBounds(jobs: JobPublicRead[]): SalaryBounds {
  let lo = Infinity;
  let hi = -Infinity;
  for (const j of jobs) {
    if (j.salary_min != null) lo = Math.min(lo, j.salary_min);
    if (j.salary_max != null) hi = Math.max(hi, j.salary_max);
  }
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi) {
    return SALARY_FALLBACK;
  }
  return {
    min: Math.floor(lo / SALARY_STEP) * SALARY_STEP,
    max: Math.ceil(hi / SALARY_STEP) * SALARY_STEP,
  };
}

interface FilterPanelProps {
  /** When true, render a search input at the top of the panel. */
  showSearch?: boolean;
  query: string;
  onQueryChange: (q: string) => void;
  locations: string[];
  selectedLocation: string | null;
  onLocationChange: (loc: string | null) => void;
  salaryBounds: SalaryBounds;
  salaryRange: [number, number];
  onSalaryChange: (range: [number, number]) => void;
  isSalaryActive: boolean;
  onResetSalary: () => void;
  hasActiveFilter: boolean;
  onClearAll: () => void;
}

function FilterPanel({
  showSearch = false,
  query,
  onQueryChange,
  locations,
  selectedLocation,
  onLocationChange,
  salaryBounds,
  salaryRange,
  onSalaryChange,
  isSalaryActive,
  onResetSalary,
  hasActiveFilter,
  onClearAll,
}: FilterPanelProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      {showSearch && (
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("common.search")}
          </p>
          <SearchInput
            value={query}
            onChange={onQueryChange}
            placeholder={t("publicJobs.board.searchPlaceholder")}
            disableShortcut
            clearable
          />
        </div>
      )}

      {locations.length >= 2 && (
        <div>
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("publicJobs.board.locationLabel")}
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => onLocationChange(null)}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition",
                !selectedLocation
                  ? "bg-copper text-white"
                  : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
              ].join(" ")}
            >
              {t("publicJobs.board.allLocations")}
            </button>
            {locations.map((loc) => (
              <button
                key={loc}
                type="button"
                onClick={() =>
                  onLocationChange(selectedLocation === loc ? null : loc)
                }
                className={[
                  "rounded-full px-3 py-1.5 text-xs font-medium transition",
                  selectedLocation === loc
                    ? "bg-copper text-white"
                    : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
                ].join(" ")}
              >
                {loc}
              </button>
            ))}
          </div>
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-copper">
            {t("publicJobs.board.salaryRange")}
          </p>
          {isSalaryActive && (
            <button
              type="button"
              onClick={onResetSalary}
              className="text-[11px] text-copper/70 transition hover:text-copper"
            >
              {t("publicJobs.board.resetSalary")}
            </button>
          )}
        </div>
        <RangeSlider
          min={salaryBounds.min}
          max={salaryBounds.max}
          step={SALARY_STEP}
          value={salaryRange}
          onChange={onSalaryChange}
          formatValue={formatSalaryShort}
          ariaLabelMin={t("publicJobs.board.salaryMinAria")}
          ariaLabelMax={t("publicJobs.board.salaryMaxAria")}
        />
      </div>

      {hasActiveFilter && (
        <button
          type="button"
          onClick={onClearAll}
          className="w-full rounded-sm border border-white/15 px-3 py-2 text-xs font-medium text-white/65 transition hover:border-copper/50 hover:text-copper"
        >
          {t("publicJobs.board.clearFilters")}
        </button>
      )}
    </div>
  );
}

export default function JobBoardPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const [drawerOpen, setDrawerOpen] = useState(false);

  const fetcher = useCallback((cursor: string | null) => getPublicJobs(cursor), []);
  const {
    items: jobs,
    isLoading: loading,
    error: fetchError,
    sentinelRef,
  } = useInfiniteList<JobPublicRead>(fetcher);

  const initialQuery = searchParams.get("q") ?? "";
  const initialLocation = searchParams.get("loc");
  const initialSmin = searchParams.get("smin");
  const initialSmax = searchParams.get("smax");

  const [query, setQuery] = useState(initialQuery);
  const [selectedLocation, setSelectedLocation] = useState<string | null>(initialLocation);
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(() => {
    const lo = initialSmin ? Number(initialSmin) : null;
    const hi = initialSmax ? Number(initialSmax) : null;
    if (lo == null || hi == null || !Number.isFinite(lo) || !Number.isFinite(hi)) return null;
    return [lo, hi];
  });

  // Lock body scroll while the mobile filter drawer is open.
  useEffect(() => {
    if (!drawerOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [drawerOpen]);

  const onSearch = useCallback((v: string) => setQuery(v), []);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) {
      if (j.location) seen.add(j.location);
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const salaryBounds = useMemo(() => getSalaryBounds(jobs), [jobs]);

  // Derive the clamped range without storing it — avoids setState-in-effect.
  const effectiveSalaryRange = useMemo<[number, number]>(() => {
    if (!salaryRange) return [salaryBounds.min, salaryBounds.max];
    return [
      Math.max(salaryBounds.min, Math.min(salaryRange[0], salaryBounds.max)),
      Math.max(salaryBounds.min, Math.min(salaryRange[1], salaryBounds.max)),
    ];
  }, [salaryRange, salaryBounds]);

  const isSalaryActive =
    effectiveSalaryRange[0] !== salaryBounds.min ||
    effectiveSalaryRange[1] !== salaryBounds.max;

  // Sync filter state -> URL search params.
  useEffect(() => {
    const next = new URLSearchParams(searchParams);
    const setOrDelete = (key: string, val: string | null) => {
      if (val) next.set(key, val);
      else next.delete(key);
    };
    setOrDelete("q", query.trim() || null);
    setOrDelete("loc", selectedLocation);
    if (isSalaryActive) {
      setOrDelete("smin", String(effectiveSalaryRange[0]));
      setOrDelete("smax", String(effectiveSalaryRange[1]));
    } else {
      next.delete("smin");
      next.delete("smax");
    }
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, selectedLocation, effectiveSalaryRange, isSalaryActive]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((j) => {
      const matchesQuery =
        !q ||
        [j.title, j.location, j.description, j.requirements].some((s) =>
          s.toLowerCase().includes(q),
        );
      const matchesLocation = !selectedLocation || j.location === selectedLocation;

      let matchesSalary = true;
      if (isSalaryActive) {
        const [filterLo, filterHi] = effectiveSalaryRange;
        // Jobs without salary listed: always show.
        if (j.salary_min != null || j.salary_max != null) {
          const jobLo = j.salary_min ?? j.salary_max ?? 0;
          const jobHi = j.salary_max ?? j.salary_min ?? Number.POSITIVE_INFINITY;
          matchesSalary = jobHi >= filterLo && jobLo <= filterHi;
        }
      }

      return matchesQuery && matchesLocation && matchesSalary;
    });
  }, [jobs, query, selectedLocation, effectiveSalaryRange, isSalaryActive]);

  const activeFilterCount =
    (query.trim() ? 1 : 0) + (selectedLocation ? 1 : 0) + (isSalaryActive ? 1 : 0);
  const hasActiveFilter = activeFilterCount > 0;

  const handleSalaryChange = useCallback((next: [number, number]) => {
    setSalaryRange(next);
  }, []);

  const handleResetSalary = useCallback(() => {
    setSalaryRange([salaryBounds.min, salaryBounds.max]);
  }, [salaryBounds]);

  const clearFilters = useCallback(() => {
    setQuery("");
    setSelectedLocation(null);
    setSalaryRange(null);
  }, []);

  if (fetchError) {
    return (
      <div className="rounded-lg border border-danger/20 bg-danger/10 p-6 text-center text-sm text-danger">
        {t("publicJobs.board.errorLoad")}
      </div>
    );
  }

  const baseFilterPanelProps = {
    query,
    onQueryChange: setQuery,
    locations: uniqueLocations,
    selectedLocation,
    onLocationChange: setSelectedLocation,
    salaryBounds,
    salaryRange: effectiveSalaryRange,
    onSalaryChange: handleSalaryChange,
    isSalaryActive,
    onResetSalary: handleResetSalary,
    hasActiveFilter,
    onClearAll: clearFilters,
  } as const;

  const showFilters = !loading && jobs.length > 0;

  return (
    <div>
      <SeoHead
        title={t("publicJobs.board.title")}
        description={t("publicJobs.board.subtitle")}
        canonical={`${SITE_URL}/jobs`}
      />
      {/* Header */}
      <div className="mb-6 sm:mb-10">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          RS Recruiting
        </p>
        <div className="mt-3 h-px w-8 bg-copper/40" />
        <h1 className="mt-4 text-2xl font-semibold text-white/90 sm:mt-5 sm:text-3xl">
          {t("publicJobs.board.title")}
        </h1>
        <p className="mt-2 text-sm text-white/45">
          {t("publicJobs.board.subtitle")}
        </p>
      </div>

      <div className={showFilters ? "lg:grid lg:grid-cols-[240px_1fr] lg:gap-8" : ""}>
        {/* Filter sidebar (desktop only) */}
        {showFilters && (
          <aside className="hidden lg:sticky lg:top-6 lg:block lg:self-start">
            <div className="rounded-xl border border-white/8 bg-card-raised/40 p-5">
              <p className="mb-4 text-sm font-medium text-white/85">
                {t("publicJobs.board.filters")}
              </p>
              <FilterPanel {...baseFilterPanelProps} />
            </div>
          </aside>
        )}

        {/* Results column */}
        <div className="min-w-0">
          {/* Search + mobile filter trigger */}
          {!loading && jobs.length > 0 && (
            <div className="mb-5 flex items-stretch gap-2">
              <div className="flex-1">
                <SearchInput
                  initialValue={initialQuery}
                  onChange={onSearch}
                  placeholder={t("publicJobs.board.searchPlaceholder")}
                />
              </div>
              {showFilters && (
                <button
                  type="button"
                  onClick={() => setDrawerOpen(true)}
                  className="relative inline-flex shrink-0 items-center gap-1.5 rounded-md border border-white/15 bg-card-raised/40 px-3 text-sm font-medium text-white/75 transition hover:border-copper/40 hover:text-white lg:hidden"
                  aria-label={t("publicJobs.board.openFilters")}
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
                      d="M2 4a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4Zm2 4a.75.75 0 0 1 .75-.75h6.5a.75.75 0 0 1 0 1.5h-6.5A.75.75 0 0 1 4 8Zm2 4a.75.75 0 0 1 .75-.75h2.5a.75.75 0 0 1 0 1.5h-2.5A.75.75 0 0 1 6 12Z"
                      clipRule="evenodd"
                    />
                  </svg>
                  {t("publicJobs.board.filters")}
                  {activeFilterCount > 0 && (
                    <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
                      {activeFilterCount}
                    </span>
                  )}
                </button>
              )}
            </div>
          )}

          {!loading && hasActiveFilter && (
            <div className="mb-4 space-y-2.5">
              <div className="flex flex-wrap items-center gap-2">
                {query.trim() && (
                  <FilterChip
                    label={`${t("common.search")}: "${query.trim()}"`}
                    onRemove={() => setQuery("")}
                  />
                )}
                {selectedLocation && (
                  <FilterChip
                    label={`${t("publicJobs.board.locationLabel")}: ${selectedLocation}`}
                    onRemove={() => setSelectedLocation(null)}
                  />
                )}
                {isSalaryActive && (
                  <FilterChip
                    label={`${t("publicJobs.board.salaryRange")}: ${formatSalaryShort(effectiveSalaryRange[0])} – ${formatSalaryShort(effectiveSalaryRange[1])}`}
                    onRemove={handleResetSalary}
                  />
                )}
              </div>
              <p className="text-xs text-white/40">
                {t("publicJobs.board.resultsCount", { count: filtered.length })}
              </p>
            </div>
          )}

          {/* Content */}
          {loading ? (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 py-16 text-center sm:py-20">
              <p className="text-sm text-white/30">
                {hasActiveFilter
                  ? t("publicJobs.board.noResults")
                  : t("publicJobs.board.noPositions")}
              </p>
              {hasActiveFilter && (
                <button
                  type="button"
                  onClick={clearFilters}
                  className="mt-4 text-xs text-copper/70 transition hover:text-copper"
                >
                  {t("publicJobs.board.clearFilters")}
                </button>
              )}
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              {filtered.map((job) => (
                <Link
                  key={job.id}
                  to={{
                    pathname: `/jobs/${job.id}`,
                    search: searchParams.toString(),
                  }}
                  className="group block rounded-xl border border-white/8 bg-card p-5 transition duration-200 hover:border-copper/25 hover:bg-card-raised sm:p-6"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate font-medium text-white/85 transition duration-200 group-hover:text-white/95">
                        {job.title}
                      </h2>
                      <p className="mt-1 flex items-center gap-1 text-sm text-white/40">
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          viewBox="0 0 16 16"
                          fill="currentColor"
                          className="size-3.5 shrink-0"
                          aria-hidden="true"
                        >
                          <path
                            fillRule="evenodd"
                            d="M8 1.5A4.5 4.5 0 0 0 3.5 6c0 2.625 3.375 7.5 4.5 7.5S12.5 8.625 12.5 6A4.5 4.5 0 0 0 8 1.5ZM8 7.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"
                            clipRule="evenodd"
                          />
                        </svg>
                        <span className="truncate">{job.location}</span>
                      </p>
                    </div>
                    <span className="shrink-0 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
                      {t("publicJobs.board.open")}
                    </span>
                  </div>
                  <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-white/50 sm:line-clamp-none">
                    {truncate(job.description, 160)}
                  </p>
                  <div className="mt-4 flex items-center gap-1.5 text-xs">
                    <span className="text-white/35">{t("common.salary")}:</span>
                    <span className="font-medium text-copper/85">
                      {formatCardSalary(job.salary_min, job.salary_max) ??
                        t("common.salaryNotSpecified")}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-white/25">
                    {t("publicJobs.board.posted")} {formatDate(job.created_at)}
                  </p>
                </Link>
              ))}
            </div>
          )}
          <div ref={sentinelRef} />
        </div>
      </div>

      {/* Mobile filter drawer — portaled to body so it escapes the page-enter
          transform (which creates a containing block for fixed elements). */}
      {showFilters &&
        createPortal(
          <div
            className={`fixed inset-0 z-[100] lg:hidden ${drawerOpen ? "pointer-events-auto" : "pointer-events-none"}`}
            aria-hidden={!drawerOpen}
          >
            <div
              onClick={() => setDrawerOpen(false)}
              className={`absolute inset-0 bg-black/65 transition-opacity duration-200 ${drawerOpen ? "opacity-100" : "opacity-0"}`}
            />
            <div
              className={`absolute inset-y-0 start-0 flex w-[88%] max-w-sm flex-col bg-card-raised shadow-2xl shadow-black/50 transition-transform duration-200 ease-out ${drawerOpen ? "translate-x-0" : "ltr:-translate-x-full rtl:translate-x-full"}`}
              role="dialog"
              aria-modal="true"
              aria-label={t("publicJobs.board.filters")}
            >
              <div className="flex items-center justify-between border-b border-white/8 px-5 py-4">
                <p className="text-sm font-semibold text-white/90">
                  {t("publicJobs.board.filters")}
                </p>
                <button
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                  aria-label={t("common.close")}
                  className="rounded-sm p-1 text-white/55 transition hover:text-white"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 16 16"
                    fill="currentColor"
                    className="size-4"
                    aria-hidden="true"
                  >
                    <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06L6.94 8l-4.72 4.72a.75.75 0 1 0 1.06 1.06L8 9.06l4.72 4.72a.75.75 0 1 0 1.06-1.06L9.06 8l4.72-4.72a.75.75 0 0 0-1.06-1.06L8 6.94 3.28 2.22Z" />
                  </svg>
                </button>
              </div>
              <div className="flex-1 overflow-y-auto px-5 py-5">
                <FilterPanel {...baseFilterPanelProps} showSearch />
              </div>
              <div className="border-t border-white/8 px-5 py-3">
                <button
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                  className="w-full rounded-sm bg-copper py-2.5 text-sm font-medium text-white transition hover:bg-gold"
                >
                  {t("publicJobs.board.showResults", { count: filtered.length })}
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </div>
  );
}
