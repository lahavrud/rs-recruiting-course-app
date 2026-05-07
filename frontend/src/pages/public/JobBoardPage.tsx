import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJobs } from "@/services/jobs";
import SearchInput from "@/components/ui/SearchInput";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import type { JobPublicRead } from "@/types/api";
import axios from "axios";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength).trimEnd() + "…";
}

function CardSkeleton() {
  return (
    <div className="animate-pulse rounded-xl border border-white/5 bg-card p-6">
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

export default function JobBoardPage() {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<JobPublicRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [selectedLocation, setSelectedLocation] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchJobs() {
      try {
        const data = await getPublicJobs();
        if (!cancelled) setJobs(data);
      } catch (err) {
        if (!cancelled) {
          if (axios.isAxiosError(err)) {
            setError(t("publicJobs.board.errorLoad"));
          } else {
            setError(t("publicJobs.board.errorGeneric"));
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, [t]);

  const onSearch = useCallback((v: string) => setQuery(v), []);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) {
      if (j.location) seen.add(j.location);
    }
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return jobs.filter((j) => {
      const matchesQuery =
        !q ||
        [j.title, j.location, j.description].some((s) =>
          s.toLowerCase().includes(q),
        );
      const matchesLocation = !selectedLocation || j.location === selectedLocation;
      return matchesQuery && matchesLocation;
    });
  }, [jobs, query, selectedLocation]);

  const hasActiveFilter = !!query.trim() || !!selectedLocation;

  if (error) {
    return (
      <div className="rounded-lg border border-danger/20 bg-danger/10 p-6 text-center text-sm text-danger">
        {error}
      </div>
    );
  }

  return (
    <div>
      <SeoHead
        title={t("publicJobs.board.title")}
        description={t("publicJobs.board.subtitle")}
        canonical={`${SITE_URL}/jobs`}
      />
      {/* Header */}
      <div className="mb-8 sm:mb-10">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          RS Recruiting
        </p>
        <div className="mt-3 h-px w-8 bg-copper/40" />
        <h1 className="mt-5 text-2xl font-semibold text-white/90 sm:text-3xl">
          {t("publicJobs.board.title")}
        </h1>
        <p className="mt-2 text-sm text-white/45">
          {t("publicJobs.board.subtitle")}
        </p>
      </div>

      {/* Search + location filters */}
      {!loading && jobs.length > 0 && (
        <div className="mb-6 space-y-3">
          <SearchInput
            onChange={onSearch}
            placeholder={t("publicJobs.board.searchPlaceholder")}
          />
          {uniqueLocations.length >= 2 && (
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setSelectedLocation(null)}
                className={[
                  "rounded-full px-3 py-1 text-xs font-medium transition",
                  !selectedLocation
                    ? "bg-copper text-white"
                    : "border border-white/15 text-white/50 hover:border-white/30 hover:text-white/75",
                ].join(" ")}
              >
                {t("publicJobs.board.allLocations")}
              </button>
              {uniqueLocations.map((loc) => (
                <button
                  key={loc}
                  type="button"
                  onClick={() =>
                    setSelectedLocation((prev) => (prev === loc ? null : loc))
                  }
                  className={[
                    "rounded-full px-3 py-1 text-xs font-medium transition",
                    selectedLocation === loc
                      ? "bg-copper text-white"
                      : "border border-white/15 text-white/50 hover:border-white/30 hover:text-white/75",
                  ].join(" ")}
                >
                  {loc}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Content */}
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center">
          <p className="text-sm text-white/30">
            {hasActiveFilter
              ? t("publicJobs.board.noResults")
              : t("publicJobs.board.noPositions")}
          </p>
          {hasActiveFilter && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setSelectedLocation(null);
              }}
              className="mt-4 text-xs text-copper/70 transition hover:text-copper"
            >
              {t("publicJobs.board.clearFilters")}
            </button>
          )}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {filtered.map((job) => (
            <Link
              key={job.id}
              to={`/jobs/${job.id}`}
              className="group block rounded-xl border border-white/8 bg-card p-6 transition duration-200 hover:border-copper/25 hover:bg-card-raised"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
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
                    {job.location}
                  </p>
                </div>
                <span className="shrink-0 rounded-full bg-success/10 px-2.5 py-0.5 text-xs font-medium text-success">
                  {t("publicJobs.board.open")}
                </span>
              </div>
              <p className="mt-3 text-sm leading-relaxed text-white/50">
                {truncate(job.description, 160)}
              </p>
              <div className="mt-4 flex items-center justify-between gap-3">
                <p className="text-xs text-white/25">
                  {t("publicJobs.board.posted")} {formatDate(job.created_at)}
                </p>
                {job.salary_min != null && job.salary_max != null && (
                  <p className="shrink-0 text-xs font-medium text-copper/70">
                    {job.salary_min.toLocaleString("he-IL")}–{job.salary_max.toLocaleString("he-IL")} ₪
                  </p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
