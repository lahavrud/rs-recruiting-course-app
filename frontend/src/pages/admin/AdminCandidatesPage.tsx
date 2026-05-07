import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  deleteCandidate,
  fetchResumeBlob,
  getApplications,
  getCandidate,
  getCandidates,
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
import DropdownMenu, {
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/DropdownMenu";
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

  // Auto-open detail modal when navigated from another page via ?detail=<id>
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("detail");
    if (!id || Number.isNaN(Number(id))) return;
    window.history.replaceState({}, "", window.location.pathname);
    getCandidate(Number(id)).then(setDetail).catch(() => toast.error(t("common.genericError")));
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

      {isLoading ? (
        <TableSkeleton rows={6} columns={4} />
      ) : error ? (
        <ErrorState message={t("admin.candidates.loadError")} onRetry={reload} />
      ) : candidates.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.candidates.title")}
          headline={t("admin.candidates.empty")}
        />
      ) : (
        <>
          {/* Mobile cards */}
          <div className="space-y-2 md:hidden">
            {candidates.map((c) => (
              <button
                key={c.id}
                onClick={() => setDetail(c)}
                className="w-full rounded-xl border border-white/8 bg-card px-4 py-3 text-start transition hover:border-white/15"
              >
                <p className="truncate font-medium text-white/85">{c.full_name}</p>
                <p className="truncate text-xs text-white/50">{c.email}</p>
                <p className="mt-2 text-xs text-white/35">{formatDate(c.created_at)}</p>
              </button>
            ))}
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
                {candidates.map((c) => (
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
        title={t("admin.candidates.deleteConfirmTitle")}
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
  const navigate = useNavigate();
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
    let cancelled = false;
    setApplications(null);
    setAppsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    getApplications({ candidate_id: candidate.id, limit: 100 })
      .then((page) => {
        if (!cancelled) setApplications(page.items);
      })
      .catch(() => {
        if (!cancelled) setAppsError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [candidate]);

  if (!candidate) return null;
  const c = candidate;
  const hasAnswers =
    c.service_concept ||
    c.salary_expectations ||
    c.personality_strength ||
    c.personality_weakness;

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
      <div className="space-y-5 text-sm">
        <div className="flex flex-wrap gap-x-6 gap-y-1">
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

        {/* Applications by this candidate */}
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
                    onClick={() => { onClose(); navigate(`/admin/applications?candidate=${a.candidate_id}`, { state: { autoOpen: a } }); }}
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
    </Dialog>
  );
}

// ── Edit dialog ────────────────────────────────────────────────────────────

interface EditProps {
  candidate: CandidateProfileRead | null;
  onClose: () => void;
  onSaved: (next: CandidateProfileRead) => void;
  onError: () => void;
}

function EditDialog({ candidate, onClose, onSaved, onError }: EditProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState<CandidateProfileUpdate>({});
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Re-seed form when target candidate changes — same one-shot reset
  // pattern as in the detail dialog above.
  useEffect(() => {
    if (!candidate) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({
      full_name: candidate.full_name,
      email: candidate.email,
      phone: candidate.phone ?? "",
      linkedin_url: candidate.linkedin_url ?? "",
      service_concept: candidate.service_concept ?? "",
      salary_expectations: candidate.salary_expectations ?? "",
      personality_strength: candidate.personality_strength ?? "",
      personality_weakness: candidate.personality_weakness ?? "",
    });
    setValidationError(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [candidate]);

  function set<K extends keyof CandidateProfileUpdate>(
    key: K,
    value: CandidateProfileUpdate[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!candidate) return;
    setSaving(true);
    setValidationError(null);
    // Backend rejects empty strings on optional nullable fields; send null
    // when the user emptied the field.
    const body: CandidateProfileUpdate = {
      full_name: form.full_name,
      email: form.email,
      phone: form.phone?.trim() ? form.phone : null,
      linkedin_url: form.linkedin_url?.trim() ? form.linkedin_url : null,
      service_concept: form.service_concept?.trim() ? form.service_concept : null,
      salary_expectations: form.salary_expectations?.trim()
        ? form.salary_expectations
        : null,
      personality_strength: form.personality_strength?.trim()
        ? form.personality_strength
        : null,
      personality_weakness: form.personality_weakness?.trim()
        ? form.personality_weakness
        : null,
    };
    try {
      const updated = await updateCandidate(candidate.id, body);
      onSaved(updated);
    } catch (err: unknown) {
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      if (status === 422) {
        setValidationError(t("admin.candidates.errors.saveFailed"));
      } else {
        onError();
      }
    } finally {
      setSaving(false);
    }
  }

  if (!candidate) return null;

  return (
    <Dialog
      open={candidate != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.candidates.editModalTitle")}
      description={candidate.email}
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
        <Field label={t("admin.candidates.fields.fullName")}>
          <input
            type="text"
            value={form.full_name ?? ""}
            onChange={(e) => set("full_name", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.email")}>
          <input
            type="email"
            value={form.email ?? ""}
            onChange={(e) => set("email", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.phone")}>
          <input
            type="tel"
            value={form.phone ?? ""}
            onChange={(e) => set("phone", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.linkedin")}>
          <input
            type="url"
            value={form.linkedin_url ?? ""}
            onChange={(e) => set("linkedin_url", e.target.value)}
            className={inputCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.serviceConcept")} full>
          <textarea
            rows={2}
            value={form.service_concept ?? ""}
            onChange={(e) => set("service_concept", e.target.value)}
            className={textareaCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.salaryExpectations")} full>
          <textarea
            rows={2}
            value={form.salary_expectations ?? ""}
            onChange={(e) => set("salary_expectations", e.target.value)}
            className={textareaCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.strength")} full>
          <textarea
            rows={2}
            value={form.personality_strength ?? ""}
            onChange={(e) => set("personality_strength", e.target.value)}
            className={textareaCls}
          />
        </Field>
        <Field label={t("admin.candidates.fields.weakness")} full>
          <textarea
            rows={2}
            value={form.personality_weakness ?? ""}
            onChange={(e) => set("personality_weakness", e.target.value)}
            className={textareaCls}
          />
        </Field>
      </div>
      {validationError && <p className="mt-3 text-xs text-danger">{validationError}</p>}
    </Dialog>
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
