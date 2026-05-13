import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import axios from "axios";
import { apiErrorKey } from "@/utils/apiError";
import {
  deleteCandidate,
  fetchResumeBlob,
  getActiveCompanies,
  getApplications,
  getCandidate,
  getCandidates,
  getJobs,
  updateCandidate,
} from "@/services/admin";
import type {
  ApplicationWithDetails,
  CandidateProfileRead,
  CandidateProfileUpdate,
} from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import Dialog from "@/components/ui/Dialog";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import TableSkeleton from "@/components/ui/TableSkeleton";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SearchInput from "@/components/ui/SearchInput";
import MobileEntityCard from "@/components/admin/MobileEntityCard";
import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import FunnelIcon from "@/components/admin/FunnelIcon";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import { useDebounce } from "@/hooks/useDebounce";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { inputCls, textareaCls } from "@/styles/forms";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function ResumeLink({ fileKey, label }: { fileKey: string; label: string }) {
  const [isLoading, setIsLoading] = useState(false);
  async function open(e: React.MouseEvent) {
    e.stopPropagation();
    if (isLoading) return;
    setIsLoading(true);
    try {
      const blob = await fetchResumeBlob(fileKey);
      const url = URL.createObjectURL(blob);
      const win = window.open(url, "_blank");
      if (!win) {
        const link = document.createElement("a");
        link.href = url;
        link.download = fileKey;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (err) {
      console.error("Failed to fetch resume", err);
    } finally {
      setIsLoading(false);
    }
  }
  return (
    <button
      onClick={open}
      disabled={isLoading}
      className={`text-copper hover:text-gold transition-opacity ${isLoading ? "opacity-50 cursor-wait" : ""}`}
    >
      {isLoading ? "טוען..." : `${label} ↗`}
    </button>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminCandidatesPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.candidates.title"));
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<CandidateProfileRead>> =>
      getCandidates({ cursor }),
    [],
  );

  const {
    items: candidates,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<CandidateProfileRead>(fetcher);

  const [detail, setDetail] = useState<CandidateProfileRead | null>(null);
  const [editing, setEditing] = useState<CandidateProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<CandidateProfileRead | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);

  // Client-side filters on the loaded candidate set.
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [filterOpen, setFilterOpen] = useState(false);
  const [jobFilter, setJobFilter] = useState<number[]>([]);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);

  // Cache jobs + companies for the filter selects, and applications for the
  // candidate→job / candidate→company lookup.
  const [allJobs, setAllJobs] = useState<{ id: number; title: string; company_id: number }[]>([]);
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [jobTitleById, setJobTitleById] = useState<Map<number, string>>(
    new Map(),
  );
  const [appCache, setAppCache] = useState<ApplicationWithDetails[]>([]);
  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      getJobs({ limit: 100 }, ctrl.signal),
      getActiveCompanies({ limit: 100 }, ctrl.signal),
      getApplications({ limit: 100 }, ctrl.signal),
    ])
      .then(([jobsPage, companiesPage, appsPage]) => {
        setAllJobs(
          jobsPage.items.map((j) => ({
            id: j.id,
            title: j.title,
            company_id: j.company_id,
          })),
        );
        setJobTitleById(new Map(jobsPage.items.map((j) => [j.id, j.title])));
        setCompanyNameById(
          new Map(
            companiesPage.items.map((row) => [
              row.company_profile.id,
              row.company_profile.name,
            ]),
          ),
        );
        setAppCache(appsPage.items);
      })
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  // candidate_id → set of job IDs / company IDs they applied to.
  const candidateAppliedJobs = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const a of appCache) {
      if (!map.has(a.candidate_id)) map.set(a.candidate_id, new Set());
      map.get(a.candidate_id)!.add(a.job_id);
    }
    return map;
  }, [appCache]);

  const candidateAppliedCompanies = useMemo(() => {
    const map = new Map<number, Set<number>>();
    for (const a of appCache) {
      if (!map.has(a.candidate_id)) map.set(a.candidate_id, new Set());
      map.get(a.candidate_id)!.add(a.job.company_id);
    }
    return map;
  }, [appCache]);

  const filteredCandidates = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    return candidates.filter((c) => {
      if (jobFilter.length > 0) {
        const jobs = candidateAppliedJobs.get(c.id);
        if (!jobs || !jobFilter.some((id) => jobs.has(id))) return false;
      }
      if (companyFilter.length > 0) {
        const companies = candidateAppliedCompanies.get(c.id);
        if (!companies || !companyFilter.some((id) => companies.has(id))) return false;
      }
      if (!q) return true;
      return [c.full_name, c.email, c.phone ?? "", c.linkedin_url ?? ""].some((s) =>
        s.toLowerCase().includes(q),
      );
    });
  }, [
    candidates,
    debouncedQuery,
    jobFilter,
    companyFilter,
    candidateAppliedJobs,
    candidateAppliedCompanies,
  ]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    jobFilter.length +
    companyFilter.length;


  // Auto-open detail modal when navigated from another page via ?detail=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    const ctrl = new AbortController();
    window.history.replaceState({}, "", window.location.pathname);
    getCandidate(Number(id), ctrl.signal)
      .then((c) => setDetail(c))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        toast.error(t(apiErrorKey(e)));
      });
    return () => ctrl.abort();
  }, [t, toast]);

  async function handleDeleteConfirm() {
    if (!deletePending) return;
    setPendingDelete(true);
    try {
      await deleteCandidate(deletePending.id);
      removeItem((c) => c.id === deletePending.id);
      toast.success(t("admin.candidates.deletedToast"));
      setDeletePending(null);
      setDetail(null);
    } catch {
      toast.error(t("admin.candidates.errors.deleteFailed"));
    } finally {
      setPendingDelete(false);
    }
  }

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin.candidates.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin.candidates.title")}
        subtitle={t("admin.candidates.subtitle")}
      />

      {/* Search + filter trigger */}
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin.candidates.searchPlaceholder")}
            clearable
          />
        </div>
        <button
          type="button"
          onClick={() => setFilterOpen((o) => !o)}
          aria-expanded={filterOpen}
          aria-label={t("admin.candidates.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            filterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin.candidates.filters")}</span>
          {activeFilterCount > 0 && (
            <span className="inline-flex size-5 items-center justify-center rounded-full bg-copper text-[10px] font-semibold text-white">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {activeFilterCount > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common.search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {jobFilter.map((id) => (
            <ActiveFilterChip
              key={`job-${id}`}
              label={`${t("admin.candidates.filterByJob")}: ${jobTitleById.get(id) ?? `#${id}`}`}
              onRemove={() => setJobFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin.candidates.filterByCompany")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
        </div>
      )}

      <div
        className={`mb-4 grid transition-[grid-template-rows] duration-300 ease-out ${
          filterOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="overflow-hidden">
          <div
            className={`grid grid-cols-1 gap-3 rounded-md border border-white/8 bg-card/40 p-4 transition-opacity duration-200 sm:grid-cols-2 ${
              filterOpen ? "opacity-100 delay-100" : "opacity-0"
            }`}
          >
            {/* Company first → in RTL it lands on the visual right */}
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
                {t("admin.candidates.filterByCompany")}
              </p>
              <SearchableMultiSelect<number>
                values={companyFilter}
                onChange={(next) => {
                  setCompanyFilter(next);
                  if (next.length > 0 && jobFilter.length > 0) {
                    const allowed = new Set(
                      allJobs
                        .filter((j) => next.includes(j.company_id))
                        .map((j) => j.id),
                    );
                    setJobFilter((prev) => prev.filter((id) => allowed.has(id)));
                  }
                }}
                options={Array.from(companyNameById.entries()).map(([id, name]) => ({
                  value: id,
                  label: name,
                }))}
                placeholder={t("admin.candidates.allCompanies")}
              />
            </div>
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
                {t("admin.candidates.filterByJob")}
              </p>
              <SearchableMultiSelect<number>
                values={jobFilter}
                onChange={setJobFilter}
                options={allJobs
                  .filter(
                    (j) =>
                      companyFilter.length === 0 ||
                      companyFilter.includes(j.company_id),
                  )
                  .map((j) => ({ value: j.id, label: j.title }))}
                placeholder={t("admin.candidates.allJobs")}
              />
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
        <ErrorState message={t("admin.candidates.loadError")} onRetry={reload} />
      ) : candidates.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.candidates.title")}
          headline={t("admin.candidates.empty")}
        />
      ) : filteredCandidates.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-16 text-center">
          <p className="text-sm text-white/40">
            {t("publicJobs.board.noResults")}
          </p>
        </div>
      ) : (
        <>
          {/* Mobile cards — tap to expand inline; 3-dot menu for actions */}
          <div className="space-y-2 md:hidden">
            {filteredCandidates.map((c) => {
              const actions = (
                <DropdownMenu
                  ariaLabel={t("admin.candidates.rowActionsLabel")}
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
                  <DropdownMenuItem onSelect={() => setEditing(c)}>
                    {t("admin.candidates.editAction")}
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onSelect={() =>
                      window.open(
                        `mailto:${c.email}?subject=${encodeURIComponent(
                          t("admin.candidates.emailSubject", { name: c.full_name }),
                        )}`,
                        "_self",
                      )
                    }
                  >
                    {t("admin.candidates.emailAction")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="danger"
                    onSelect={() => setDeletePending(c)}
                  >
                    {t("admin.candidates.deleteAction")}
                  </DropdownMenuItem>
                </DropdownMenu>
              );
              return (
                <MobileEntityCard
                  key={c.id}
                  title={<span className="truncate text-white/85">{c.full_name}</span>}
                  badge={
                    <span className="text-[11px] text-white/40">
                      {formatDate(c.created_at)}
                    </span>
                  }
                  actions={actions}
                >
                  <CandidateDetailBody candidate={c} />
                </MobileEntityCard>
              );
            })}
          </div>

          {/* Desktop table */}
          <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin.candidates.table.name")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.candidates.table.phone")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.candidates.table.resume")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.candidates.table.linkedin")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.candidates.table.date")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {filteredCandidates.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setDetail(c)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white/85">{c.full_name}</p>
                      <p className="text-xs text-white/40">{c.email}</p>
                    </td>
                    <td className="px-4 py-3 text-white/60">
                      {c.phone ?? <span className="text-white/20">—</span>}
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {c.resume_path ? (
                        <ResumeLink
                          fileKey={c.resume_path.split("/").pop() ?? c.resume_path}
                          label={t("admin.candidates.table.resume")}
                        />
                      ) : (
                        <span className="text-white/20">
                          {t("admin.candidates.noFile")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      {c.linkedin_url ? (
                        <a
                          href={c.linkedin_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-copper hover:text-gold"
                        >
                          LinkedIn ↗
                        </a>
                      ) : (
                        <span className="text-white/20">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(c.created_at)}
                    </td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu
                        ariaLabel={t("admin.candidates.rowActionsLabel")}
                        trigger={
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:bg-white/8 hover:text-white/80"
                          >
                            <span aria-hidden>⋮</span>
                          </button>
                        }
                      >
                        <DropdownMenuItem onSelect={() => setDetail(c)}>
                          {t("admin.candidates.viewAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setEditing(c)}>
                          {t("admin.candidates.editAction")}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setDeletePending(c)}
                        >
                          {t("admin.candidates.deleteAction")}
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
        candidate={detail}
        onClose={() => setDetail(null)}
        onEdit={() => {
          if (detail) setEditing(detail);
          setDetail(null);
        }}
        onDelete={() => {
          if (detail) setDeletePending(detail);
          setDetail(null);
        }}
      />

      <EditDialog
        candidate={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          updateItem((c) => c.id === updated.id, updated);
          toast.success(t("admin.candidates.savedToast"));
          setEditing(null);
        }}
        onError={() => toast.error(t("admin.candidates.errors.saveFailed"))}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin.candidates.deleteConfirmTitle", { name: deletePending?.full_name ?? "" })}
        message={t("admin.candidates.deleteConfirmMessage")}
        confirmLabel={t("admin.candidates.deleteConfirmYes")}
        variant="danger"
        isPending={pendingDelete}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

// ── Detail dialog ──────────────────────────────────────────────────────────

interface DetailProps {
  candidate: CandidateProfileRead | null;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function DetailDialog({ candidate, onClose, onEdit, onDelete }: DetailProps) {
  const { t } = useTranslation();
  const [applications, setApplications] = useState<ApplicationWithDetails[] | null>(
    null,
  );
  const [appsError, setAppsError] = useState(false);

  useEffect(() => {
    // Reset state when the target candidate changes — the only sane way to
    // clear the previous candidate's applications before fetching the new
    // one's. setState-in-effect is intentional here.
    /* eslint-disable react-hooks/set-state-in-effect */
    if (!candidate) {
      setApplications(null);
      setAppsError(false);
      return;
    }
    const ctrl = new AbortController();
    setApplications(null);
    setAppsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getApplications({ candidate_id: candidate.id, limit: 100 }, ctrl.signal)
      .then((page) => setApplications(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setAppsError(true);
      });
    return () => ctrl.abort();
  }, [candidate]);

  if (!candidate) return null;
  const c = candidate;

  return (
    <Dialog
      open={candidate != null}
      onOpenChange={(o) => !o && onClose()}
      title={c.full_name}
      description={c.email}
      size="lg"
      footer={
        <>
          <button
            onClick={onDelete}
            className="rounded-sm border border-danger/40 px-4 py-2 text-sm text-danger hover:bg-danger/10"
          >
            {t("admin.candidates.deleteAction")}
          </button>
          <button
            onClick={onEdit}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("admin.candidates.editAction")}
          </button>
        </>
      }
    >
      <CandidateDetailBody
        candidate={c}
        applications={applications}
        appsError={appsError}
        onLeavePage={onClose}
      />
    </Dialog>
  );
}

/** Detail body shared by the desktop dialog and the mobile inline expansion. */
function CandidateDetailBody({
  candidate,
  applications: appsProp,
  appsError: appsErrorProp,
  onLeavePage,
}: {
  candidate: CandidateProfileRead;
  applications?: ApplicationWithDetails[] | null;
  appsError?: boolean;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const c = candidate;
  const hasAnswers =
    c.service_concept ||
    c.salary_expectations ||
    c.personality_strength ||
    c.personality_weakness;

  // Self-fetch the applications list when the parent didn't pass one (mobile).
  const useLocal = appsProp === undefined;
  const [localApps, setLocalApps] = useState<ApplicationWithDetails[] | null>(null);
  const [localAppsError, setLocalAppsError] = useState(false);
  useEffect(() => {
    if (!useLocal) return;
    const ctrl = new AbortController();
    /* eslint-disable react-hooks/set-state-in-effect */
    setLocalApps(null);
    setLocalAppsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getApplications({ candidate_id: candidate.id, limit: 100 }, ctrl.signal)
      .then((page) => setLocalApps(page.items))
      .catch((e) => {
        if (axios.isCancel(e)) return;
        setLocalAppsError(true);
      });
    return () => ctrl.abort();
  }, [candidate.id, useLocal]);
  const applications = useLocal ? localApps : appsProp;
  const appsError = useLocal ? localAppsError : (appsErrorProp ?? false);

  return (
    <div className="space-y-5 text-sm">
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <a
          href={`mailto:${c.email}?subject=${encodeURIComponent(t("admin.candidates.emailSubject", { name: c.full_name }))}`}
          className="text-copper/85 transition hover:text-copper hover:underline"
        >
          {c.email}
        </a>
        {c.phone && <span className="text-white/60">{c.phone}</span>}
        {c.linkedin_url && (
          <a
            href={c.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-copper hover:text-gold"
          >
            LinkedIn ↗
          </a>
        )}
        {c.resume_path ? (
          <ResumeLink
            fileKey={c.resume_path.split("/").pop() ?? c.resume_path}
            label={t("admin.candidates.table.resume")}
          />
        ) : (
          <span className="text-white/40">
            {t("admin.candidates.table.resume")}: {t("admin.candidates.noFile")}
          </span>
        )}
      </div>

      {hasAnswers && (
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
          {c.service_concept && (
            <>
              <dt className="text-white/35">
                {t("admin.candidates.details.serviceConcept")}
              </dt>
              <dd className="text-white/70">{c.service_concept}</dd>
            </>
          )}
          {c.salary_expectations && (
            <>
              <dt className="text-white/35">
                {t("admin.candidates.details.salaryExpectations")}
              </dt>
              <dd className="text-white/70">{c.salary_expectations}</dd>
            </>
          )}
          {c.personality_strength && (
            <>
              <dt className="text-white/35">
                {t("admin.candidates.details.strength")}
              </dt>
              <dd className="text-white/70">{c.personality_strength}</dd>
            </>
          )}
          {c.personality_weakness && (
            <>
              <dt className="text-white/35">
                {t("admin.candidates.details.weakness")}
              </dt>
              <dd className="text-white/70">{c.personality_weakness}</dd>
            </>
          )}
        </dl>
      )}

      <div className="border-t border-white/8 pt-4">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
          {t("admin.candidates.applicationsSection")}
        </p>
        {appsError ? (
          <p className="mt-3 text-xs text-danger">
            {t("admin.candidates.errors.applicationsLoadFailed")}
          </p>
        ) : applications == null ? (
          <p className="mt-3 text-xs text-white/35">{t("common.loading")}</p>
        ) : applications.length === 0 ? (
          <p className="mt-3 text-xs text-white/35">
            {t("admin.candidates.noApplications")}
          </p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {applications.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => {
                    onLeavePage?.();
                    navigate(`/admin/applications?candidate=${a.candidate_id}`, {
                      state: { autoOpen: a },
                    });
                  }}
                  className="flex w-full items-center justify-between rounded-sm border border-white/6 bg-card px-3 py-2 transition hover:border-copper/25 hover:bg-card-raised"
                >
                  <span className="text-white/80">{a.job.title}</span>
                  <span className="text-xs text-white/40">
                    {t(`admin.applications.statusLabels.${a.status}`)} ·{" "}
                    {formatDate(a.created_at)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ── Edit dialog ────────────────────────────────────────────────────────────

interface EditProps {
  candidate: CandidateProfileRead | null;
  onClose: () => void;
  onSaved: (next: CandidateProfileRead) => void;
  onError: () => void;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_RE = /^[+\d\s().-]{5,20}$/;

function EditDialog({ candidate, onClose, onSaved, onError }: EditProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<CandidateProfileUpdate>({});
  const [initialForm, setInitialForm] = useState<CandidateProfileUpdate>({});
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  useEffect(() => {
    if (!candidate) return;
    const seed: CandidateProfileUpdate = {
      full_name: candidate.full_name,
      email: candidate.email,
      phone: candidate.phone ?? "",
      linkedin_url: candidate.linkedin_url ?? "",
      service_concept: candidate.service_concept ?? "",
      salary_expectations: candidate.salary_expectations ?? "",
      personality_strength: candidate.personality_strength ?? "",
      personality_weakness: candidate.personality_weakness ?? "",
    };
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm(seed);
    setInitialForm(seed);
    setErrors({});
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [candidate]);

  function set<K extends keyof CandidateProfileUpdate>(key: K, value: CandidateProfileUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key as string]) setErrors((prev) => ({ ...prev, [key as string]: "" }));
  }

  const isDirty = JSON.stringify(form) !== JSON.stringify(initialForm);

  function handleClose() {
    if (isDirty) { setConfirmDiscard(true); } else { onClose(); }
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!form.full_name?.trim()) e.full_name = t("common.validation.required");
    else if (form.full_name.trim().length < 2) e.full_name = t("common.validation.tooShort", { min: 2 });
    else if (form.full_name.length > 100) e.full_name = t("common.validation.tooLong", { max: 100 });
    if (!form.email?.trim()) e.email = t("common.validation.required");
    else if (!EMAIL_RE.test(form.email)) e.email = t("common.validation.emailInvalid");
    if (!form.phone?.trim()) e.phone = t("common.validation.required");
    else if (!PHONE_RE.test(form.phone.trim())) {
      e.phone = t("common.validation.phoneInvalid");
    }
    if (form.linkedin_url?.trim()) {
      try {
        const url = new URL(form.linkedin_url);
        if (!url.hostname.endsWith("linkedin.com")) e.linkedin_url = t("common.validation.linkedinInvalid");
      } catch {
        e.linkedin_url = t("common.validation.linkedinInvalid");
      }
    }
    const textFields = ["service_concept", "salary_expectations", "personality_strength", "personality_weakness"] as const;
    for (const f of textFields) {
      if ((form[f]?.length ?? 0) > 2000) e[f] = t("common.validation.tooLong", { max: 2000 });
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSave() {
    if (!candidate || !validate()) return;
    setSaving(true);
    const body: CandidateProfileUpdate = {
      full_name: form.full_name,
      email: form.email,
      phone: form.phone,
      linkedin_url: form.linkedin_url?.trim() ? form.linkedin_url : null,
      service_concept: form.service_concept?.trim() ? form.service_concept : null,
      salary_expectations: form.salary_expectations?.trim() ? form.salary_expectations : null,
      personality_strength: form.personality_strength?.trim() ? form.personality_strength : null,
      personality_weakness: form.personality_weakness?.trim() ? form.personality_weakness : null,
    };
    try {
      const updated = await updateCandidate(candidate.id, body);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  if (!candidate) return null;

  return (
    <>
    <Dialog
      open={candidate != null}
      onOpenChange={(o) => !o && handleClose()}
      title={t("admin.candidates.editModalTitle")}
      description={candidate.email}
      size="lg"
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
            onClick={handleSave}
            disabled={saving}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {saving ? t("common.saving") : t("common.save")}
          </button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <Field label={t("admin.candidates.fields.fullName")}>
          <input type="text" value={form.full_name ?? ""} onChange={(e) => set("full_name", e.target.value)} className={inputCls} />
          {errors.full_name && <p className="mt-1 text-xs text-danger">{errors.full_name}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.email")}>
          <input type="email" value={form.email ?? ""} onChange={(e) => set("email", e.target.value)} className={inputCls} />
          {errors.email && <p className="mt-1 text-xs text-danger">{errors.email}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.phone")}>
          <input type="tel" value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value)} className={inputCls} />
          {errors.phone && <p className="mt-1 text-xs text-danger">{errors.phone}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.linkedin")}>
          <input type="url" value={form.linkedin_url ?? ""} onChange={(e) => set("linkedin_url", e.target.value)} className={inputCls} />
          {errors.linkedin_url && <p className="mt-1 text-xs text-danger">{errors.linkedin_url}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.serviceConcept")} full>
          <textarea rows={2} value={form.service_concept ?? ""} onChange={(e) => set("service_concept", e.target.value)} className={textareaCls} />
          {errors.service_concept && <p className="mt-1 text-xs text-danger">{errors.service_concept}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.salaryExpectations")} full>
          <textarea rows={2} value={form.salary_expectations ?? ""} onChange={(e) => set("salary_expectations", e.target.value)} className={textareaCls} />
          {errors.salary_expectations && <p className="mt-1 text-xs text-danger">{errors.salary_expectations}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.strength")} full>
          <textarea rows={2} value={form.personality_strength ?? ""} onChange={(e) => set("personality_strength", e.target.value)} className={textareaCls} />
          {errors.personality_strength && <p className="mt-1 text-xs text-danger">{errors.personality_strength}</p>}
        </Field>
        <Field label={t("admin.candidates.fields.weakness")} full>
          <textarea rows={2} value={form.personality_weakness ?? ""} onChange={(e) => set("personality_weakness", e.target.value)} className={textareaCls} />
          {errors.personality_weakness && <p className="mt-1 text-xs text-danger">{errors.personality_weakness}</p>}
        </Field>
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
    </>
  );
}

function Field({
  label,
  children,
  full,
}: {
  label: string;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <label className={`block ${full ? "sm:col-span-2" : ""}`}>
      <span className="block text-xs text-white/45">{label}</span>
      <span className="mt-1 block">{children}</span>
    </label>
  );
}
