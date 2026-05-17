import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { apiErrorKey } from "@/utils/apiError";
import { getActiveCompanies } from "@/services/adminCompanies";
import {
  approveJob,
  createJob,
  deleteJob,
  getJob,
  getJobs,
  rejectJob,
  updateJob,
} from "@/services/adminJobs";
import { getApplications } from "@/services/adminApplications";
import type {
  ActiveCompanyRead,
  JobAdminCreate,
  JobAdminUpdate,
  JobRead,
  JobRequirementItem,
} from "@/types/api";
import { JobStatus, JOB_SHORT_DESC_MAX, JOB_REQ_MIN_COUNT } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import Dialog from "@/components/ui/Dialog";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import TableSkeleton from "@/components/ui/TableSkeleton";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SearchInput from "@/components/ui/SearchInput";
import RangeSlider from "@/components/ui/RangeSlider";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import JobRequirementsInput from "@/components/ui/JobRequirementsInput";
import JobTagsInput from "@/components/ui/JobTagsInput";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { focusFirstError } from "@/utils/focusFirstError";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { inputCls, selectCls, textareaCls } from "@/styles/forms";

const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];

// Order in which fields are scanned when auto-focusing the first invalid
// field on submit. Mirrors the visual order in the dialog so users see the
// scroll/focus move through the form top-to-bottom.
const JOB_EDIT_FIELD_ORDER = [
  "title",
  "location",
  "salary_min",
  "salary_max",
  "short_description",
  "description",
  "requirements",
  "tags",
] as const;

const JOB_CREATE_FIELD_ORDER = [
  "company_id",
  "title",
  "location",
  "salary_min",
  "salary_max",
  "short_description",
  "description",
  "requirements",
  "tags",
] as const;

const STATUS_COLORS: Record<string, string> = {
  PENDING_APPROVAL: "bg-warning/10 text-warning",
  PUBLISHED: "bg-success/10 text-success",
  CLOSED: "bg-white/8 text-white/45",
};

const ALL_FILTER = "ALL";
type FilterValue = string;

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminJobsPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.jobs.title"));
  const toast = useToast();

  const [filter, setFilter] = useState<FilterValue>(() => {
    const s = new URLSearchParams(window.location.search).get("status");
    if (
      s === JobStatus.PENDING_APPROVAL ||
      s === JobStatus.PUBLISHED ||
      s === JobStatus.CLOSED
    ) {
      return s;
    }
    return ALL_FILTER;
  });

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<JobRead>> => {
      const params: { status?: JobStatus; cursor: string | null } = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as JobStatus;
      return getJobs(params);
    },
    [filter],
  );

  const {
    items: jobs,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
    removeItem,
  } = useInfiniteList<JobRead>(fetcher);

  const [detail, setDetail] = useState<JobRead | null>(null);
  const [editing, setEditing] = useState<JobRead | null>(null);
  const [creating, setCreating] = useState(false);
  const [deletePending, setDeletePending] = useState<JobRead | null>(null);
  const [rejectPending, setRejectPending] = useState<JobRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  // Client-side filters (applied to the loaded set).
  // Status is the only filter that re-fetches server-side (see fetcher above);
  // everything else narrows the in-memory result.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [salaryRange, setSalaryRange] = useState<[number, number] | null>(null);
  const [filterOpen, setFilterOpen] = useState(false);

  const uniqueLocations = useMemo(() => {
    const seen = new Set<string>();
    for (const j of jobs) if (j.location) seen.add(j.location.trim());
    return Array.from(seen).sort((a, b) => a.localeCompare(b, "he"));
  }, [jobs]);

  const uniqueCompanies = useMemo(() => {
    const seen = new Set<number>();
    for (const j of jobs) seen.add(j.company_id);
    return Array.from(seen);
  }, [jobs]);

  const salaryBounds = useMemo(() => {
    let lo = Infinity, hi = -Infinity;
    for (const j of jobs) {
      if (j.salary_min != null) lo = Math.min(lo, j.salary_min);
      if (j.salary_max != null) hi = Math.max(hi, j.salary_max);
    }
    if (!Number.isFinite(lo) || !Number.isFinite(hi) || lo >= hi) {
      return { min: 0, max: 50000 };
    }
    return { min: Math.floor(lo / 500) * 500, max: Math.ceil(hi / 500) * 500 };
  }, [jobs]);

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

  const filteredJobs = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return jobs.filter((j) => {
      if (q) {
        const reqsText = j.requirements.map((r) => r.text).join(" ");
        const tagsText = j.tags.join(" ");
        const matches = [
          j.title,
          j.location,
          j.short_description,
          j.description,
          reqsText,
          tagsText,
        ].some((s) => s.toLowerCase().includes(q));
        if (!matches) return false;
      }
      if (selectedLocations.length > 0 && !selectedLocations.includes(j.location.trim())) return false;
      if (companyFilter.length > 0 && !companyFilter.includes(j.company_id)) return false;
      if (featuredOnly && !j.is_featured) return false;
      if (isSalaryActive) {
        const [filterLo, filterHi] = effectiveSalaryRange;
        if (j.salary_min != null || j.salary_max != null) {
          const jobLo = j.salary_min ?? Number.NEGATIVE_INFINITY;
          const jobHi = j.salary_max ?? Number.POSITIVE_INFINITY;
          if (!(jobHi >= filterLo && jobLo <= filterHi)) return false;
        }
      }
      return true;
    });
  }, [
    jobs,
    debouncedQuery,
    selectedLocations,
    companyFilter,
    featuredOnly,
    effectiveSalaryRange,
    isSalaryActive,
  ]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    selectedLocations.length +
    companyFilter.length +
    (featuredOnly ? 1 : 0) +
    (isSalaryActive ? 1 : 0);

  function clearFilters() {
    setQuery("");
    setSelectedLocations([]);
    setCompanyFilter([]);
    setFeaturedOnly(false);
    setSalaryRange(null);
  }

  // Load company names + emails for the filter chip and the mailto action.
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [companyEmailById, setCompanyEmailById] = useState<Map<number, string>>(
    new Map(),
  );
  useEffect(() => {
    if (uniqueCompanies.length === 0) return;
    const ctrl = new AbortController();
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((page) => {
        const names = new Map<number, string>();
        const emails = new Map<number, string>();
        for (const row of page.items) {
          names.set(row.company_profile.id, row.company_profile.name);
          if (row.user?.email) {
            emails.set(row.company_profile.id, row.user.email);
          }
        }
        setCompanyNameById(names);
        setCompanyEmailById(emails);
      })
      .catch(() => {});
    return () => ctrl.abort();
  }, [uniqueCompanies.length]);

  function openMailToCompany(job: JobRead) {
    const email = companyEmailById.get(job.company_id);
    if (!email) {
      toast.error(t("admin.jobs.emailNoAddress"));
      return;
    }
    const subject = encodeURIComponent(
      t("admin.jobs.emailSubjectPrefix", { title: job.title }),
    );
    window.open(`mailto:${email}?subject=${subject}`, "_self");
  }

  // Auto-open detail modal when navigated from another page via ?detail=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    const ctrl = new AbortController();
    window.history.replaceState({}, "", window.location.pathname);
    getJob(Number(id), ctrl.signal)
      .then((job) => setDetail(job))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        toast.error(t(apiErrorKey(e)));
      });
    return () => ctrl.abort();
  }, [t, toast]);

  const STATUS_LABELS: Record<string, string> = {
    PENDING_APPROVAL: t("admin.jobs.statusLabels.PENDING_APPROVAL"),
    PUBLISHED: t("admin.jobs.statusLabels.PUBLISHED"),
    CLOSED: t("admin.jobs.statusLabels.CLOSED"),
  };

  async function handleApprove(job: JobRead) {
    try {
      const updated = await approveJob(job.id);
      updateItem((j) => j.id === job.id, updated);
      toast.success(t("admin.jobs.approvedToast"));
    } catch {
      toast.error(t("admin.jobs.approveError"));
    }
  }

  async function handleRejectConfirm() {
    if (!rejectPending) return;
    setPendingMutation(true);
    try {
      await rejectJob(rejectPending.id);
      // Backend sets status to CLOSED on reject
      updateItem((j) => j.id === rejectPending.id, {
        ...rejectPending,
        status: JobStatus.CLOSED,
      });
      toast.success(t("admin.jobs.rejectedToast"));
      setRejectPending(null);
    } catch {
      toast.error(t("admin.jobs.rejectError"));
    } finally {
      setPendingMutation(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setPendingMutation(true);
    try {
      await deleteJob(deletePending.id);
      removeItem((j) => j.id === deletePending.id);
      toast.success(t("admin.jobs.deletedToast"));
      setDeletePending(null);
      setDetail(null);
    } catch {
      toast.error(t("admin.jobs.errors.deleteFailed"));
    } finally {
      setPendingMutation(false);
    }
  }

  const filterTabs: FilterValue[] = [ALL_FILTER, ...ALL_STATUSES];

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin.jobs.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin.jobs.title")}
        subtitle={t("admin.jobs.subtitle")}
        action={
          <button
            onClick={() => setCreating(true)}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("admin.jobs.newJob")}
          </button>
        }
      />

      {/* Search + filter trigger */}
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin.jobs.searchPlaceholder")}
            clearable
          />
        </div>
        <button
          type="button"
          onClick={() => setFilterOpen((o) => !o)}
          aria-expanded={filterOpen}
          aria-label={t("admin.jobs.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            filterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin.jobs.filters")}</span>
          {activeFilterCount > 0 && (
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {/* Active filter chips */}
      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {filter !== ALL_FILTER && (
            <ActiveFilterChip
              label={`${t("admin.jobs.fields.status")}: ${STATUS_LABELS[filter]}`}
              onRemove={() => setFilter(ALL_FILTER)}
            />
          )}
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common.search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {selectedLocations.map((loc) => (
            <ActiveFilterChip
              key={`loc-${loc}`}
              label={`${t("publicJobs.board.locationLabel")}: ${loc}`}
              onRemove={() =>
                setSelectedLocations((prev) => prev.filter((x) => x !== loc))
              }
            />
          ))}
          {isSalaryActive && (
            <ActiveFilterChip
              label={`${t("publicJobs.board.salaryRange")}: ${effectiveSalaryRange[0].toLocaleString("he-IL")}–${effectiveSalaryRange[1].toLocaleString("he-IL")} ₪`}
              onRemove={() => setSalaryRange(null)}
            />
          )}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin.jobs.fields.company")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {featuredOnly && (
            <ActiveFilterChip
              label={t("admin.jobs.featuredOnly")}
              onRemove={() => setFeaturedOnly(false)}
            />
          )}
        </div>
      )}

      {/* Filter panel — animated open/close via grid-rows 0fr→1fr */}
      <div
        className={`mb-4 grid transition-[grid-template-rows] duration-300 ease-out ${
          filterOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`space-y-4 rounded-md border border-white/8 bg-card/40 p-4 transition-opacity duration-200 ${
              filterOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
          <div>
            <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-copper">
              {t("admin.jobs.fields.status")}
            </p>
            <div className="flex flex-wrap gap-1.5">
              {filterTabs.map((tab) => {
                const active = filter === tab;
                return (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setFilter(tab)}
                    className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                      active
                        ? "bg-copper text-white"
                        : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85"
                    }`}
                  >
                    {tab === ALL_FILTER
                      ? t("admin.jobs.filterAll")
                      : STATUS_LABELS[tab]}
                  </button>
                );
              })}
            </div>
          </div>
          {uniqueLocations.length >= 2 && (
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-widest text-copper">
                {t("publicJobs.board.locationLabel")}
              </p>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={() => setSelectedLocations([])}
                  className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                    selectedLocations.length === 0
                      ? "bg-copper text-white"
                      : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85"
                  }`}
                >
                  {t("publicJobs.board.allLocations")}
                </button>
                {uniqueLocations.map((loc) => {
                  const active = selectedLocations.includes(loc);
                  return (
                    <button
                      key={loc}
                      type="button"
                      onClick={() =>
                        setSelectedLocations((prev) =>
                          active
                            ? prev.filter((x) => x !== loc)
                            : [...prev, loc],
                        )
                      }
                      className={`rounded-full px-2.5 py-1 text-xs font-medium transition ${
                        active
                          ? "bg-copper text-white"
                          : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85"
                      }`}
                    >
                      {loc}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <p className="text-[11px] font-semibold uppercase tracking-widest text-copper">
                {t("publicJobs.board.salaryRange")}
              </p>
              {isSalaryActive && (
                <button
                  type="button"
                  onClick={() =>
                    setSalaryRange([salaryBounds.min, salaryBounds.max])
                  }
                  className="text-[11px] text-copper/70 transition hover:text-copper"
                >
                  {t("publicJobs.board.resetSalary")}
                </button>
              )}
            </div>
            <RangeSlider
              min={salaryBounds.min}
              max={salaryBounds.max}
              step={500}
              value={effectiveSalaryRange}
              onChange={(next) => setSalaryRange(next)}
              formatValue={(n) => `${n.toLocaleString("he-IL")} ₪`}
              ariaLabelMin={t("publicJobs.board.salaryMinAria")}
              ariaLabelMax={t("publicJobs.board.salaryMaxAria")}
            />
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
                {t("admin.jobs.fields.company")}
              </p>
              <SearchableMultiSelect<number>
                values={companyFilter}
                onChange={setCompanyFilter}
                options={uniqueCompanies.map((id) => ({
                  value: id,
                  label: companyNameById.get(id) ?? `#${id}`,
                }))}
                placeholder={t("admin.jobs.companyAll")}
              />
            </div>
            <label className="mt-auto inline-flex items-center gap-2 text-sm text-white/80">
              <input
                type="checkbox"
                checked={featuredOnly}
                onChange={(e) => setFeaturedOnly(e.target.checked)}
                className="size-4 rounded border-white/20 bg-well text-copper focus:ring-copper"
              />
              {t("admin.jobs.featuredOnly")}
            </label>
          </div>
          </div>
        </div>
      </div>

      {isLoading ? (
        <>
          <div className="md:hidden">
            <MobileListSkeleton rows={6} />
          </div>
          <div className="hidden md:block">
            <TableSkeleton rows={6} columns={4} />
          </div>
        </>
      ) : error ? (
        <ErrorState message={t("admin.jobs.loadError")} onRetry={reload} />
      ) : jobs.length === 0 ? (
        <EmptyState eyebrow={t("admin.jobs.title")} headline={t("admin.jobs.empty")} />
      ) : filteredJobs.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-16 text-center">
          <p className="text-sm text-white/40">
            {t("publicJobs.board.noResults")}
          </p>
          <button
            type="button"
            onClick={clearFilters}
            className="mt-3 text-xs text-copper/70 transition hover:text-copper"
          >
            {t("publicJobs.board.clearFilters")}
          </button>
        </div>
      ) : (
        <>
          {/* Mobile cards — tap row to expand inline; 3-dot menu for actions */}
          <div className="space-y-2 md:hidden">
            {filteredJobs.map((job) => (
              <MobileJobCard
                key={job.id}
                job={job}
                statusLabels={STATUS_LABELS}
                statusColors={STATUS_COLORS}
                companyName={companyNameById.get(job.company_id)}
                actions={
                  <DropdownMenu
                    ariaLabel={t("admin.jobs.rowActionsLabel")}
                    trigger={
                      <button
                        type="button"
                        className="inline-flex size-9 items-center justify-center rounded-full text-white/45 transition hover:bg-white/8 hover:text-white/85"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <span aria-hidden>⋮</span>
                      </button>
                    }
                  >
                    <DropdownMenuItem onSelect={() => setEditing(job)}>
                      {t("admin.jobs.editAction")}
                    </DropdownMenuItem>
                    <DropdownMenuItem onSelect={() => openMailToCompany(job)}>
                      {t("admin.jobs.email")}
                    </DropdownMenuItem>
                    {job.status === JobStatus.PENDING_APPROVAL && (
                      <>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem onSelect={() => handleApprove(job)}>
                          {t("admin.jobs.approve")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setRejectPending(job)}
                        >
                          {t("admin.jobs.reject")}
                        </DropdownMenuItem>
                      </>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      variant="danger"
                      onSelect={() => setDeletePending(job)}
                    >
                      {t("admin.jobs.deleteAction")}
                    </DropdownMenuItem>
                  </DropdownMenu>
                }
              />
            ))}
          </div>

          {/* Desktop table */}
          <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin.jobs.fields.title")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.jobs.fields.location")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("common.salary")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.jobs.fields.status")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.jobs.submittedLabel")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {filteredJobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setDetail(job)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="relative px-4 py-3 font-medium text-white/85">
                      {job.is_featured && <FeaturedDesktopSash />}
                      <span>{job.title}</span>
                    </td>
                    <td className="px-4 py-3 text-white/60">{job.location}</td>
                    <td className="px-4 py-3 text-sm text-copper/70">
                      {job.salary_min != null && job.salary_max != null
                        ? `${job.salary_min.toLocaleString("he-IL")}–${job.salary_max.toLocaleString("he-IL")} ₪`
                        : <span className="text-white/20">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status]}`}
                      >
                        {STATUS_LABELS[job.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(job.created_at)}
                    </td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu
                        ariaLabel={t("admin.jobs.rowActionsLabel")}
                        trigger={
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:bg-white/8 hover:text-white/80"
                          >
                            <span aria-hidden>⋮</span>
                          </button>
                        }
                      >
                        <DropdownMenuItem onSelect={() => setDetail(job)}>
                          {t("admin.jobs.viewAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setEditing(job)}>
                          {t("admin.jobs.editAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => openMailToCompany(job)}>
                          {t("admin.jobs.email")}
                        </DropdownMenuItem>
                        {job.status === JobStatus.PENDING_APPROVAL && (
                          <>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem onSelect={() => handleApprove(job)}>
                              {t("admin.jobs.approve")}
                            </DropdownMenuItem>
                            <DropdownMenuItem
                              variant="danger"
                              onSelect={() => setRejectPending(job)}
                            >
                              {t("admin.jobs.reject")}
                            </DropdownMenuItem>
                          </>
                        )}
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setDeletePending(job)}
                        >
                          {t("admin.jobs.deleteAction")}
                        </DropdownMenuItem>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div ref={sentinelRef} />
          {isFetchingMore && (
            <p className="mt-4 text-center text-xs text-white/30">
              {t("common.loading")}
            </p>
          )}
        </>
      )}

      <DetailDialog
        job={detail}
        statusLabels={STATUS_LABELS}
        statusColors={STATUS_COLORS}
        companyName={detail ? companyNameById.get(detail.company_id) : undefined}
        onClose={() => setDetail(null)}
        onEdit={() => {
          if (detail) setEditing(detail);
          setDetail(null);
        }}
        onDelete={() => {
          if (detail) setDeletePending(detail);
          setDetail(null);
        }}
        onApprove={() => {
          if (detail) handleApprove(detail);
          setDetail(null);
        }}
        onReject={() => {
          if (detail) setRejectPending(detail);
          setDetail(null);
        }}
      />

      <EditDialog
        job={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          updateItem((j) => j.id === updated.id, updated);
          toast.success(t("admin.jobs.savedToast"));
          setEditing(null);
        }}
        onError={() => toast.error(t("admin.jobs.errors.saveFailed"))}
      />

      <CreateDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(created) => {
          prependItem(created);
          toast.success(t("admin.jobs.createdToast"));
          setCreating(false);
        }}
        onError={() => toast.error(t("admin.jobs.errors.createFailed"))}
      />

      <ConfirmDialog
        open={rejectPending != null}
        onOpenChange={(o) => !o && setRejectPending(null)}
        title={t("admin.jobs.rejectConfirmTitle")}
        message={t("admin.jobs.rejectConfirm")}
        confirmLabel={t("admin.jobs.reject")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleRejectConfirm}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin.jobs.deleteConfirmTitle")}
        message={t("admin.jobs.deleteConfirmMessage")}
        confirmLabel={t("admin.jobs.deleteConfirmYes")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

// ── Detail dialog ──────────────────────────────────────────────────────────

interface DetailProps {
  job: JobRead | null;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyName?: string;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onApprove?: () => void;
  onReject?: () => void;
}

function DetailDialog({
  job,
  statusLabels,
  statusColors,
  companyName,
  onClose,
  onEdit,
  onDelete,
  onApprove,
  onReject,
}: DetailProps) {
  const { t } = useTranslation();
  if (!job) return null;
  const isPending = job.status === JobStatus.PENDING_APPROVAL;
  return (
    <Dialog
      open={job != null}
      onOpenChange={(o) => !o && onClose()}
      title={job.title}
      description={job.location}
      size="lg"
      footer={
        <>
          <button
            onClick={onDelete}
            className="rounded-sm border border-danger/40 px-4 py-2 text-sm text-danger hover:bg-danger/10"
          >
            {t("admin.jobs.deleteAction")}
          </button>
          {isPending && onReject && (
            <button
              onClick={onReject}
              className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/70 hover:border-white/40 hover:text-white"
            >
              {t("admin.jobs.reject")}
            </button>
          )}
          {isPending && onApprove && (
            <button
              onClick={onApprove}
              className="rounded-sm border border-success/40 bg-success/15 px-4 py-2 text-sm font-medium text-success hover:bg-success/25"
            >
              {t("admin.jobs.approve")}
            </button>
          )}
          <button
            onClick={onEdit}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("admin.jobs.editAction")}
          </button>
        </>
      }
    >
      <JobDetailBody
        job={job}
        statusLabels={statusLabels}
        statusColors={statusColors}
        companyName={companyName}
        onLeavePage={onClose}
      />
    </Dialog>
  );
}

/** Body content shared by the desktop detail dialog and the mobile inline card expansion. */
function JobDetailBody({
  job,
  statusLabels,
  statusColors,
  companyName,
  onLeavePage,
}: {
  job: JobRead;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyName?: string;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  // Lazy-fetch application count for this job. `null` = loading, number = total.
  // We fetch a generous first page; if it's smaller than the limit it's exact.
  // If we got exactly the limit, we report "N+" since there may be more.
  const APP_FETCH_LIMIT = 100;
  const [applicationCount, setApplicationCount] = useState<{
    n: number;
    capped: boolean;
  } | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    getApplications({ job_id: job.id, limit: APP_FETCH_LIMIT }, ctrl.signal)
      .then((page) =>
        setApplicationCount({
          n: page.items.length,
          capped: page.items.length === APP_FETCH_LIMIT,
        }),
      )
      .catch(() => {});
    return () => ctrl.abort();
  }, [job.id]);

  const salaryStr =
    job.salary_min != null && job.salary_max != null
      ? `${job.salary_min.toLocaleString("he-IL")}–${job.salary_max.toLocaleString("he-IL")} ₪/חודש`
      : null;

  return (
    <div className="space-y-4 text-sm">
      {/* Header strip: status + featured ribbon eyebrow only */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[job.status]}`}
        >
          {statusLabels[job.status]}
        </span>
        {job.is_featured && (
          <span className="inline-flex items-center gap-1 rounded-full border border-gold/40 bg-gold/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-gold">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="size-2.5"
              aria-hidden="true"
            >
              <path d="M12 2c.7 2.5 2.5 3.5 2.5 6a2.5 2.5 0 0 1-5 0c0-1 .4-1.7 1-2.3C9 7 9 5 12 2zm0 8c3.5 0 6 2.8 6 6.3a6 6 0 1 1-12 0c0-2 1-3.5 2.4-4.5-.1 1.6.7 2.7 1.9 3.3-.7-2.2.7-3.5 1.7-5.1z" />
            </svg>
            {t("publicJobs.board.featured")}
          </span>
        )}
      </div>

      {/* Metadata grid — labeled fields read cleanly on mobile */}
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-xs sm:grid-cols-[auto_1fr_auto_1fr] sm:gap-x-6">
        <dt className="text-white/40">{t("admin.jobs.fields.company")}</dt>
        <dd>
          <button
            type="button"
            onClick={() => {
              onLeavePage?.();
              navigate(`/admin/companies?detail=${job.company_id}`);
            }}
            className="inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-copper/90 transition hover:border-copper/30 hover:bg-copper/10 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-copper/85 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline"
          >
            {companyName ?? t("admin.jobs.companyLabel", { id: job.company_id })}
          </button>
        </dd>
        <dt className="text-white/40">{t("admin.jobs.submittedLabel")}</dt>
        <dd className="text-white/70">{formatDate(job.created_at)}</dd>
        {salaryStr && (
          <>
            <dt className="text-white/40">{t("common.salary")}</dt>
            <dd className="font-medium text-copper/85">{salaryStr}</dd>
          </>
        )}
        <dt className="text-white/40">{t("admin.jobs.candidatesLabel")}</dt>
        <dd className="inline-flex items-center gap-1.5">
          <span className="font-medium text-copper/85">
            {applicationCount == null
              ? "…"
              : applicationCount.capped
                ? `${applicationCount.n}+`
                : applicationCount.n}
          </span>
          {applicationCount != null && applicationCount.n > 0 && (
            <button
              type="button"
              onClick={() => {
                onLeavePage?.();
                navigate(`/admin/applications?job=${job.id}`);
              }}
              className="inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-white/65 transition hover:border-copper/30 hover:bg-copper/10 hover:text-copper sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-white/40 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline"
            >
              {t("admin.jobs.candidatesView")}
            </button>
          )}
        </dd>
      </dl>

      {job.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {job.tags.map((tag) => (
            <span
              key={tag}
              className="rounded-full border border-copper/25 bg-copper/10 px-2.5 py-0.5 text-xs font-medium text-copper/90"
            >
              {tag}
            </span>
          ))}
        </div>
      )}

      {/* Short description: lifted into a subtle well so it doesn't compete with the metadata */}
      <div className="rounded-md border border-white/6 bg-well/30 px-3 py-2.5">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("admin.jobs.fields.shortDescription")}
        </p>
        <p className="mt-1 leading-relaxed text-white/80">{job.short_description}</p>
      </div>

      <CollapsibleSection title={t("admin.jobs.fields.description")}>
        <p className="whitespace-pre-wrap leading-relaxed text-white/75">
          {job.description}
        </p>
      </CollapsibleSection>
      {job.requirements.length > 0 && (
        <CollapsibleSection title={t("admin.jobs.fields.requirements")}>
          <ul className="space-y-1.5 text-white/75">
            {job.requirements.map((req, i) => (
              <li key={i} className="flex items-start gap-2">
                <span
                  aria-hidden="true"
                  className="mt-2 inline-block size-1.5 shrink-0 rounded-full bg-copper/70"
                />
                <span>{req.text}</span>
              </li>
            ))}
          </ul>
        </CollapsibleSection>
      )}
    </div>
  );
}

/**
 * Mobile card with controlled expand/collapse. A dedicated chevron column at
 * the inline-start of the summary row makes the affordance unmissable, the
 * border tints copper when open, and a "סגור" button anchors the bottom of
 * the expanded content so the user can always close without scrolling back up.
 *
 * The expand/collapse uses the grid-template-rows 0fr→1fr trick so the height
 * animates smoothly without us having to measure the content.
 */
function MobileJobCard({
  job,
  statusLabels,
  statusColors,
  companyName,
  actions,
}: {
  job: JobRead;
  statusLabels: Record<string, string>;
  statusColors: Record<string, string>;
  companyName?: string;
  actions: React.ReactNode;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-card transition-colors duration-200 ${
        open ? "border-copper/40 bg-card-raised" : "border-white/8 hover:border-white/15"
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={open ? t("admin.jobs.collapseLabel") : t("admin.jobs.expandLabel")}
        className="flex w-full cursor-pointer items-center gap-3 px-3 py-3 pe-12 text-start active:scale-[0.99]"
      >
        <span
          className={`inline-flex size-7 shrink-0 items-center justify-center rounded-full border transition-colors duration-200 ${
            job.is_featured
              ? open
                ? "border-gold bg-gold/25 text-gold"
                : "border-gold/50 bg-gold/10 text-gold"
              : open
                ? "border-copper bg-copper/15 text-copper"
                : "border-white/15 text-white/45"
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 16 16"
            fill="currentColor"
            className={`size-3.5 transition-transform duration-300 ease-out ${open ? "rotate-180" : ""}`}
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </span>
        <p className="min-w-0 flex-1 truncate font-medium text-white/85">
          {job.title}
        </p>
        <span
          className={`shrink-0 inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium ${statusColors[job.status]}`}
        >
          {statusLabels[job.status]}
        </span>
      </button>
      <div className="absolute end-1 top-2">{actions}</div>
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`border-t border-white/8 px-4 py-4 transition-opacity duration-200 ${
              open ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            <JobDetailBody
              job={job}
              statusLabels={statusLabels}
              statusColors={statusColors}
              companyName={companyName}
            />
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-sm border border-white/15 px-3 py-2 text-xs font-medium text-white/65 transition-colors hover:border-copper/50 hover:text-copper active:scale-[0.99]"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 16 16"
                fill="currentColor"
                className="size-3.5"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M11.78 10.28a.75.75 0 0 1-1.06 0L8 7.56l-2.72 2.72a.75.75 0 1 1-1.06-1.06l3.25-3.25a.75.75 0 0 1 1.06 0l3.25 3.25a.75.75 0 0 1 0 1.06Z"
                  clipRule="evenodd"
                />
              </svg>
              {t("admin.jobs.collapseLabel")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Textarea that auto-grows with its content. Mobile users can't drag the
 * native resize handle, so the box expands as they type instead.
 */
function AutoGrowTextarea({
  value,
  onChange,
  className,
  minRows = 4,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
  minRows?: number;
  placeholder?: string;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);
  return (
    <textarea
      ref={ref}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      rows={minRows}
      placeholder={placeholder}
      className={`${className ?? ""} resize-none overflow-hidden`}
    />
  );
}

/**
 * Tiny diagonal sash anchored to the top-right corner of a desktop title
 * cell. Sits z-above the text so the title doesn't push it out, and small
 * enough that it doesn't visually overlap the title.
 */
function FeaturedDesktopSash() {
  const { t } = useTranslation();
  return (
    <span
      className="pointer-events-none absolute right-0 top-0 z-20 h-7 w-7 overflow-hidden"
      aria-label={t("publicJobs.board.featured")}
    >
      <span
        className="absolute top-1 -right-3 inline-flex w-12 origin-center rotate-45 items-center justify-center bg-gradient-to-r from-copper via-gold to-gold-light py-px text-white shadow-[0_1px_2px_rgba(0,0,0,0.5)]"
      >
        <svg
          viewBox="0 0 24 24"
          fill="currentColor"
          className="size-2.5"
          aria-hidden="true"
        >
          <path d="M12 2.5l3.09 6.26 6.91 1.01-5 4.87 1.18 6.88L12 18.27l-6.18 3.25L7 14.64 2 9.77l6.91-1.01L12 2.5z" />
        </svg>
      </span>
    </span>
  );
}

function FunnelIcon() {
  return (
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
  );
}

function ActiveFilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
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

/**
 * Animated accordion (controlled). Used for the description/requirements
 * sections in the detail view and the form sections inside dialogs.
 *
 * The expand/collapse animates via the `grid-template-rows: 0fr → 1fr` trick
 * so the height transitions smoothly without measuring the content.
 */
function AnimatedAccordion({
  title,
  children,
  defaultOpen = false,
  variant = "card",
}: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  /** "card": copper-bordered surface for detail sections.
   *  "form": divider-only for stacking inside form dialogs. */
  variant?: "card" | "form";
}) {
  const [open, setOpen] = useState(defaultOpen);
  const wrapperCls =
    variant === "card"
      ? "rounded-md border border-white/8 bg-card/40"
      : "border-b border-white/8 pb-3 last:border-b-0";
  const summaryCls =
    variant === "card"
      ? "px-3 py-2.5"
      : "py-2.5";
  const innerCls =
    variant === "card"
      ? "px-3 pb-3 text-sm"
      : "pt-2";
  return (
    <div className={wrapperCls}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className={`flex w-full cursor-pointer items-center justify-between gap-3 text-start text-[10px] font-semibold uppercase tracking-widest text-copper ${summaryCls}`}
      >
        <span>{title}</span>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 16 16"
          fill="currentColor"
          className={`size-3.5 text-white/40 transition-transform duration-300 ease-out ${open ? "rotate-180" : ""}`}
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M4.22 5.72a.75.75 0 0 1 1.06 0L8 8.44l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 6.78a.75.75 0 0 1 0-1.06Z"
            clipRule="evenodd"
          />
        </svg>
      </button>
      <div
        className={`grid transition-[grid-template-rows] duration-300 ease-out ${
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`${innerCls} transition-opacity duration-200 ${
              open ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}

function CollapsibleSection(props: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return <AnimatedAccordion {...props} variant="card" />;
}

function FormSection(props: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  return <AnimatedAccordion {...props} variant="form" />;
}

/** Featured-toggle as a star button. Click opens a confirm dialog in the parent. */
function FeaturedStarButton({
  active,
  onToggleRequest,
}: {
  active: boolean;
  onToggleRequest: () => void;
}) {
  const { t } = useTranslation();
  return (
    <button
      type="button"
      onClick={onToggleRequest}
      aria-pressed={active}
      aria-label={t("admin.jobs.fields.featuredToggleAria")}
      title={t(active ? "admin.jobs.featuredOnHint" : "admin.jobs.featuredOffHint")}
      className={`inline-flex size-10 shrink-0 items-center justify-center rounded-sm border transition duration-200 active:scale-90 ${
        active
          ? "border-gold/60 bg-gold/15 text-gold hover:bg-gold/25"
          : "border-white/15 text-white/40 hover:border-gold/40 hover:text-gold/80"
      }`}
    >
      <svg
        viewBox="0 0 24 24"
        fill={active ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
        className="size-5"
        aria-hidden="true"
      >
        <path d="M12 2.5l3.09 6.26 6.91 1.01-5 4.87 1.18 6.88L12 18.27l-6.18 3.25L7 14.64 2 9.77l6.91-1.01L12 2.5z" />
      </svg>
    </button>
  );
}

/** Status as segmented pills (replaces the dropdown). */
function StatusPills({
  value,
  onChange,
}: {
  value: JobStatus;
  onChange: (s: JobStatus) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="mt-1 flex flex-wrap gap-1.5">
      {ALL_STATUSES.map((s) => {
        const active = value === s;
        return (
          <button
            key={s}
            type="button"
            onClick={() => onChange(s)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition ${
              active
                ? "bg-copper text-white"
                : "border border-white/15 text-white/55 hover:border-white/30 hover:text-white/85"
            }`}
          >
            {t(`admin.jobs.statusLabels.${s}`)}
          </button>
        );
      })}
    </div>
  );
}

const SALARY_FORM_MIN = 0;
const SALARY_FORM_MAX = 60000;
const SALARY_FORM_STEP = 500;

/** Salary range slider + numeric display (replaces two number inputs). */
function SalaryRangeField({
  min,
  max,
  onChange,
  error,
}: {
  min?: number;
  max?: number;
  onChange: (lo: number, hi: number) => void;
  error?: string;
}) {
  const { t } = useTranslation();
  const lo = Math.max(SALARY_FORM_MIN, Math.min(min ?? SALARY_FORM_MIN, SALARY_FORM_MAX));
  const hi = Math.max(
    Math.min(SALARY_FORM_MAX, Math.max(max ?? SALARY_FORM_MAX, SALARY_FORM_MIN)),
    lo,
  );
  return (
    <div className="mt-1 space-y-3 rounded-md border border-white/8 bg-well/40 px-3 pb-3 pt-2.5">
      <p className="text-sm font-medium text-copper/85">
        {lo.toLocaleString("he-IL")}–{hi.toLocaleString("he-IL")} ₪/חודש
      </p>
      <RangeSlider
        min={SALARY_FORM_MIN}
        max={SALARY_FORM_MAX}
        step={SALARY_FORM_STEP}
        value={[lo, hi]}
        onChange={([newLo, newHi]) => onChange(newLo, newHi)}
        formatValue={(n) => `${n.toLocaleString("he-IL")} ₪`}
        ariaLabelMin={t("common.salaryMin")}
        ariaLabelMax={t("common.salaryMax")}
      />
      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  );
}

// ── Edit dialog ────────────────────────────────────────────────────────────

interface EditProps {
  job: JobRead | null;
  onClose: () => void;
  onSaved: (next: JobRead) => void;
  onError: () => void;
}

function EditDialog({ job, onClose, onSaved, onError }: EditProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<JobAdminUpdate>({});
  const [initialForm, setInitialForm] = useState<JobAdminUpdate>({});
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [confirmFeatured, setConfirmFeatured] = useState(false);
  const [pendingStatus, setPendingStatus] = useState<JobStatus | null>(null);
  const [confirmSaveOpen, setConfirmSaveOpen] = useState(false);

  useEffect(() => {
    if (!job) return;
    const seed: JobAdminUpdate = {
      title: job.title,
      short_description: job.short_description,
      description: job.description,
      requirements:
        job.requirements.length > 0
          ? job.requirements.map((r) => ({ text: r.text }))
          : Array.from({ length: JOB_REQ_MIN_COUNT }, () => ({ text: "" })),
      tags: [...job.tags],
      is_featured: job.is_featured,
      location: job.location,
      salary_min: job.salary_min ?? undefined,
      salary_max: job.salary_max ?? undefined,
      status: job.status,
    };
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [job]);

  function set<K extends keyof JobAdminUpdate>(key: K, value: JobAdminUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: "" }));
  }

  const isDirty = JSON.stringify(form) !== JSON.stringify(initialForm);

  function handleClose() {
    if (isDirty) { setConfirmDiscard(true); } else { onClose(); }
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.title?.trim()) e.title = t("common.validation.required");
    else if (form.title.length > 100) e.title = t("common.validation.tooLong", { max: 100 });
    if (!form.short_description?.trim()) e.short_description = t("common.validation.required");
    else if (form.short_description.length > JOB_SHORT_DESC_MAX)
      e.short_description = t("common.validation.tooLong", { max: JOB_SHORT_DESC_MAX });
    if (!form.location?.trim()) e.location = t("common.validation.required");
    else if (form.location.length > 200) e.location = t("common.validation.tooLong", { max: 200 });
    if (!form.description?.trim()) e.description = t("common.validation.required");
    else if (form.description.length > 5000) e.description = t("common.validation.tooLong", { max: 5000 });
    const reqs = form.requirements ?? [];
    const filledReqs = reqs.filter((r) => r.text.trim().length > 0);
    if (filledReqs.length < JOB_REQ_MIN_COUNT)
      e.requirements = t("common.validation.requirementsMin", { min: JOB_REQ_MIN_COUNT });
    if (form.salary_min == null || form.salary_min < 0) e.salary_min = t("common.validation.required");
    if (form.salary_max == null || form.salary_max < 0) e.salary_max = t("common.validation.required");
    else if (form.salary_min != null && form.salary_max < form.salary_min) e.salary_max = t("common.validation.salaryMaxBelowMin");
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, JOB_EDIT_FIELD_ORDER);
      return false;
    }
    return true;
  }

  function requestSave() {
    if (!job || !validate()) return;
    // Nothing actually changed — skip the confirm + API call and just close.
    if (!isDirty) {
      onClose();
      return;
    }
    setConfirmSaveOpen(true);
  }

  async function executeSave() {
    if (!job) return;
    setConfirmSaveOpen(false);
    setSaving(true);
    try {
      const payload: JobAdminUpdate = {
        ...form,
        requirements: (form.requirements ?? [])
          .map((r) => ({ text: r.text.trim() }))
          .filter((r) => r.text.length > 0),
      };
      const updated = await updateJob(job.id, payload);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  if (!job) return null;
  return (
    <>
      <Dialog
        open={job != null}
        onOpenChange={(o) => !o && handleClose()}
        title={t("admin.jobs.editModalTitle")}
        description={job.title}
        size="lg"
        preventOutsideClose
        footer={
          <>
            <button
              onClick={handleClose}
              disabled={saving}
              className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/60 hover:border-white/40 hover:text-white/90 disabled:opacity-60"
            >
              {t("common.cancel")}
            </button>
            <button
              onClick={requestSave}
              disabled={saving || !isDirty}
              className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? t("common.saving") : t("common.save")}
            </button>
          </>
        }
      >
        <div className="space-y-2 text-sm">
          <FormSection title={t("admin.jobs.formSections.basics")} defaultOpen>
            <div className="space-y-3">
              <Field label={t("admin.jobs.fields.title")} full name="title">
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={form.title ?? ""}
                    onChange={(e) => set("title", e.target.value)}
                    className={`${inputCls} flex-1`}
                  />
                  <FeaturedStarButton
                    active={form.is_featured ?? false}
                    onToggleRequest={() => setConfirmFeatured(true)}
                  />
                </div>
                {errors.title && <p className="mt-1 text-xs text-danger">{errors.title}</p>}
              </Field>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label={t("admin.jobs.fields.location")} name="location">
                  <input
                    type="text"
                    value={form.location ?? ""}
                    onChange={(e) => set("location", e.target.value)}
                    className={inputCls}
                  />
                  {errors.location && <p className="mt-1 text-xs text-danger">{errors.location}</p>}
                </Field>
                <Field label={t("admin.jobs.fields.status")}>
                  <StatusPills
                    value={(form.status ?? job.status) as JobStatus}
                    onChange={(s) => {
                      if (s === (form.status ?? job.status)) return;
                      setPendingStatus(s);
                    }}
                  />
                </Field>
              </div>
              <Field
                label={t("admin.jobs.fields.salaryRange")}
                full
                name="salary_min"
              >
                <SalaryRangeField
                  min={form.salary_min}
                  max={form.salary_max}
                  onChange={(lo, hi) => {
                    set("salary_min", lo);
                    set("salary_max", hi);
                  }}
                  error={errors.salary_min || errors.salary_max}
                />
              </Field>
            </div>
          </FormSection>
          <FormSection title={t("admin.jobs.formSections.content")}>
            <div className="space-y-3">
              <Field
                label={t("admin.jobs.fields.shortDescription")}
                full
                name="short_description"
              >
                <input
                  type="text"
                  maxLength={JOB_SHORT_DESC_MAX}
                  value={form.short_description ?? ""}
                  onChange={(e) => set("short_description", e.target.value)}
                  className={inputCls}
                />
                <p className="mt-1 text-[11px] text-white/35">
                  {t("admin.jobs.fields.shortDescriptionHint", {
                    count: (form.short_description ?? "").length,
                    max: JOB_SHORT_DESC_MAX,
                  })}
                </p>
                {errors.short_description && <p className="mt-1 text-xs text-danger">{errors.short_description}</p>}
              </Field>
              <Field
                label={t("admin.jobs.fields.description")}
                full
                name="description"
              >
                <AutoGrowTextarea
                  value={form.description ?? ""}
                  onChange={(v) => set("description", v)}
                  minRows={6}
                  className={`${textareaCls} min-h-40`}
                />
                {errors.description && <p className="mt-1 text-xs text-danger">{errors.description}</p>}
              </Field>
            </div>
          </FormSection>
          <FormSection title={t("admin.jobs.formSections.lists")}>
            <div className="space-y-3">
              <Field
                label={t("admin.jobs.fields.requirements")}
                full
                name="requirements"
              >
                <JobRequirementsInput
                  value={form.requirements ?? []}
                  onChange={(reqs: JobRequirementItem[]) => set("requirements", reqs)}
                  error={errors.requirements}
                />
              </Field>
              <Field label={t("admin.jobs.fields.tags")} full>
                <JobTagsInput
                  value={form.tags ?? []}
                  onChange={(tags) => set("tags", tags)}
                  error={errors.tags}
                />
              </Field>
            </div>
          </FormSection>
        </div>
      </Dialog>
      <ConfirmDialog
        open={confirmDiscard}
        onOpenChange={(o) => !o && setConfirmDiscard(false)}
        title={t("common.discardTitle")}
        message={t("common.discardMessage")}
        cancelLabel={t("common.continueEditing")}
        confirmLabel={t("common.discard")}
        variant="danger"
        onConfirm={() => { setConfirmDiscard(false); onClose(); }}
      />
      <ConfirmDialog
        open={confirmFeatured}
        onOpenChange={(o) => !o && setConfirmFeatured(false)}
        title={
          form.is_featured
            ? t("admin.jobs.featuredUnsetTitle")
            : t("admin.jobs.featuredSetTitle")
        }
        message={
          form.is_featured
            ? t("admin.jobs.featuredUnsetMessage")
            : t("admin.jobs.featuredSetMessage")
        }
        confirmLabel={t("common.confirm")}
        onConfirm={() => {
          set("is_featured", !(form.is_featured ?? false));
          setConfirmFeatured(false);
        }}
      />
      <ConfirmDialog
        open={pendingStatus !== null}
        onOpenChange={(o) => !o && setPendingStatus(null)}
        title={t("admin.jobs.statusChangeConfirmTitle")}
        message={t("admin.jobs.statusChangeConfirmMessage")}
        confirmLabel={t("common.confirm")}
        onConfirm={() => {
          if (pendingStatus) set("status", pendingStatus);
          setPendingStatus(null);
        }}
      />
      <ConfirmDialog
        open={confirmSaveOpen}
        onOpenChange={(o) => !o && setConfirmSaveOpen(false)}
        title={t("admin.jobs.saveConfirmTitle")}
        message={t("admin.jobs.saveConfirmMessage")}
        confirmLabel={t("common.save")}
        onConfirm={executeSave}
      />
    </>
  );
}

// ── Create dialog ──────────────────────────────────────────────────────────

interface CreateProps {
  open: boolean;
  onClose: () => void;
  onCreated: (job: JobRead) => void;
  onError: () => void;
}

const emptyRequirements = (): JobRequirementItem[] =>
  Array.from({ length: JOB_REQ_MIN_COUNT }, () => ({ text: "" }));

function CreateDialog({ open, onClose, onCreated, onError }: CreateProps) {
  const { t } = useTranslation();
  const [companies, setCompanies] = useState<ActiveCompanyRead[] | null>(null);
  const [companiesError, setCompaniesError] = useState(false);
  const [form, setForm] = useState<Partial<JobAdminCreate>>({
    title: "",
    short_description: "",
    description: "",
    requirements: emptyRequirements(),
    tags: [],
    is_featured: false,
    location: "",
    status: JobStatus.PUBLISHED,
    salary_min: undefined,
    salary_max: undefined,
  });
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmFeatured, setConfirmFeatured] = useState(false);
  const [confirmSaveOpen, setConfirmSaveOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setCompanies(null);
    setCompaniesError(false);
    setErrors({});
    setForm({
      title: "",
      short_description: "",
      description: "",
      requirements: emptyRequirements(),
      tags: [],
      is_featured: false,
      location: "",
      status: JobStatus.PUBLISHED,
      salary_min: undefined,
      salary_max: undefined,
    });
    /* eslint-enable react-hooks/set-state-in-effect */
    getActiveCompanies({ limit: 100 }, ctrl.signal)
      .then((page) => {
        setCompanies(page.items);
        if (page.items.length > 0) {
          setForm((prev) => ({
            ...prev,
            company_id: page.items[0].company_profile.id,
          }));
        }
      })
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setCompaniesError(true);
      });
    return () => ctrl.abort();
  }, [open]);

  function set<K extends keyof JobAdminCreate>(key: K, value: JobAdminCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[String(key)]) setErrors((prev) => ({ ...prev, [String(key)]: "" }));
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.title?.trim()) e.title = t("common.validation.required");
    else if (form.title.length > 100) e.title = t("common.validation.tooLong", { max: 100 });
    if (!form.short_description?.trim()) e.short_description = t("common.validation.required");
    else if (form.short_description.length > JOB_SHORT_DESC_MAX)
      e.short_description = t("common.validation.tooLong", { max: JOB_SHORT_DESC_MAX });
    if (!form.location?.trim()) e.location = t("common.validation.required");
    else if (form.location.length > 200) e.location = t("common.validation.tooLong", { max: 200 });
    if (!form.description?.trim()) e.description = t("common.validation.required");
    else if (form.description.length > 5000) e.description = t("common.validation.tooLong", { max: 5000 });
    const filledReqs = (form.requirements ?? []).filter((r) => r.text.trim().length > 0);
    if (filledReqs.length < JOB_REQ_MIN_COUNT)
      e.requirements = t("common.validation.requirementsMin", { min: JOB_REQ_MIN_COUNT });
    if (form.salary_min == null || form.salary_min < 0) e.salary_min = t("common.validation.required");
    if (form.salary_max == null || form.salary_max < 0) e.salary_max = t("common.validation.required");
    else if (form.salary_min != null && form.salary_max < form.salary_min) e.salary_max = t("common.validation.salaryMaxBelowMin");
    setErrors(e);
    if (Object.keys(e).length > 0) {
      focusFirstError(e, JOB_CREATE_FIELD_ORDER);
      return false;
    }
    return true;
  }

  function requestSave() {
    if (!form.company_id || !validate()) return;
    setConfirmSaveOpen(true);
  }

  async function executeSave() {
    if (!form.company_id) return;
    setConfirmSaveOpen(false);
    setSaving(true);
    try {
      const created = await createJob({
        company_id: form.company_id,
        title: form.title!,
        short_description: form.short_description!,
        description: form.description!,
        requirements: (form.requirements ?? [])
          .map((r) => ({ text: r.text.trim() }))
          .filter((r) => r.text.length > 0),
        tags: form.tags ?? [],
        is_featured: form.is_featured ?? false,
        location: form.location!,
        salary_min: form.salary_min!,
        salary_max: form.salary_max!,
        status: form.status,
      });
      onCreated(created);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.jobs.newJobModalTitle")}
      size="lg"
      preventOutsideClose
      footer={
        <>
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/60 hover:border-white/40 hover:text-white/90 disabled:opacity-60"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={requestSave}
            disabled={saving}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {saving ? t("common.saving") : t("common.save")}
          </button>
        </>
      }
    >
      <div className="space-y-2 text-sm">
        <FormSection title={t("admin.jobs.formSections.basics")} defaultOpen>
          <div className="space-y-3">
            <Field label={t("admin.jobs.fields.company")} full name="company_id">
              {companiesError ? (
                <p className="text-xs text-danger">
                  {t("admin.jobs.errors.companiesLoadFailed")}
                </p>
              ) : companies == null ? (
                <p className="text-xs text-white/35">{t("common.loading")}</p>
              ) : (
                <select
                  value={form.company_id ?? ""}
                  onChange={(e) => set("company_id", Number(e.target.value))}
                  className={selectCls}
                >
                  {companies.map((row) => (
                    <option
                      key={row.company_profile.id}
                      value={row.company_profile.id}
                      className="bg-well"
                    >
                      {row.company_profile.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            <Field label={t("admin.jobs.fields.title")} full name="title">
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={form.title ?? ""}
                  onChange={(e) => set("title", e.target.value)}
                  className={`${inputCls} flex-1`}
                />
                <FeaturedStarButton
                  active={form.is_featured ?? false}
                  onToggleRequest={() => setConfirmFeatured(true)}
                />
              </div>
              {errors.title && <p className="mt-1 text-xs text-danger">{errors.title}</p>}
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label={t("admin.jobs.fields.location")} name="location">
                <input
                  type="text"
                  value={form.location ?? ""}
                  onChange={(e) => set("location", e.target.value)}
                  className={inputCls}
                />
                {errors.location && <p className="mt-1 text-xs text-danger">{errors.location}</p>}
              </Field>
              <Field label={t("admin.jobs.fields.status")}>
                <StatusPills
                  value={(form.status ?? JobStatus.PUBLISHED) as JobStatus}
                  onChange={(s) => set("status", s)}
                />
              </Field>
            </div>
            <Field
              label={t("admin.jobs.fields.salaryRange")}
              full
              name="salary_min"
            >
              <SalaryRangeField
                min={form.salary_min}
                max={form.salary_max}
                onChange={(lo, hi) => {
                  setForm((prev) => ({ ...prev, salary_min: lo, salary_max: hi }));
                }}
                error={errors.salary_min || errors.salary_max}
              />
            </Field>
          </div>
        </FormSection>
        <FormSection title={t("admin.jobs.formSections.content")}>
          <div className="space-y-3">
            <Field
              label={t("admin.jobs.fields.shortDescription")}
              full
              name="short_description"
            >
              <input
                type="text"
                maxLength={JOB_SHORT_DESC_MAX}
                value={form.short_description ?? ""}
                onChange={(e) => set("short_description", e.target.value)}
                className={inputCls}
              />
              <p className="mt-1 text-[11px] text-white/35">
                {t("admin.jobs.fields.shortDescriptionHint", {
                  count: (form.short_description ?? "").length,
                  max: JOB_SHORT_DESC_MAX,
                })}
              </p>
              {errors.short_description && <p className="mt-1 text-xs text-danger">{errors.short_description}</p>}
            </Field>
            <Field
              label={t("admin.jobs.fields.description")}
              full
              name="description"
            >
              <AutoGrowTextarea
                value={form.description ?? ""}
                onChange={(v) => set("description", v)}
                minRows={6}
                className={`${textareaCls} min-h-40`}
              />
              {errors.description && <p className="mt-1 text-xs text-danger">{errors.description}</p>}
            </Field>
          </div>
        </FormSection>
        <FormSection title={t("admin.jobs.formSections.lists")}>
          <div className="space-y-3">
            <Field
              label={t("admin.jobs.fields.requirements")}
              full
              name="requirements"
            >
              <JobRequirementsInput
                value={form.requirements ?? []}
                onChange={(reqs) => set("requirements", reqs)}
                error={errors.requirements}
              />
            </Field>
            <Field label={t("admin.jobs.fields.tags")} full>
              <JobTagsInput
                value={form.tags ?? []}
                onChange={(tags) => set("tags", tags)}
                error={errors.tags}
              />
            </Field>
          </div>
        </FormSection>
      </div>
    </Dialog>
    <ConfirmDialog
      open={confirmFeatured}
      onOpenChange={(o) => !o && setConfirmFeatured(false)}
      title={
        form.is_featured
          ? t("admin.jobs.featuredUnsetTitle")
          : t("admin.jobs.featuredSetTitle")
      }
      message={
        form.is_featured
          ? t("admin.jobs.featuredUnsetMessage")
          : t("admin.jobs.featuredSetMessage")
      }
      confirmLabel={t("common.confirm")}
      onConfirm={() => {
        setForm((prev) => ({ ...prev, is_featured: !(prev.is_featured ?? false) }));
        setConfirmFeatured(false);
      }}
    />
    <ConfirmDialog
      open={confirmSaveOpen}
      onOpenChange={(o) => !o && setConfirmSaveOpen(false)}
      title={t("admin.jobs.saveConfirmTitle")}
      message={t("admin.jobs.saveConfirmMessage")}
      confirmLabel={t("common.save")}
      onConfirm={executeSave}
    />
    </>
  );
}

// ── Field helper ───────────────────────────────────────────────────────────

function Field({
  label,
  children,
  full,
  name,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
  name?: string;
}) {
  return (
    <label
      className={`block ${full ? "sm:col-span-2" : ""}`}
      data-field={name}
    >
      <span className="block text-xs text-white/45">{label}</span>
      <span className="mt-1 block">{children}</span>
    </label>
  );
}
