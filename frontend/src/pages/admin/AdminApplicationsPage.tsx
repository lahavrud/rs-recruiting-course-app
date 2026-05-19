import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDebounce } from "@/hooks/useDebounce";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { getActiveCompanies } from "@/services/adminCompanies";
import { getJobs } from "@/services/adminJobs";
import {
  deleteApplication,
  getApplications,
  updateApplicationNotes,
  updateApplicationStatus,
} from "@/services/adminApplications";
import type { ApplicationListParams } from "@/services/adminApplications";
import { fetchResumeBlob } from "@/services/adminCandidates";
import { ApplicationStatus } from "@/types/api";
import type { ApplicationStatusUpdate, ApplicationWithDetails } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import Dialog from "@/components/ui/Dialog";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import TableSkeleton from "@/components/ui/TableSkeleton";
import MobileListSkeleton from "@/components/admin/MobileListSkeleton";
import SearchInput from "@/components/ui/SearchInput";
import FunnelIcon from "@/components/admin/FunnelIcon";
import ActiveFilterChip from "@/components/admin/ActiveFilterChip";
import MobileEntityCard from "@/components/admin/MobileEntityCard";
import SearchableMultiSelect from "@/components/admin/SearchableMultiSelect";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
import { useAutoOpenFromRouteState } from "@/hooks/useAutoOpenFromRouteState";
import { usePageTitle } from "@/hooks/usePageTitle";
import { useToast } from "@/hooks/useToast";
import { selectCls, textareaCls } from "@/styles/forms";

const ALL_STATUSES = [
  ApplicationStatus.NEW,
  ApplicationStatus.APPROVED_BY_ADMIN,
  ApplicationStatus.REJECTED,
  ApplicationStatus.HIRED,
];

const TERMINAL_STATUSES = new Set<string>([
  ApplicationStatus.REJECTED,
  ApplicationStatus.HIRED,
]);

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  REJECTED: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
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

// ── Resume link — fetches via axios so the JWT travels with it ──────────────

const MIME_TO_EXT: Record<string, string> = {
  "application/pdf": "pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
  "application/msword": "doc",
};

function buildDownloadName(candidateName: string, fileKey: string, mimeType: string): string {
  const slug = candidateName.trim().replace(/\s+/g, "-");
  const keyExt = fileKey.includes(".") ? fileKey.split(".").pop() : undefined;
  const safeKeyExt = keyExt && /^[a-zA-Z0-9]{1,5}$/.test(keyExt) ? keyExt.toLowerCase() : undefined;
  const ext = MIME_TO_EXT[mimeType] ?? safeKeyExt ?? "bin";
  return `${slug}-resume.${ext}`;
}

function triggerDownload(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function ResumeLink({
  fileKey,
  label,
  candidateName,
}: {
  fileKey: string;
  label: string;
  candidateName: string;
}) {
  const [isLoading, setIsLoading] = useState(false);
  async function open(e: React.MouseEvent) {
    e.stopPropagation();
    if (isLoading) return;
    setIsLoading(true);
    try {
      const blob = await fetchResumeBlob(fileKey);
      const mimeType = blob.type || "application/octet-stream";
      const filename = buildDownloadName(candidateName, fileKey, mimeType);
      const isPdf = mimeType === "application/pdf" || fileKey.toLowerCase().endsWith(".pdf");

      // iOS ignores <a download> on blob URLs — use Web Share API instead.
      // Scoped to iOS only: other platforms mishandle navigator.share with files.
      const isIOS =
        /iPhone|iPad|iPod/.test(navigator.userAgent) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
      if (isIOS && typeof navigator.canShare === "function") {
        const file = new File([blob], filename, { type: mimeType });
        if (navigator.canShare({ files: [file] })) {
          try {
            await navigator.share({ files: [file] });
            return;
          } catch (err) {
            if (err instanceof Error && err.name === "AbortError") return;
          }
        }
      }

      const url = URL.createObjectURL(blob);
      if (isPdf || isIOS) {
        const win = window.open(url, "_blank");
        if (!win) triggerDownload(url, filename);
      } else {
        triggerDownload(url, filename);
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

export default function AdminApplicationsPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.applications.title"));
  const toast = useToast();

  const [filter, setFilter] = useState<FilterValue>(() => {
    const s = new URLSearchParams(window.location.search).get("status");
    if (
      s === ApplicationStatus.NEW ||
      s === ApplicationStatus.APPROVED_BY_ADMIN ||
      s === ApplicationStatus.REJECTED ||
      s === ApplicationStatus.HIRED
    ) {
      return s;
    }
    return ALL_FILTER;
  });

  // Job filter: multi-select (client-side). URL ?job=<id> seeds the array.
  const [jobFilter, setJobFilter] = useState<number[]>(() => {
    const val = new URLSearchParams(window.location.search).get("job");
    return val && !Number.isNaN(Number(val)) ? [Number(val)] : [];
  });
  // Candidate filter: still single, URL-driven (?candidate=<id>) — there's no
  // UI to pick more than one from the panel.
  const [filterCandidateId, setFilterCandidateId] = useState<number | undefined>(() => {
    const val = new URLSearchParams(window.location.search).get("candidate");
    return val && !Number.isNaN(Number(val)) ? Number(val) : undefined;
  });

  // Clean URL params on mount after reading them
  useEffect(() => {
    if (jobFilter.length > 0 || filterCandidateId != null) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ApplicationWithDetails>> => {
      const params: ApplicationListParams = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as ApplicationStatus;
      if (filterCandidateId != null) params.candidate_id = filterCandidateId;
      return getApplications(params);
    },
    [filter, filterCandidateId],
  );

  const {
    items: applications,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<ApplicationWithDetails>(fetcher);

  const [detail, setDetail] = useState<ApplicationWithDetails | null>(null);
  const [statusModal, setStatusModal] = useState<ApplicationWithDetails | null>(null);
  const [notesModal, setNotesModal] = useState<ApplicationWithDetails | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<ApplicationWithDetails | null>(
    null,
  );
  const [pendingDelete, setPendingDelete] = useState(false);

  // Client-side filters (status + job/candidate are server-side via fetcher).
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 200);
  const [filterOpen, setFilterOpen] = useState(false);
  const [companyFilter, setCompanyFilter] = useState<number[]>([]);

  // Cache of all jobs and active companies for the filter selects.
  const [allJobs, setAllJobs] = useState<{ id: number; title: string; company_id: number }[]>([]);
  const [companyNameById, setCompanyNameById] = useState<Map<number, string>>(
    new Map(),
  );
  const [jobTitleById, setJobTitleById] = useState<Map<number, string>>(
    new Map(),
  );
  useEffect(() => {
    const ctrl = new AbortController();
    Promise.all([
      getJobs({ limit: 100 }, ctrl.signal),
      getActiveCompanies({ limit: 100 }, ctrl.signal),
    ])
      .then(([jobsPage, companiesPage]) => {
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
      })
      .catch(() => {
        /* best-effort */
      });
    return () => ctrl.abort();
  }, []);

  const filteredApplications = useMemo(() => {
    const q = debouncedQuery.trim().toLowerCase();
    const jobSet = new Set(jobFilter);
    const companySet = new Set(companyFilter);
    return applications.filter((a) => {
      if (jobSet.size > 0 && !jobSet.has(a.job_id)) return false;
      if (companySet.size > 0 && !companySet.has(a.job.company_id)) return false;
      if (!q) return true;
      return [
        a.candidate.full_name,
        a.candidate.email,
        a.candidate.phone ?? "",
        a.job.title,
        a.job.location,
        a.admin_notes ?? "",
      ].some((s) => s.toLowerCase().includes(q));
    });
  }, [applications, debouncedQuery, jobFilter, companyFilter]);

  const activeFilterCount =
    (debouncedQuery.trim() ? 1 : 0) +
    (filter !== ALL_FILTER ? 1 : 0) +
    jobFilter.length +
    (filterCandidateId != null ? 1 : 0) +
    companyFilter.length;


  // Auto-open application passed via navigation state (e.g. from Candidate detail)
  useAutoOpenFromRouteState<ApplicationWithDetails>("autoOpen", setDetail);

  const STATUS_LABELS: Record<string, string> = {
    NEW: t("admin.applications.statusLabels.NEW"),
    APPROVED_BY_ADMIN: t("admin.applications.statusLabels.APPROVED_BY_ADMIN"),
    REJECTED: t("admin.applications.statusLabels.REJECTED"),
    HIRED: t("admin.applications.statusLabels.HIRED"),
  };

  async function handleDeleteConfirm() {
    if (!deleteCandidate) return;
    setPendingDelete(true);
    try {
      await deleteApplication(deleteCandidate.id);
      removeItem((a) => a.id === deleteCandidate.id);
      toast.success(t("admin.applications.deletedToast"));
      setDeleteCandidate(null);
      setDetail(null);
    } catch {
      toast.error(t("admin.applications.errors.deleteFailed"));
    } finally {
      setPendingDelete(false);
    }
  }

  const filterTabs: FilterValue[] = [ALL_FILTER, ...ALL_STATUSES];

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin.applications.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin.applications.title")}
        subtitle={t("admin.applications.subtitle")}
      />

      {/* Search + filter trigger */}
      <div className="mb-3 flex items-stretch gap-2">
        <div className="flex-1">
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder={t("admin.applications.searchPlaceholder")}
            clearable
          />
        </div>
        <button
          type="button"
          onClick={() => setFilterOpen((o) => !o)}
          aria-expanded={filterOpen}
          aria-label={t("admin.applications.openFilters")}
          className={`relative inline-flex shrink-0 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors duration-200 active:scale-95 ${
            filterOpen
              ? "border-copper/50 bg-copper/10 text-white"
              : "border-white/15 bg-card-raised/40 text-white/75 hover:border-copper/40 hover:text-white"
          }`}
        >
          <FunnelIcon />
          <span className="hidden sm:inline">{t("admin.applications.filters")}</span>
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
              label={`${t("admin.applications.table.status")}: ${STATUS_LABELS[filter]}`}
              onRemove={() => setFilter(ALL_FILTER)}
            />
          )}
          {query.trim() && (
            <ActiveFilterChip
              label={`${t("common.search")}: "${query.trim()}"`}
              onRemove={() => setQuery("")}
            />
          )}
          {jobFilter.map((id) => (
            <ActiveFilterChip
              key={`job-${id}`}
              label={`${t("common.filteredByJob")}: ${jobTitleById.get(id) ?? `#${id}`}`}
              onRemove={() => setJobFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
          {filterCandidateId != null && (
            <ActiveFilterChip
              label={`${t("common.filteredByCandidate")} #${filterCandidateId}`}
              onRemove={() => setFilterCandidateId(undefined)}
            />
          )}
          {companyFilter.map((id) => (
            <ActiveFilterChip
              key={`co-${id}`}
              label={`${t("admin.applications.filterByCompany")}: ${companyNameById.get(id) ?? `#${id}`}`}
              onRemove={() => setCompanyFilter((prev) => prev.filter((x) => x !== id))}
            />
          ))}
        </div>
      )}

      {/* Filter panel — animated open/close */}
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
                {t("admin.applications.table.status")}
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
                        ? t("admin.applications.filterAll")
                        : STATUS_LABELS[tab]}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {/* Company first → in RTL it lands on the visual right */}
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
                  {t("admin.applications.filterByCompany")}
                </p>
                <SearchableMultiSelect<number>
                  values={companyFilter}
                  onChange={(next) => {
                    setCompanyFilter(next);
                    // Drop any selected jobs that no longer match an active company.
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
                  placeholder={t("admin.applications.allCompanies")}
                />
              </div>
              <div>
                <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-widest text-copper">
                  {t("admin.applications.filterByJob")}
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
                  placeholder={t("admin.applications.allJobs")}
                />
              </div>
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
        <ErrorState message={t("admin.applications.loadError")} onRetry={reload} />
      ) : applications.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.applications.title")}
          headline={t("admin.applications.empty")}
        />
      ) : filteredApplications.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-16 text-center">
          <p className="text-sm text-white/40">
            {t("publicJobs.board.noResults")}
          </p>
        </div>
      ) : (
        <>
          {/* Mobile cards — tap to expand inline; 3-dot menu for actions */}
          <div className="space-y-2 md:hidden">
            {filteredApplications.map((app) => {
              const actions = (
                <DropdownMenu
                  ariaLabel={t("admin.applications.rowActionsLabel")}
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
                  <DropdownMenuItem onSelect={() => setStatusModal(app)}>
                    {t("admin.applications.updateStatusAction")}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => setNotesModal(app)}>
                    {t("admin.applications.editNotesAction")}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    variant="danger"
                    onSelect={() => setDeleteCandidate(app)}
                  >
                    {t("admin.applications.deleteAction")}
                  </DropdownMenuItem>
                </DropdownMenu>
              );
              return (
                <MobileEntityCard
                  key={app.id}
                  title={
                    <div className="min-w-0">
                      <p className="truncate font-medium text-white/85">
                        {app.candidate.full_name}
                      </p>
                      <p className="truncate text-[11px] font-normal text-white/50">
                        {app.job.title}
                      </p>
                    </div>
                  }
                  badge={
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS_COLORS[app.status]}`}
                    >
                      {STATUS_LABELS[app.status]}
                    </span>
                  }
                  actions={actions}
                >
                  <ApplicationDetailBody app={app} />
                </MobileEntityCard>
              );
            })}
          </div>

          {/* Desktop */}
          <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin.applications.table.candidate")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.applications.table.job")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.applications.table.status")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.applications.table.date")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {filteredApplications.map((app) => (
                  <tr
                    key={app.id}
                    onClick={() => setDetail(app)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white/85">
                        {app.candidate.full_name}
                      </p>
                      <p className="text-xs text-white/40">{app.candidate.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-white/80">{app.job.title}</p>
                      <p className="text-xs text-white/40">{app.job.location}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[app.status]}`}
                      >
                        {STATUS_LABELS[app.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(app.created_at)}
                    </td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu
                        ariaLabel={t("admin.applications.rowActionsLabel")}
                        trigger={
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:bg-white/8 hover:text-white/80"
                          >
                            <span aria-hidden>⋮</span>
                          </button>
                        }
                      >
                        <DropdownMenuItem onSelect={() => setDetail(app)}>
                          {t("admin.applications.viewAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setStatusModal(app)}>
                          {t("admin.applications.updateStatusAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem onSelect={() => setNotesModal(app)}>
                          {t("admin.applications.editNotesAction")}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setDeleteCandidate(app)}
                        >
                          {t("admin.applications.deleteAction")}
                        </DropdownMenuItem>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sentinel for IntersectionObserver */}
          <div ref={sentinelRef} />
          {isFetchingMore && (
            <p className="mt-4 text-center text-xs text-white/30">
              {t("common.loading")}
            </p>
          )}
        </>
      )}

      {/* Detail modal */}
      <DetailDialog
        app={detail}
        onClose={() => setDetail(null)}
        onUpdateStatus={() => {
          if (detail) setStatusModal(detail);
          setDetail(null);
        }}
        onEditNotes={() => {
          if (detail) setNotesModal(detail);
          setDetail(null);
        }}
        onDelete={() => {
          if (detail) setDeleteCandidate(detail);
          setDetail(null);
        }}
      />

      {/* Status update modal */}
      <StatusDialog
        app={statusModal}
        onClose={() => setStatusModal(null)}
        onSaved={(updated) => {
          updateItem(
            (a) => a.id === updated.id,
            (prev) => ({
              ...prev,
              status: updated.status,
              admin_notes: updated.admin_notes,
              updated_at: updated.updated_at,
            }),
          );
          toast.success(t("admin.applications.savedToast"));
          setStatusModal(null);
        }}
        onError={() => toast.error(t("admin.applications.errors.updateFailed"))}
      />

      {/* Notes-only modal */}
      <NotesDialog
        app={notesModal}
        onClose={() => setNotesModal(null)}
        onSaved={(updated) => {
          updateItem(
            (a) => a.id === updated.id,
            (prev) => ({
              ...prev,
              admin_notes: updated.admin_notes,
              updated_at: updated.updated_at,
            }),
          );
          toast.success(t("admin.applications.notesSavedToast"));
          setNotesModal(null);
        }}
        onError={() => toast.error(t("admin.applications.errors.notesFailed"))}
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteCandidate != null}
        onOpenChange={(o) => !o && setDeleteCandidate(null)}
        title={t("admin.applications.deleteConfirmTitle")}
        message={t("admin.applications.deleteConfirm")}
        confirmLabel={t("admin.applications.deleteConfirmYes")}
        variant="danger"
        isPending={pendingDelete}
        onConfirm={handleDeleteConfirm}
      />
    </div>
  );
}

// ── Detail dialog ───────────────────────────────────────────────────────────

interface DetailProps {
  app: ApplicationWithDetails | null;
  onClose: () => void;
  onUpdateStatus: () => void;
  onEditNotes: () => void;
  onDelete: () => void;
}

function DetailDialog({
  app,
  onClose,
  onUpdateStatus,
  onEditNotes,
  onDelete,
}: DetailProps) {
  const { t } = useTranslation();
  if (!app) return null;
  const c = app.candidate;
  return (
    <Dialog
      open={app != null}
      onOpenChange={(o) => !o && onClose()}
      title={c.full_name}
      description={app.job.title}
      size="lg"
      footer={
        <>
          <button
            onClick={onDelete}
            className="rounded-sm border border-danger/40 px-4 py-2 text-sm text-danger hover:bg-danger/10"
          >
            {t("admin.applications.deleteAction")}
          </button>
          <button
            onClick={onEditNotes}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/70 hover:border-white/40 hover:text-white/90"
          >
            {t("admin.applications.editNotesAction")}
          </button>
          <button
            onClick={onUpdateStatus}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("admin.applications.updateStatusAction")}
          </button>
        </>
      }
    >
      <ApplicationDetailBody app={app} onLeavePage={onClose} />
    </Dialog>
  );
}

/** Detail body shared by the desktop dialog and the mobile inline expansion. */
function ApplicationDetailBody({
  app,
  onLeavePage,
}: {
  app: ApplicationWithDetails;
  onLeavePage?: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const c = app.candidate;
  const linkBtnCls =
    "inline-flex items-center rounded-sm border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-copper/90 transition hover:border-copper/30 hover:bg-copper/10 sm:rounded-none sm:border-0 sm:bg-transparent sm:p-0 sm:text-copper/80 sm:hover:bg-transparent sm:hover:text-copper sm:hover:underline";
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2 border-b border-white/8 pb-3">
        <button
          type="button"
          onClick={() => {
            onLeavePage?.();
            navigate(`/admin/candidates?detail=${app.candidate_id}`);
          }}
          className={linkBtnCls}
        >
          {t("common.viewCandidate")}
        </button>
        <button
          type="button"
          onClick={() => {
            onLeavePage?.();
            navigate(`/admin/jobs?detail=${app.job_id}`);
          }}
          className={linkBtnCls}
        >
          {t("common.viewJob")}
        </button>
        <span className="text-xs text-white/40">{formatDate(app.created_at)}</span>
      </div>
      <div className="flex flex-wrap gap-x-6 gap-y-1">
        <span className="text-white/60">{c.email}</span>
        {c.phone && <span className="text-white/60">{c.phone}</span>}
        {c.linkedin_url && (
          <a
            href={c.linkedin_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-copper hover:text-gold"
          >
            {t("admin.applications.details.linkedin")} ↗
          </a>
        )}
        {c.resume_path ? (
          <ResumeLink
            fileKey={c.resume_path.split("/").pop() ?? c.resume_path}
            label={t("admin.applications.details.resume")}
            candidateName={c.full_name}
          />
        ) : (
          <span className="text-white/40">
            {t("admin.applications.details.resume")}:{" "}
            {t("admin.applications.details.noFile")}
          </span>
        )}
      </div>

      {(app.service_concept ||
        app.salary_expectations ||
        app.strength ||
        app.growth_area) && (
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
          {app.service_concept && (
            <>
              <dt className="text-white/35">
                {t("admin.applications.details.serviceConcept")}
              </dt>
              <dd className="text-white/70">{app.service_concept}</dd>
            </>
          )}
          {app.salary_expectations && (
            <>
              <dt className="text-white/35">
                {t("admin.applications.details.salaryExpectations")}
              </dt>
              <dd className="text-white/70">{app.salary_expectations}</dd>
            </>
          )}
          {app.strength && (
            <>
              <dt className="text-white/35">
                {t("admin.applications.details.strength")}
              </dt>
              <dd className="text-white/70">{app.strength}</dd>
            </>
          )}
          {app.growth_area && (
            <>
              <dt className="text-white/35">
                {t("admin.applications.details.weakness")}
              </dt>
              <dd className="text-white/70">{app.growth_area}</dd>
            </>
          )}
        </dl>
      )}

      {app.admin_notes && (
        <div className="rounded-md border border-white/8 bg-card p-3 text-white/70">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
            {t("admin.applications.modal.adminNotes")}
          </p>
          <p className="mt-1 whitespace-pre-wrap">{app.admin_notes}</p>
        </div>
      )}
    </div>
  );
}

// ── Status dialog (with optional notes) ──────────────────────────────────────

interface StatusDialogProps {
  app: ApplicationWithDetails | null;
  onClose: () => void;
  onSaved: (next: {
    id: number;
    status: ApplicationStatus;
    admin_notes: string | null;
    updated_at: string;
  }) => void;
  onError: () => void;
}

function StatusDialog({ app, onClose, onSaved, onError }: StatusDialogProps) {
  const { t } = useTranslation();
  const [newStatus, setNewStatus] = useState<string>(
    app?.status ?? ApplicationStatus.NEW,
  );
  const [notes, setNotes] = useState<string>(app?.admin_notes ?? "");
  const [saving, setSaving] = useState(false);

  // Re-seed form fields whenever the target application changes (e.g. user
  // closes one row's dialog and opens another).
  const lastAppId = useRef<number | null>(null);
  useEffect(() => {
    if (!app) {
      lastAppId.current = null;
      return;
    }
    if (lastAppId.current === app.id) return;
    lastAppId.current = app.id;
    setNewStatus(app.status);
    setNotes(app.admin_notes ?? "");
  }, [app]);

  async function handleSave() {
    if (!app) return;
    setSaving(true);
    const body: ApplicationStatusUpdate = {
      status: newStatus as ApplicationStatusUpdate["status"],
      admin_notes: notes.trim() || null,
    };
    try {
      const updated = await updateApplicationStatus(app.id, body);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  const isRevert =
    app != null && TERMINAL_STATUSES.has(app.status) && newStatus !== app.status;

  if (!app) return null;

  return (
    <Dialog
      open={app != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.applications.modal.title")}
      size="md"
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
            onClick={handleSave}
            disabled={saving}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {saving ? t("common.saving") : t("common.save")}
          </button>
        </>
      }
    >
      <div className="space-y-3 text-sm text-white/70">
        <p>
          <span className="text-white/40">
            {t("admin.applications.modal.candidateLabel")}:
          </span>{" "}
          {app.candidate.full_name}
        </p>
        <p>
          <span className="text-white/40">
            {t("admin.applications.modal.jobLabel")}:
          </span>{" "}
          {app.job.title}
        </p>
        <div>
          <label className="block text-white/50">
            {t("admin.applications.modal.newStatusLabel")}
          </label>
          <select
            value={newStatus}
            onChange={(e) => setNewStatus(e.target.value)}
            className={`mt-1 ${selectCls}`}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s} className="bg-well">
                {t(`admin.applications.statusLabels.${s}`)}
              </option>
            ))}
          </select>
          {isRevert && (
            <p className="mt-2 text-xs text-warning">
              {t("admin.applications.revertConfirm")}
            </p>
          )}
        </div>
        <div>
          <label className="block text-white/50">
            {t("admin.applications.modal.adminNotes")}{" "}
            <span className="text-white/25">({t("common.optional")})</span>
          </label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className={`mt-1 ${textareaCls}`}
            placeholder={t("admin.applications.modal.notesPlaceholder")}
          />
        </div>
      </div>
    </Dialog>
  );
}

// ── Notes-only dialog ──────────────────────────────────────────────────────

interface NotesDialogProps {
  app: ApplicationWithDetails | null;
  onClose: () => void;
  onSaved: (next: {
    id: number;
    admin_notes: string | null;
    updated_at: string;
  }) => void;
  onError: () => void;
}

function NotesDialog({ app, onClose, onSaved, onError }: NotesDialogProps) {
  const { t } = useTranslation();
  const [notes, setNotes] = useState<string>(app?.admin_notes ?? "");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!app) return;
    setSaving(true);
    try {
      const updated = await updateApplicationNotes(app.id, notes.trim() ? notes : null);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  if (!app) return null;

  return (
    <Dialog
      open={app != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.applications.notesModalTitle")}
      description={app.candidate.full_name}
      size="md"
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
            onClick={handleSave}
            disabled={saving}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {saving ? t("common.saving") : t("common.save")}
          </button>
        </>
      }
    >
      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        rows={5}
        maxLength={5000}
        className={textareaCls}
        placeholder={t("admin.applications.modal.notesPlaceholder")}
      />
      {notes.length > 4800 && (
        <p className="mt-1 text-xs text-white/35">{notes.length} / 5000</p>
      )}
    </Dialog>
  );
}
