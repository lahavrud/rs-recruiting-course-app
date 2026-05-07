import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getPublicJob } from "@/services/jobs";
import SeoHead, { SITE_URL, SITE_NAME } from "@/components/ui/SeoHead";
import type { JobPublicRead } from "@/types/api";
import axios from "axios";

function formatSalary(min: number | null, max: number | null): string | null {
  if (!min && !max) return null;
  const fmt = (n: number) => n.toLocaleString("he-IL");
  if (min && max) return `${fmt(min)}–${fmt(max)} ₪/חודש`;
  if (min) return `מ-${fmt(min)} ₪/חודש`;
  return `עד ${fmt(max!)} ₪/חודש`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function DetailSkeleton() {
  return (
    <div className="mx-auto max-w-4xl animate-pulse">
      <div className="mb-8 h-4 w-24 rounded bg-white/8" />
      <div className="lg:grid lg:grid-cols-[1fr_280px] lg:gap-8">
        {/* Left */}
        <div className="rounded-xl border border-white/5 bg-card p-6 sm:p-10">
          <div className="space-y-3">
            <div className="h-6 w-2/3 rounded bg-white/8" />
            <div className="h-4 w-1/4 rounded bg-white/5" />
          </div>
          <div className="my-8 h-px bg-white/5" />
          <div className="space-y-2">
            <div className="h-3 w-20 rounded bg-white/5" />
            {[1, 0.9, 0.85, 0.7, 0.8].map((w, i) => (
              <div key={i} className="h-3 rounded bg-white/5" style={{ width: `${w * 100}%` }} />
            ))}
          </div>
          <div className="mt-8 space-y-2">
            <div className="h-3 w-20 rounded bg-white/5" />
            {[0.95, 0.75, 0.6].map((w, i) => (
              <div key={i} className="h-3 rounded bg-white/5" style={{ width: `${w * 100}%` }} />
            ))}
          </div>
        </div>
        {/* Right sidebar */}
        <div className="mt-4 rounded-xl border border-white/5 bg-card p-6 lg:mt-0">
          <div className="space-y-3">
            <div className="h-5 w-3/4 rounded bg-white/8" />
            <div className="h-3 w-1/2 rounded bg-white/5" />
            <div className="h-3 w-2/5 rounded bg-white/5" />
          </div>
          <div className="mt-6 h-10 rounded-sm bg-white/5" />
        </div>
      </div>
    </div>
  );
}

export default function JobDetailPage() {
  const { t } = useTranslation();
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<JobPublicRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) {
      navigate("/jobs", { replace: true });
      return;
    }

    const jobId = Number.parseInt(id, 10);
    if (!Number.isFinite(jobId)) {
      navigate("/jobs", { replace: true });
      return;
    }

    let cancelled = false;

    async function fetchJob() {
      try {
        const data = await getPublicJob(jobId);
        if (!cancelled) setJob(data);
      } catch (err) {
        if (!cancelled) {
          if (axios.isAxiosError(err) && err.response?.status === 404) {
            setError(t("publicJobs.detail.unavailable"));
          } else {
            setError(t("publicJobs.detail.errorLoad"));
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchJob();
    return () => {
      cancelled = true;
    };
  }, [id, navigate, t]);

  if (loading) return <DetailSkeleton />;

  if (error || !job) {
    return (
      <div className="text-center">
        <div className="rounded-lg border border-danger/20 bg-danger/10 p-6 text-sm text-danger">
          {error ?? t("publicJobs.detail.notFound")}
        </div>
        <Link
          to="/jobs"
          className="mt-6 inline-block text-sm text-white/40 transition hover:text-copper"
        >
          {t("publicJobs.detail.backToJobs")}
        </Link>
      </div>
    );
  }

  const applyHref = `/jobs/${job.id}/apply`;

  const jobPosting = {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: job.title,
    description: `${job.description}\n\n${job.requirements}`,
    datePosted: job.created_at,
    url: `${SITE_URL}/jobs/${job.id}`,
    hiringOrganization: { "@type": "Organization", name: SITE_NAME, sameAs: SITE_URL },
    jobLocation: {
      "@type": "Place",
      address: { "@type": "PostalAddress", addressLocality: job.location, addressCountry: "IL" },
    },
    ...(job.salary_min != null && job.salary_max != null ? {
      baseSalary: {
        "@type": "MonetaryAmount",
        currency: "ILS",
        value: { "@type": "QuantitativeValue", minValue: job.salary_min, maxValue: job.salary_max, unitText: "MONTH" },
      },
    } : {}),
  };

  return (
    <div className="mx-auto max-w-4xl">
      <SeoHead
        title={job.title}
        description={job.description.slice(0, 160)}
        canonical={`${SITE_URL}/jobs/${job.id}`}
        ogType="article"
        structuredData={jobPosting}
      />
      <Link
        to="/jobs"
        className="mb-8 inline-flex items-center gap-1.5 text-sm text-white/35 transition hover:text-copper"
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
            d="M6.22 4.22a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06L7.28 11.78a.75.75 0 0 1-1.06-1.06L8.94 8 6.22 5.28a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
        {t("publicJobs.detail.backToJobs")}
      </Link>

      <div className="lg:grid lg:grid-cols-[1fr_280px] lg:items-start lg:gap-8">
        {/* ── Main article ── */}
        <article className="rounded-xl border border-white/8 bg-card p-6 sm:p-10">
          {/* Header */}
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h1 className="text-xl font-semibold text-white/95 sm:text-2xl">
                {job.title}
              </h1>
              <p className="mt-1.5 flex items-center gap-1.5 text-sm text-white/45">
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
            <span className="shrink-0 rounded-full bg-success/10 px-3 py-1 text-xs font-medium text-success">
              {t("publicJobs.detail.open")}
            </span>
          </div>
          <p className="mt-2 text-xs text-white/25">
            {t("publicJobs.detail.posted")} {formatDate(job.created_at)}
          </p>
          {formatSalary(job.salary_min, job.salary_max) && (
            <p className="mt-1.5 text-sm font-medium text-copper/80">
              {formatSalary(job.salary_min, job.salary_max)}
            </p>
          )}

          <div className="my-8 h-px bg-white/8" />

          {/* About the role */}
          <div>
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">
              {t("publicJobs.detail.aboutRole")}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/65">
              {job.description}
            </p>
          </div>

          {/* Requirements */}
          <div className="mt-8">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-copper">
              {t("publicJobs.detail.requirements")}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-white/65">
              {job.requirements}
            </p>
          </div>

          {/* Mobile CTA — hidden on lg */}
          <div className="mt-10 border-t border-white/8 pt-8 lg:hidden">
            <Link
              to={applyHref}
              className="inline-block w-full rounded-sm bg-copper py-3 text-center text-sm font-medium text-white transition hover:bg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-card"
            >
              {t("publicJobs.detail.applyNow")}
            </Link>
          </div>
        </article>

        {/* ── Sticky sidebar ── */}
        <aside className="mt-4 lg:sticky lg:top-6 lg:mt-0">
          <div className="rounded-xl border border-white/8 bg-card p-6">
            <h2 className="font-medium text-white/90">{job.title}</h2>
            <p className="mt-1.5 flex items-center gap-1.5 text-sm text-white/45">
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
            <p className="mt-1 text-xs text-white/25">
              {t("publicJobs.detail.posted")} {formatDate(job.created_at)}
            </p>
            {formatSalary(job.salary_min, job.salary_max) && (
              <p className="mt-2 text-sm font-medium text-copper/80">
                {formatSalary(job.salary_min, job.salary_max)}
              </p>
            )}

            <div className="mt-5 h-px bg-white/8" />

            <Link
              to={applyHref}
              className="mt-5 block rounded-sm bg-copper py-3 text-center text-sm font-medium text-white transition hover:bg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gold focus-visible:ring-offset-2 focus-visible:ring-offset-card"
            >
              {t("publicJobs.detail.applyNow")}
            </Link>
          </div>
        </aside>
      </div>
    </div>
  );
}
