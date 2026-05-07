import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  approveJob,
  contactJob,
  createJob,
  deleteJob,
  getActiveCompanies,
  getJob,
  getJobs,
  rejectJob,
  updateJob,
} from "@/services/admin";
import type {
  ActiveCompanyRead,
  JobAdminCreate,
  JobRead,
  JobUpdate,
} from "@/types/api";
import { JobStatus } from "@/types/api";
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
import { inputCls, selectCls, textareaCls } from "@/styles/forms";

const ALL_STATUSES = [
  JobStatus.PENDING_APPROVAL,
  JobStatus.PUBLISHED,
  JobStatus.CLOSED,
];

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

  const [filter, setFilter] = useState<FilterValue>(ALL_FILTER);

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
  const [contacting, setContacting] = useState<JobRead | null>(null);
  const [deletePending, setDeletePending] = useState<JobRead | null>(null);
  const [rejectPending, setRejectPending] = useState<JobRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  // Auto-open detail modal when navigated from another page via ?detail=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    window.history.replaceState({}, "", window.location.pathname);
    getJob(Number(id)).then(setDetail).catch(() => toast.error(t("common.genericError")));
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
              {tab === ALL_FILTER ? t("admin.jobs.filterAll") : STATUS_LABELS[tab]}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <TableSkeleton rows={6} columns={4} />
      ) : error ? (
        <ErrorState message={t("admin.jobs.loadError")} onRetry={reload} />
      ) : jobs.length === 0 ? (
        <EmptyState eyebrow={t("admin.jobs.title")} headline={t("admin.jobs.empty")} />
      ) : (
        <>
          {/* Mobile cards */}
          <div className="space-y-2 md:hidden">
            {jobs.map((job) => (
              <button
                key={job.id}
                onClick={() => setDetail(job)}
                className="w-full rounded-xl border border-white/8 bg-card px-4 py-3 text-start transition hover:border-white/15"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-white/85">{job.title}</p>
                    <p className="truncate text-xs text-white/50">{job.location}</p>
                  </div>
                  <span
                    className={`mt-0.5 shrink-0 inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[job.status]}`}
                  >
                    {STATUS_LABELS[job.status]}
                  </span>
                </div>
              </button>
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
                    {t("admin.jobs.fields.status")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.jobs.submittedLabel")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {jobs.map((job) => (
                  <tr
                    key={job.id}
                    onClick={() => setDetail(job)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="px-4 py-3 font-medium text-white/85">{job.title}</td>
                    <td className="px-4 py-3 text-white/60">{job.location}</td>
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
                        <DropdownMenuItem onSelect={() => setContacting(job)}>
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

      <ContactDialog
        job={contacting}
        onClose={() => setContacting(null)}
        onSent={() => {
          toast.success(t("admin.jobs.emailSuccess"));
          setContacting(null);
        }}
        onError={() => toast.error(t("admin.jobs.emailError"))}
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
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function DetailDialog({
  job,
  statusLabels,
  statusColors,
  onClose,
  onEdit,
  onDelete,
}: DetailProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  if (!job) return null;
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
          <button
            onClick={onEdit}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
          >
            {t("admin.jobs.editAction")}
          </button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span
            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${statusColors[job.status]}`}
          >
            {statusLabels[job.status]}
          </span>
          <button
            type="button"
            onClick={() => { onClose(); navigate(`/admin/companies?detail=${job.company_id}`); }}
            className="text-copper/70 underline-offset-2 transition hover:text-copper hover:underline"
          >
            {t("admin.jobs.companyLabel", { id: job.company_id })}
          </button>
          <span className="text-white/40">
            {t("admin.jobs.submittedLabel")} {formatDate(job.created_at)}
          </span>
          <button
            type="button"
            onClick={() => { onClose(); navigate(`/admin/applications?job=${job.id}`); }}
            className="text-copper/70 underline-offset-2 transition hover:text-copper hover:underline"
          >
            {t("common.viewApplications")}
          </button>
        </div>
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
            {t("admin.jobs.fields.description")}
          </p>
          <p className="mt-2 whitespace-pre-wrap text-white/75">{job.description}</p>
        </section>
        <section>
          <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
            {t("admin.jobs.fields.requirements")}
          </p>
          <p className="mt-2 whitespace-pre-wrap text-white/75">{job.requirements}</p>
        </section>
      </div>
    </Dialog>
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
  const [form, setForm] = useState<JobUpdate>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!job) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({
      title: job.title,
      description: job.description,
      requirements: job.requirements,
      location: job.location,
      status: job.status,
    });
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [job]);

  function set<K extends keyof JobUpdate>(key: K, value: JobUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!job) return;
    setSaving(true);
    try {
      const updated = await updateJob(job.id, form);
      onSaved(updated);
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  }

  if (!job) return null;
  return (
    <Dialog
      open={job != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.jobs.editModalTitle")}
      description={job.title}
      size="lg"
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
      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <Field label={t("admin.jobs.fields.title")}>
          <input
            type="text"
            value={form.title ?? ""}
            onChange={(e) => set("title", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.location")}>
          <input
            type="text"
            value={form.location ?? ""}
            onChange={(e) => set("location", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.status")}>
          <select
            value={form.status ?? job.status}
            onChange={(e) => set("status", e.target.value as JobStatus)}
            className={selectCls}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s} className="bg-well">
                {t(`admin.jobs.statusLabels.${s}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("admin.jobs.fields.description")} full>
          <textarea
            rows={4}
            value={form.description ?? ""}
            onChange={(e) => set("description", e.target.value)}
            className={textareaCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.requirements")} full>
          <textarea
            rows={3}
            value={form.requirements ?? ""}
            onChange={(e) => set("requirements", e.target.value)}
            className={textareaCls}
          />
        </Field>
      </div>
    </Dialog>
  );
}

// ── Create dialog ──────────────────────────────────────────────────────────

interface CreateProps {
  open: boolean;
  onClose: () => void;
  onCreated: (job: JobRead) => void;
  onError: () => void;
}

function CreateDialog({ open, onClose, onCreated, onError }: CreateProps) {
  const { t } = useTranslation();
  const [companies, setCompanies] = useState<ActiveCompanyRead[] | null>(null);
  const [companiesError, setCompaniesError] = useState(false);
  const [form, setForm] = useState<Partial<JobAdminCreate>>({
    title: "",
    description: "",
    requirements: "",
    location: "",
    status: JobStatus.PUBLISHED,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    /* eslint-disable react-hooks/set-state-in-effect */
    setCompanies(null);
    setCompaniesError(false);
    setForm({
      title: "",
      description: "",
      requirements: "",
      location: "",
      status: JobStatus.PUBLISHED,
    });
    /* eslint-enable react-hooks/set-state-in-effect */
    getActiveCompanies({ limit: 100 })
      .then((page) => {
        if (cancelled) return;
        setCompanies(page.items);
        if (page.items.length > 0) {
          setForm((prev) => ({
            ...prev,
            company_id: page.items[0].company_profile.id,
          }));
        }
      })
      .catch(() => {
        if (!cancelled) setCompaniesError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  function set<K extends keyof JobAdminCreate>(key: K, value: JobAdminCreate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (
      !form.company_id ||
      !form.title ||
      !form.description ||
      !form.requirements ||
      !form.location
    )
      return;
    setSaving(true);
    try {
      const created = await createJob({
        company_id: form.company_id,
        title: form.title,
        description: form.description,
        requirements: form.requirements,
        location: form.location,
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
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.jobs.newJobModalTitle")}
      size="lg"
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
            disabled={
              saving ||
              !form.company_id ||
              !form.title ||
              !form.description ||
              !form.requirements ||
              !form.location
            }
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {saving ? t("common.saving") : t("common.save")}
          </button>
        </>
      }
    >
      <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
        <Field label={t("admin.jobs.fields.company")} full>
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
        <Field label={t("admin.jobs.fields.title")}>
          <input
            type="text"
            value={form.title ?? ""}
            onChange={(e) => set("title", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.location")}>
          <input
            type="text"
            value={form.location ?? ""}
            onChange={(e) => set("location", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.status")}>
          <select
            value={form.status ?? JobStatus.PUBLISHED}
            onChange={(e) => set("status", e.target.value as JobStatus)}
            className={selectCls}
          >
            {ALL_STATUSES.map((s) => (
              <option key={s} value={s} className="bg-well">
                {t(`admin.jobs.statusLabels.${s}`)}
              </option>
            ))}
          </select>
        </Field>
        <Field label={t("admin.jobs.fields.description")} full>
          <textarea
            rows={4}
            value={form.description ?? ""}
            onChange={(e) => set("description", e.target.value)}
            className={textareaCls}
          />
        </Field>
        <Field label={t("admin.jobs.fields.requirements")} full>
          <textarea
            rows={3}
            value={form.requirements ?? ""}
            onChange={(e) => set("requirements", e.target.value)}
            className={textareaCls}
          />
        </Field>
      </div>
    </Dialog>
  );
}

// ── Contact dialog ─────────────────────────────────────────────────────────

interface ContactProps {
  job: JobRead | null;
  onClose: () => void;
  onSent: () => void;
  onError: () => void;
}

function ContactDialog({ job, onClose, onSent, onError }: ContactProps) {
  const { t } = useTranslation();
  const [note, setNote] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!job) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setNote("");
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [job]);

  async function handleSend() {
    if (!job) return;
    setSending(true);
    try {
      await contactJob(job.id, note);
      onSent();
    } catch {
      onError();
    } finally {
      setSending(false);
    }
  }

  if (!job) return null;
  return (
    <Dialog
      open={job != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.jobs.emailModalTitle")}
      description={job.title}
      size="md"
      footer={
        <>
          <button
            onClick={onClose}
            disabled={sending}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/60 hover:border-white/40 hover:text-white/90 disabled:opacity-60"
          >
            {t("common.cancel")}
          </button>
          <button
            onClick={handleSend}
            disabled={sending}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {sending ? t("admin.jobs.emailSending") : t("admin.jobs.emailSend")}
          </button>
        </>
      }
    >
      <label className="block text-sm">
        <span className="block text-xs text-white/45">
          {t("admin.jobs.emailModalLabel")}
        </span>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={5}
          className={`mt-1 ${textareaCls}`}
          placeholder={t("admin.jobs.emailModalPlaceholder")}
        />
      </label>
    </Dialog>
  );
}

// ── Field helper ───────────────────────────────────────────────────────────

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
