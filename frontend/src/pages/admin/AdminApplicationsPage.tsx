import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  deleteApplication,
  getApplications,
  updateApplicationNotes,
  updateApplicationStatus,
  fetchResumeBlob,
} from "@/services/admin";
import type { ApplicationListParams } from "@/services/admin";
import { ApplicationStatus } from "@/types/api";
import type { ApplicationStatusUpdate, ApplicationWithDetails } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import Dialog from "@/components/ui/Dialog";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import TableSkeleton from "@/components/ui/TableSkeleton";
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
import { useInfiniteList, type CursorPage } from "@/hooks/useInfiniteList";
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

function ResumeLink({ fileKey, label }: { fileKey: string; label: string }) {
  async function open(e: React.MouseEvent) {
    e.stopPropagation();
    const win = window.open("", "_blank");
    if (!win) return;
    try {
      const blob = await fetchResumeBlob(fileKey);
      const url = URL.createObjectURL(blob);
      win.location.href = url;
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      win.close();
    }
  }
  return (
    <button onClick={open} className="text-copper hover:text-gold">
      {label} ↗
    </button>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminApplicationsPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.applications.title"));
  const toast = useToast();

  const [filter, setFilter] = useState<FilterValue>(ALL_FILTER);

  // Pre-fill job/candidate filters from URL params (?job=<id> or ?candidate=<id>)
  const [filterJobId, setFilterJobId] = useState<number | undefined>(() => {
    const val = new URLSearchParams(window.location.search).get("job");
    return val && !Number.isNaN(Number(val)) ? Number(val) : undefined;
  });
  const [filterCandidateId, setFilterCandidateId] = useState<number | undefined>(() => {
    const val = new URLSearchParams(window.location.search).get("candidate");
    return val && !Number.isNaN(Number(val)) ? Number(val) : undefined;
  });

  // Clean URL params on mount after reading them
  useEffect(() => {
    if (filterJobId != null || filterCandidateId != null) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [filterJobId, filterCandidateId]);

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ApplicationWithDetails>> => {
      const params: ApplicationListParams = { cursor };
      if (filter !== ALL_FILTER) params.status = filter as ApplicationStatus;
      if (filterJobId != null) params.job_id = filterJobId;
      if (filterCandidateId != null) params.candidate_id = filterCandidateId;
      return getApplications(params);
    },
    [filter, filterJobId, filterCandidateId],
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

  const navigate = useNavigate();
  const location = useLocation();

  const [detail, setDetail] = useState<ApplicationWithDetails | null>(null);
  const [statusModal, setStatusModal] = useState<ApplicationWithDetails | null>(null);
  const [notesModal, setNotesModal] = useState<ApplicationWithDetails | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<ApplicationWithDetails | null>(
    null,
  );
  const [pendingDelete, setPendingDelete] = useState(false);

  // Auto-open application passed via navigation state (e.g. from Candidate detail)
  useEffect(() => {
    const app = (location.state as { autoOpen?: ApplicationWithDetails } | null)
      ?.autoOpen;
    if (!app) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDetail(app);
    navigate(location.pathname + location.search, { replace: true, state: null });
  }, [location.state, location.pathname, location.search, navigate]);

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

      {(filterJobId != null || filterCandidateId != null) && (
        <div className="mb-4 flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-copper/30 bg-copper/10 py-1 ps-3 pe-2 text-xs text-copper">
            {filterJobId != null
              ? `${t("common.filteredByJob")} #${filterJobId}`
              : `${t("common.filteredByCandidate")} #${filterCandidateId}`}
            <button
              type="button"
              aria-label={t("common.clearFilter")}
              onClick={() => { setFilterJobId(undefined); setFilterCandidateId(undefined); }}
              className="rounded-full p-0.5 hover:bg-copper/20"
            >
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" fill="currentColor" className="size-3" aria-hidden="true">
                <path d="M4.22 3.22a.75.75 0 0 0-1.06 1.06L4.94 6 3.16 7.78a.75.75 0 1 0 1.06 1.06L6 7.06l1.78 1.78a.75.75 0 1 0 1.06-1.06L7.06 6l1.78-1.78a.75.75 0 0 0-1.06-1.06L6 4.94 4.22 3.22Z" />
              </svg>
            </button>
          </span>
        </div>
      )}

      <div className="mb-5 flex flex-wrap gap-2">
        {filterTabs.map((tab) => {
          const active = filter === tab;
          return (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                active
                  ? "bg-copper text-white"
                  : "border border-white/10 text-white/40 hover:border-white/20 hover:text-white/70"
              }`}
            >
              {tab === ALL_FILTER
                ? t("admin.applications.filterAll")
                : STATUS_LABELS[tab]}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <TableSkeleton rows={6} columns={4} />
      ) : error ? (
        <ErrorState message={t("admin.applications.loadError")} onRetry={reload} />
      ) : applications.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.applications.title")}
          headline={t("admin.applications.empty")}
        />
      ) : (
        <>
          {/* Mobile */}
          <div className="space-y-2 md:hidden">
            {applications.map((app) => (
              <button
                key={app.id}
                onClick={() => setDetail(app)}
                className="w-full rounded-xl border border-white/8 bg-card px-4 py-3 text-start transition hover:border-white/15"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white/85">
                      {app.candidate.full_name}
                    </p>
                    <p className="truncate text-xs text-white/50">{app.job.title}</p>
                  </div>
                  <span
                    className={`mt-0.5 shrink-0 inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[app.status]}`}
                  >
                    {STATUS_LABELS[app.status]}
                  </span>
                </div>
                <p className="mt-2 text-xs text-white/35">
                  {formatDate(app.created_at)}
                </p>
              </button>
            ))}
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
                {applications.map((app) => (
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
          updateItem((a) => a.id === updated.id, {
            ...statusModal!,
            status: updated.status,
            admin_notes: updated.admin_notes,
            updated_at: updated.updated_at,
          });
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
          updateItem((a) => a.id === updated.id, {
            ...notesModal!,
            admin_notes: updated.admin_notes,
            updated_at: updated.updated_at,
          });
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
  const navigate = useNavigate();
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
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-white/8 pb-3">
          <button
            type="button"
            onClick={() => { onClose(); navigate(`/admin/candidates?detail=${app.candidate_id}`); }}
            className="text-xs text-copper/70 underline-offset-2 transition hover:text-copper hover:underline"
          >
            {t("common.viewCandidate")}
          </button>
          <button
            type="button"
            onClick={() => { onClose(); navigate(`/admin/jobs?detail=${app.job_id}`); }}
            className="text-xs text-copper/70 underline-offset-2 transition hover:text-copper hover:underline"
          >
            {t("common.viewJob")}
          </button>
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
            />
          ) : (
            <span className="text-white/40">
              {t("admin.applications.details.resume")}:{" "}
              {t("admin.applications.details.noFile")}
            </span>
          )}
        </div>

        {(c.service_concept ||
          c.salary_expectations ||
          c.personality_strength ||
          c.personality_weakness) && (
          <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
            {c.service_concept && (
              <>
                <dt className="text-white/35">
                  {t("admin.applications.details.serviceConcept")}
                </dt>
                <dd className="text-white/70">{c.service_concept}</dd>
              </>
            )}
            {c.salary_expectations && (
              <>
                <dt className="text-white/35">
                  {t("admin.applications.details.salaryExpectations")}
                </dt>
                <dd className="text-white/70">{c.salary_expectations}</dd>
              </>
            )}
            {c.personality_strength && (
              <>
                <dt className="text-white/35">
                  {t("admin.applications.details.strength")}
                </dt>
                <dd className="text-white/70">{c.personality_strength}</dd>
              </>
            )}
            {c.personality_weakness && (
              <>
                <dt className="text-white/35">
                  {t("admin.applications.details.weakness")}
                </dt>
                <dd className="text-white/70">{c.personality_weakness}</dd>
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
    </Dialog>
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
