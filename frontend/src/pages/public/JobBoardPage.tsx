import { type CSSProperties, useCallback, useEffect, useMemo, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { createPortal } from "react-dom";
import { Link, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJobs } from "@/services/jobs";
import { useInfiniteList } from "@/hooks/useInfiniteList";
import SearchInput from "@/components/ui/SearchInput";
import RangeSlider from "@/components/ui/RangeSlider";
import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import FeaturedRibbon from "@/components/ui/FeaturedRibbon";
import type { JobPublicRead } from "@/types/api";

function rise(delay = "0s", duration = "0.8s"): CSSProperties {
  return { animation: `text-rise ${duration} cubic-bezier(0.16, 1, 0.3, 1) ${delay} both` };
}
function revealUp(delay = "0s"): CSSProperties {
  return { animation: `reveal-up 0.75s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` };
}
function ruleDraw(delay = "0s"): CSSProperties {
  return { animation: `line-expand-h 0.7s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both`, transformOrigin: "right" };
}

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

function FilterSidebarSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-white/8 bg-card-raised/40 p-5">
      {/* "Filters" heading */}
      <div className="mb-5 h-4 w-16 rounded bg-white/10" />
      {/* Location section: label + 4 chip pills wrapped */}
      <div className="mb-6">
        <div className="mb-2.5 h-3 w-20 rounded bg-white/8" />
        <div className="flex flex-wrap gap-2">
          <div className="h-7 w-16 rounded-full bg-white/6" />
          <div className="h-7 w-20 rounded-full bg-white/6" />
          <div className="h-7 w-14 rounded-full bg-white/6" />
          <div className="h-7 w-24 rounded-full bg-white/6" />
        </div>
      </div>
      {/* Salary section: label + slider track */}
      <div>
        <div className="mb-3 h-3 w-24 rounded bg-white/8" />
        <div className="space-y-3">
          <div className="flex justify-between">
            <div className="h-3 w-12 rounded bg-white/6" />
            <div className="h-3 w-12 rounded bg-white/6" />
          </div>
          <div className="h-1.5 w-full rounded-full bg-white/6" />
        </div>
      </div>
    </div>
  );
}

function SearchBarSkeleton() {
  return (
    <div className="mb-5 flex animate-pulse items-stretch gap-2">
      <div className="h-10 flex-1 rounded-md bg-white/6" />
      {/* mobile filter trigger button placeholder */}
      <div className="h-10 w-24 shrink-0 rounded-md bg-white/6 lg:hidden" />
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-white/8 bg-card p-5 sm:p-6">
      {/* Title + location (left) / status badge (right) */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-4 w-3/4 rounded bg-white/10" />
          <div className="h-3 w-1/3 rounded bg-white/6" />
        </div>
        <div className="h-5 w-14 shrink-0 rounded-full bg-white/6" />
      </div>
      {/* short_description — line-clamp-3 on mobile, can expand on sm+ */}
      <div className="mt-3 space-y-2">
        <div className="h-3 rounded bg-white/6" />
        <div className="h-3 w-11/12 rounded bg-white/6" />
        <div className="h-3 w-3/4 rounded bg-white/6" />
      </div>
      {/* Tag chips */}
      <div className="mt-3 flex flex-wrap gap-1.5">
        <div className="h-5 w-16 rounded-full bg-white/6" />
        <div className="h-5 w-20 rounded-full bg-white/6" />
        <div className="h-5 w-14 rounded-full bg-white/6" />
      </div>
      {/* Salary line */}
      <div className="mt-4 h-3 w-2/5 rounded bg-white/6" />
      {/* Posted date */}
      <div className="mt-2 h-3 w-1/4 rounded bg-white/5" />
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
  selectedLocations: string[];
  onLocationsChange: (next: string[]) => void;
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
  selectedLocations,
  onLocationsChange,
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
              onClick={() => onLocationsChange([])}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition",
                selectedLocations.length === 0
                  ? "bg-copper text-white"
                  : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
              ].join(" ")}
            >
              {t("publicJobs.board.allLocations")}
            </button>
            {locations.map((loc) => {
              const active = selectedLocations.includes(loc);
              return (
              <button
                key={loc}
                type="button"
                onClick={() =>
                  onLocationsChange(
                    active
                      ? selectedLocations.filter((x) => x !== loc)
                      : [...selectedLocations, loc],
                  )
                }
                className={[
                  "rounded-full px-3 py-1.5 text-xs font-medium transition",
                  active
                    ? "bg-copper text-white"
                    : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85",
                ].join(" ")}
              >
                {loc}
              </button>
              );
            })}
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
  const initialLocationCsv = searchParams.get("loc");
  const initialSmin = searchParams.get("smin");
  const initialSmax = searchParams.get("smax");

  const [query, setQuery] = useState(initialQuery);
  const debouncedQuery = useDebounce(query, 300);
  const [selectedLocations, setSelectedLocations] = useState<string[]>(() =>
    initialLocationCsv ? initialLocationCsv.split(",").filter(Boolean) : [],
  );
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
    setOrDelete("q", debouncedQuery.trim() || null);
    setOrDelete(
      "loc",
      selectedLocations.length > 0 ? selectedLocations.join(",") : null,
    );
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
  }, [debouncedQuery, selectedLocations, effectiveSalaryRange, isSalaryActive]);

  const filtered = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return jobs.filter((j) => {
      const requirementsText = j.requirements.map((r) => r.text).join(" ");
      const tagsText = j.tags.join(" ");
      const matchesQuery =
        !q ||
        [
          j.title,
          j.location,
          j.short_description,
          j.description,
          requirementsText,
          tagsText,
        ].some((s) => s.toLowerCase().includes(q));
      const matchesLocation =
        selectedLocations.length === 0 || selectedLocations.includes(j.location);

      let matchesSalary = true;
      if (isSalaryActive) {
        const [filterLo, filterHi] = effectiveSalaryRange;
        // Jobs without any salary information: always show.
        if (j.salary_min != null || j.salary_max != null) {
          // Treat a single-bound job as open-ended on the missing side so a
          // job listing only "מ-10,000 ₪" still matches a filter that caps lower.
          const jobLo = j.salary_min ?? Number.NEGATIVE_INFINITY;
          const jobHi = j.salary_max ?? Number.POSITIVE_INFINITY;
          // Include the job whenever its range overlaps or touches the filter
          // range — e.g. filter 10,000–13,000 includes a 12,000–15,000 role.
          matchesSalary = jobHi >= filterLo && jobLo <= filterHi;
        }
      }

      return matchesQuery && matchesLocation && matchesSalary;
    });
  }, [jobs, debouncedQuery, selectedLocations, effectiveSalaryRange, isSalaryActive]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) + selectedLocations.length + (isSalaryActive ? 1 : 0);
  const hasActiveFilter = activeFilterCount > 0;

  const handleSalaryChange = useCallback((next: [number, number]) => {
    setSalaryRange(next);
  }, []);

  const handleResetSalary = useCallback(() => {
    setSalaryRange([salaryBounds.min, salaryBounds.max]);
  }, [salaryBounds]);

  const clearFilters = useCallback(() => {
    setQuery("");
    setSelectedLocations([]);
    setSalaryRange(null);
  }, []);

  const structuredData = useMemo(() => {
    const breadcrumb = {
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
        {
          "@type": "ListItem",
          position: 2,
          name: t("publicJobs.board.title"),
          item: `${SITE_URL}/jobs`,
        },
      ],
    };
    if (loading || jobs.length === 0) {
      return { "@context": "https://schema.org", "@graph": [breadcrumb] };
    }
    const itemList = {
      "@type": "ItemList",
      name: t("publicJobs.board.title"),
      url: `${SITE_URL}/jobs`,
      numberOfItems: jobs.length,
      itemListElement: jobs.slice(0, 10).map((job, i) => ({
        "@type": "ListItem",
        position: i + 1,
        name: job.title,
        url: `${SITE_URL}/jobs/${job.id}`,
      })),
    };
    return { "@context": "https://schema.org", "@graph": [breadcrumb, itemList] };
  }, [loading, jobs, t]);

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
    selectedLocations,
    onLocationsChange: setSelectedLocations,
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
    <div className="pb-14">
      <SeoHead
        title={t("publicJobs.board.title")}
        description={t("publicJobs.board.subtitle")}
        canonical={`${SITE_URL}/jobs`}
        structuredData={structuredData}
      />

      {/* ── Hero strip ──────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden pt-28 pb-14 sm:pt-32 sm:pb-16">
        {/* Property image background */}
        <div
          className="absolute inset-0"
          style={{
            backgroundImage: "url(/property-exterior.jpg)",
            backgroundSize: "cover",
            backgroundPosition: "center 40%",
          }}
        />
        <div className="absolute inset-0 bg-void/88" />
        {/* Copper glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 90% at 50% -10%, color-mix(in srgb, var(--color-copper) 11%, transparent), transparent)",
          }}
        />

        <div className="relative mx-auto max-w-4xl px-6">
          {/* Eyebrow */}
          <div className="h-px w-8 bg-copper/45" style={ruleDraw("0.1s")} />
          <div className="mt-3 overflow-hidden">
            <p
              className="text-[10px] font-semibold uppercase tracking-widest text-copper/75"
              style={rise("0.2s", "0.55s")}
            >
              RS Recruiting
            </p>
          </div>

          {/* Headline */}
          <div className="mt-5 overflow-hidden">
            <h1
              className="text-3xl font-semibold leading-snug text-white/92 sm:text-4xl"
              style={rise("0.3s")}
            >
              {t("publicJobs.board.title")}
            </h1>
          </div>

          {/* Subtitle */}
          <p
            className="mt-3 max-w-xl text-sm leading-relaxed text-white/45"
            style={revealUp("0.5s")}
          >
            {t("publicJobs.board.subtitle")}
          </p>

          {/* Search bar */}
          <div className="mt-8 max-w-lg" style={revealUp("0.65s")}>
            <SearchInput
              initialValue={initialQuery}
              onChange={onSearch}
              placeholder={t("publicJobs.board.searchPlaceholder")}
            />
          </div>
        </div>
      </section>

      {/* ── Job list ────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-4xl px-6 pt-10">
      <div
        className={
          loading || showFilters ? "lg:grid lg:grid-cols-[240px_1fr] lg:gap-8" : ""
        }
      >
        {/* Filter sidebar — sticky offset accounts for fixed navbar */}
        {loading ? (
          <aside className="hidden lg:sticky lg:top-28 lg:block lg:self-start">
            <FilterSidebarSkeleton />
          </aside>
        ) : showFilters ? (
          <aside className="hidden lg:sticky lg:top-28 lg:block lg:self-start">
            <div className="rounded-xl border border-white/8 bg-card-raised/40 p-5">
              <p className="mb-4 text-sm font-medium text-white/85">
                {t("publicJobs.board.filters")}
              </p>
              <FilterPanel {...baseFilterPanelProps} />
            </div>
          </aside>
        ) : null}

        {/* Results column */}
        <div className="min-w-0">
          {/* Mobile filter trigger (search bar is in hero) */}
          {loading && <SearchBarSkeleton />}
          {!loading && jobs.length > 0 && (
            <div className="mb-5 flex items-stretch gap-2">
              <div className="flex-1" />
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
                {selectedLocations.map((loc) => (
                  <FilterChip
                    key={`loc-${loc}`}
                    label={`${t("publicJobs.board.locationLabel")}: ${loc}`}
                    onRemove={() =>
                      setSelectedLocations((prev) => prev.filter((x) => x !== loc))
                    }
                  />
                ))}
                {isSalaryActive && (
                  <FilterChip
                    label={`${t("publicJobs.board.salaryRange")}: ${formatSalaryShort(effectiveSalaryRange[0])} – ${formatSalaryShort(effectiveSalaryRange[1])}`}
                    onRemove={handleResetSalary}
                  />
                )}
              </div>
              <p className="text-xs text-white/40">
                {filtered.length === 1
                  ? t("publicJobs.board.resultsCount.one")
                  : t("publicJobs.board.resultsCount.other", { count: filtered.length })}
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
                  className={[
                    "group relative block overflow-hidden rounded-xl border bg-card p-5 transition duration-200 sm:p-6",
                    job.is_featured
                      ? "border-gold/40 hover:border-gold/60 hover:bg-card-raised"
                      : "border-white/8 hover:border-copper/25 hover:bg-card-raised",
                  ].join(" ")}
                >
                  {job.is_featured && <FeaturedRibbon label={t("publicJobs.board.featured")} />}
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
                  </div>
                  <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-white/55 sm:line-clamp-none">
                    {job.short_description}
                  </p>
                  {job.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {job.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-copper/25 bg-copper/10 px-2 py-0.5 text-[11px] font-medium text-copper/90"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
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
    </div>
  );
}
