import axios from "axios";
import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  adminCreateCompany,
  approveCompany,
  createInvite,
  deleteCompany,
  getActiveCompanies,
  getInvites,
  getJobs,
  getPendingCompanies,
  rejectCompany,
  resendInvite,
  revokeInvite,
  updateCompanyProfile,
} from "@/services/admin";
import type {
  ActiveCompanyRead,
  CompanyProfileAdminCreate,
  CompanyProfileAdminUpdate,
  CompanyProfileRead,
  InviteTokenCreate,
  InviteTokenRead,
  JobRead,
  PendingCompanyRead,
} from "@/types/api";
import { InviteTokenStatus } from "@/types/api";
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
import { inputCls } from "@/styles/forms";

type Tab = "active" | "pending" | "invites";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const COMPANY_ID_RE = /^\d{9}$/;
const MOBILE_RE = /^05[0-9]\d{7}$/;

// ── Page ────────────────────────────────────────────────────────────────────

export default function AdminCompaniesPage() {
  const { t } = useTranslation();
  usePageTitle(t("admin.companies.title"));
  const [tab, setTab] = useState<Tab>("pending");
  const [creating, setCreating] = useState(false);
  const [inviting, setInviting] = useState(false);

  function handleInvite() {
    setTab("invites");
    setInviting(true);
  }

  return (
    <div>
      <h1 data-page-heading className="sr-only">
        {t("admin.companies.title")}
      </h1>
      <PageHeader
        eyebrow={t("admin.companies.title")}
        subtitle={t("admin.companies.subtitle")}
        action={
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              onClick={() => setCreating(true)}
              className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
            >
              {t("admin.companies.newCompany")}
            </button>
            <button
              onClick={handleInvite}
              className="rounded-sm border border-copper/40 px-4 py-2 text-sm font-medium text-copper/80 transition hover:border-copper hover:text-copper"
            >
              {t("admin.companies.inviteForm.newInviteButton")}
            </button>
          </div>
        }
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {(["pending", "active", "invites"] as Tab[]).map((key) => {
          const active = tab === key;
          return (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`rounded-full px-3 py-1 text-sm font-medium transition ${
                active
                  ? "bg-copper text-white"
                  : "border border-white/10 text-white/40 hover:border-white/20 hover:text-white/70"
              }`}
            >
              {t(`admin.companies.tabs.${key}`)}
            </button>
          );
        })}
      </div>

      {tab === "active" && <ActiveTab />}
      {tab === "pending" && <PendingTab />}
      {tab === "invites" && (
        <InvitesTab
          externalOpen={inviting}
          onExternalClose={() => setInviting(false)}
        />
      )}

      <CreateCompanyDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

// ── Active tab ─────────────────────────────────────────────────────────────

function ActiveTab() {
  const { t } = useTranslation();
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<ActiveCompanyRead>> =>
      getActiveCompanies({ cursor }),
    [],
  );

  const {
    items: companies,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    updateItem,
    removeItem,
  } = useInfiniteList<ActiveCompanyRead>(fetcher);

  const [detail, setDetail] = useState<CompanyProfileRead | null>(null);
  const [editing, setEditing] = useState<CompanyProfileRead | null>(null);
  const [deletePending, setDeletePending] = useState<ActiveCompanyRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  async function handleDelete() {
    if (!deletePending) return;
    setPendingMutation(true);
    try {
      await deleteCompany(deletePending.user.id);
      removeItem((c) => c.user.id === deletePending.user.id);
      toast.success(t("admin.companies.deletedToast"));
      setDeletePending(null);
    } catch {
      toast.error(t("admin.companies.active.deleteError"));
    } finally {
      setPendingMutation(false);
    }
  }

  return (
    <>
      {isLoading ? (
        <TableSkeleton rows={5} columns={3} />
      ) : error ? (
        <ErrorState message={t("admin.companies.active.loadError")} onRetry={reload} />
      ) : companies.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.companies.tabs.active")}
          headline={t("admin.companies.active.empty")}
        />
      ) : (
        <>
          <div className="space-y-2 md:hidden">
            {companies.map((row) => (
              <button
                key={row.user.id}
                onClick={() => setDetail(row.company_profile)}
                className="w-full rounded-xl border border-white/8 bg-card px-4 py-3 text-start transition hover:border-white/15"
              >
                <p className="truncate font-medium text-white/85">
                  {row.company_profile.name}
                </p>
                <p className="truncate text-xs text-white/50">{row.user.email}</p>
              </button>
            ))}
          </div>

          <div className="hidden overflow-x-auto rounded-xl border border-white/8 bg-card md:block">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.active.table.company")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.active.table.contact")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.active.table.joined")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {companies.map((row) => (
                  <tr
                    key={row.user.id}
                    onClick={() => setDetail(row.company_profile)}
                    className="cursor-pointer transition hover:bg-white/3"
                  >
                    <td className="px-4 py-3">
                      <p className="font-medium text-white/85">
                        {row.company_profile.name}
                      </p>
                      <p className="text-xs text-white/40">{row.user.email}</p>
                    </td>
                    <td className="px-4 py-3 text-white/60">
                      {row.company_profile.contact_first_name}{" "}
                      {row.company_profile.contact_last_name}
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(row.user.created_at)}
                    </td>
                    <td
                      className="px-4 py-3 text-end"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <DropdownMenu
                        ariaLabel={t("admin.companies.rowActionsLabel")}
                        trigger={
                          <button
                            type="button"
                            className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:bg-white/8 hover:text-white/80"
                          >
                            <span aria-hidden>⋮</span>
                          </button>
                        }
                      >
                        <DropdownMenuItem
                          onSelect={() => setDetail(row.company_profile)}
                        >
                          {t("admin.companies.viewAction")}
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          onSelect={() => setEditing(row.company_profile)}
                        >
                          {t("admin.companies.editAction")}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          variant="danger"
                          onSelect={() => setDeletePending(row)}
                        >
                          {t("admin.companies.deleteAction")}
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

      <CompanyDetailDialog
        profile={detail}
        onClose={() => setDetail(null)}
        onEdit={() => {
          if (detail) setEditing(detail);
          setDetail(null);
        }}
      />

      <EditCompanyDialog
        profile={editing}
        onClose={() => setEditing(null)}
        onSaved={(updated) => {
          updateItem(
            (c) => c.company_profile.id === updated.id,
            (() => {
              const target = companies.find((c) => c.company_profile.id === updated.id);
              return {
                user: target?.user ?? {
                  id: updated.user_id ?? 0,
                  email: "",
                  role: "COMPANY",
                  is_active: true,
                  created_at: updated.created_at,
                },
                company_profile: updated,
              } as ActiveCompanyRead;
            })(),
          );
          toast.success(t("admin.companies.savedToast"));
          setEditing(null);
        }}
      />

      <ConfirmDialog
        open={deletePending != null}
        onOpenChange={(o) => !o && setDeletePending(null)}
        title={t("admin.companies.deleteConfirmTitle")}
        message={t("admin.companies.active.deleteConfirm")}
        confirmLabel={t("admin.companies.deleteAction")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleDelete}
      />
    </>
  );
}

// ── Pending tab ────────────────────────────────────────────────────────────

function PendingTab() {
  const { t } = useTranslation();
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<PendingCompanyRead>> =>
      getPendingCompanies({ cursor }),
    [],
  );

  const {
    items: companies,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    removeItem,
  } = useInfiniteList<PendingCompanyRead>(fetcher);

  const [rejectPending, setRejectPending] = useState<PendingCompanyRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  async function handleApprove(row: PendingCompanyRead) {
    try {
      await approveCompany(row.user.id);
      removeItem((c) => c.user.id === row.user.id);
      toast.success(t("admin.companies.approvedToast"));
    } catch {
      toast.error(t("admin.companies.approveError"));
    }
  }

  async function handleRejectConfirm() {
    if (!rejectPending) return;
    setPendingMutation(true);
    try {
      await rejectCompany(rejectPending.user.id);
      removeItem((c) => c.user.id === rejectPending.user.id);
      toast.success(t("admin.companies.rejectedToast"));
      setRejectPending(null);
    } catch {
      toast.error(t("admin.companies.rejectError"));
    } finally {
      setPendingMutation(false);
    }
  }

  return (
    <>
      {isLoading ? (
        <TableSkeleton rows={4} columns={3} />
      ) : error ? (
        <ErrorState message={t("admin.companies.loadError")} onRetry={reload} />
      ) : companies.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.companies.tabs.pending")}
          headline={t("admin.companies.empty")}
        />
      ) : (
        <>
          <div className="space-y-3">
            {companies.map((row) => (
              <div
                key={row.user.id}
                className="flex flex-col gap-3 rounded-xl border border-white/8 bg-card p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="font-medium text-white/85">
                    {row.company_profile.name}
                  </p>
                  <p className="text-xs text-white/45">{row.user.email}</p>
                  <p className="mt-1 text-xs text-white/35">
                    {t("admin.companies.contactLabel")}:{" "}
                    {row.company_profile.contact_first_name}{" "}
                    {row.company_profile.contact_last_name} ·{" "}
                    {t("admin.companies.registeredLabel")}{" "}
                    {formatDate(row.user.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button
                    onClick={() => handleApprove(row)}
                    className="rounded-sm bg-success/15 px-4 py-1.5 text-sm font-medium text-success hover:bg-success/25"
                  >
                    {t("admin.companies.approveAction")}
                  </button>
                  <button
                    onClick={() => setRejectPending(row)}
                    className="rounded-sm border border-danger/25 px-4 py-1.5 text-sm font-medium text-danger hover:bg-danger/10"
                  >
                    {t("admin.companies.rejectAction")}
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div ref={sentinelRef} />
          {isFetchingMore && (
            <p className="mt-4 text-center text-xs text-white/30">
              {t("common.loading")}
            </p>
          )}
        </>
      )}

      <ConfirmDialog
        open={rejectPending != null}
        onOpenChange={(o) => !o && setRejectPending(null)}
        title={t("admin.companies.rejectConfirmTitle")}
        message={t("admin.companies.rejectConfirm")}
        confirmLabel={t("admin.companies.rejectAction")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleRejectConfirm}
      />
    </>
  );
}

// ── Invites tab ────────────────────────────────────────────────────────────

interface InvitesTabProps {
  externalOpen?: boolean;
  onExternalClose?: () => void;
}

function InvitesTab({ externalOpen, onExternalClose }: InvitesTabProps) {
  const { t } = useTranslation();
  const toast = useToast();

  const fetcher = useCallback(
    (cursor: string | null): Promise<CursorPage<InviteTokenRead>> =>
      getInvites({ cursor }),
    [],
  );

  const {
    items: invites,
    isLoading,
    isFetchingMore,
    error,
    sentinelRef,
    reload,
    prependItem,
    updateItem,
  } = useInfiniteList<InviteTokenRead>(fetcher);

  const [showInviteForm, setShowInviteForm] = useState(false);
  const [revokePending, setRevokePending] = useState<InviteTokenRead | null>(null);
  const [pendingMutation, setPendingMutation] = useState(false);

  useEffect(() => {
    if (externalOpen) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowInviteForm(true);
      onExternalClose?.();
    }
  }, [externalOpen, onExternalClose]);

  async function handleRevokeConfirm() {
    if (!revokePending) return;
    setPendingMutation(true);
    try {
      await revokeInvite(revokePending.id);
      updateItem((i) => i.id === revokePending.id, {
        ...revokePending,
        status: InviteTokenStatus.REVOKED,
      });
      toast.success(t("admin.companies.revokedToast"));
      setRevokePending(null);
    } catch {
      toast.error(t("admin.companies.inviteList.revokeError"));
    } finally {
      setPendingMutation(false);
    }
  }

  async function handleResend(invite: InviteTokenRead) {
    try {
      await resendInvite(invite.id);
      toast.success(t("admin.companies.resentToast"));
    } catch {
      toast.error(t("admin.companies.inviteList.resendError"));
    }
  }

  return (
    <>
      {isLoading ? (
        <TableSkeleton rows={5} columns={4} />
      ) : error ? (
        <ErrorState
          message={t("admin.companies.inviteList.loadError")}
          onRetry={reload}
        />
      ) : invites.length === 0 ? (
        <EmptyState
          eyebrow={t("admin.companies.tabs.invites")}
          headline={t("admin.companies.inviteList.empty")}
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-xl border border-white/8 bg-card">
            <table className="min-w-full divide-y divide-white/6 text-sm">
              <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
                <tr>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.inviteList.columnEmail")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.inviteList.columnStatus")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.inviteList.columnCreated")}
                  </th>
                  <th className="px-4 py-3 text-start">
                    {t("admin.companies.inviteList.columnExpires")}
                  </th>
                  <th className="px-4 py-3 text-end" aria-hidden />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/6">
                {invites.map((invite) => (
                  <tr key={invite.id}>
                    <td className="px-4 py-3 text-white/80">{invite.email}</td>
                    <td className="px-4 py-3">
                      <InviteStatusBadge status={invite.status} />
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(invite.created_at)}
                    </td>
                    <td className="px-4 py-3 text-white/40">
                      {formatDate(invite.expires_at)}
                    </td>
                    <td className="px-4 py-3 text-end">
                      {invite.status === InviteTokenStatus.PENDING && (
                        <DropdownMenu
                          ariaLabel={t("admin.companies.rowActionsLabel")}
                          trigger={
                            <button
                              type="button"
                              className="inline-flex h-8 w-8 items-center justify-center rounded-full text-white/40 transition hover:bg-white/8 hover:text-white/80"
                            >
                              <span aria-hidden>⋮</span>
                            </button>
                          }
                        >
                          <DropdownMenuItem onSelect={() => handleResend(invite)}>
                            {t("admin.companies.resendAction")}
                          </DropdownMenuItem>
                          <DropdownMenuItem
                            variant="danger"
                            onSelect={() => setRevokePending(invite)}
                          >
                            {t("admin.companies.revokeAction")}
                          </DropdownMenuItem>
                        </DropdownMenu>
                      )}
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

      <InviteFormDialog
        open={showInviteForm}
        onClose={() => setShowInviteForm(false)}
        onCreated={(invite) => {
          prependItem(invite);
          setShowInviteForm(false);
        }}
      />

      <ConfirmDialog
        open={revokePending != null}
        onOpenChange={(o) => !o && setRevokePending(null)}
        title={t("admin.companies.revokeConfirmTitle")}
        message={t("admin.companies.inviteList.revokeConfirm")}
        confirmLabel={t("admin.companies.revokeAction")}
        variant="danger"
        isPending={pendingMutation}
        onConfirm={handleRevokeConfirm}
      />
    </>
  );
}

function InviteStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const cls =
    status === InviteTokenStatus.PENDING
      ? "bg-warning/10 text-warning"
      : status === InviteTokenStatus.USED
        ? "bg-success/10 text-success"
        : status === InviteTokenStatus.EXPIRED
          ? "bg-white/8 text-white/40"
          : "bg-danger/10 text-danger";
  return (
    <span
      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}
    >
      {t(`admin.companies.inviteStatusLabels.${status}`)}
    </span>
  );
}

// ── Detail dialog ──────────────────────────────────────────────────────────

interface DetailProps {
  profile: CompanyProfileRead | null;
  onClose: () => void;
  onEdit: () => void;
}

function CompanyDetailDialog({ profile, onClose, onEdit }: DetailProps) {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<JobRead[] | null>(null);
  const [jobsError, setJobsError] = useState(false);

  useEffect(() => {
    if (!profile) return;
    let cancelled = false;
    /* eslint-disable react-hooks/set-state-in-effect */
    setJobs(null);
    setJobsError(false);
    /* eslint-enable react-hooks/set-state-in-effect */
    // No backend ?company_id= filter on /admin/jobs yet; fetch first page and
    // filter client-side. Adequate while companies have ~5 jobs each.
    getJobs({ limit: 100 })
      .then((page) => {
        if (cancelled) return;
        setJobs(page.items.filter((j) => j.company_id === profile.id));
      })
      .catch(() => {
        if (!cancelled) setJobsError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profile]);

  if (!profile) return null;

  return (
    <Dialog
      open={profile != null}
      onOpenChange={(o) => !o && onClose()}
      title={profile.name}
      description={t("admin.companies.detailDescription")}
      size="lg"
      footer={
        <button
          onClick={onEdit}
          className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold"
        >
          {t("admin.companies.editAction")}
        </button>
      }
    >
      <div className="space-y-4 text-sm">
        <dl className="grid grid-cols-1 gap-x-8 gap-y-2 sm:grid-cols-2">
          <dt className="text-white/35">{t("admin.companies.fields.companyId")}</dt>
          <dd className="text-white/70">
            {profile.company_id || t("admin.companies.noCompanyId")}
          </dd>
          {profile.address && (
            <>
              <dt className="text-white/35">{t("admin.companies.fields.address")}</dt>
              <dd className="text-white/70">{profile.address}</dd>
            </>
          )}
          {(profile.contact_first_name || profile.contact_last_name) && (
            <>
              <dt className="text-white/35">{t("admin.companies.contactLabel")}</dt>
              <dd className="text-white/70">
                {profile.contact_first_name} {profile.contact_last_name}
              </dd>
            </>
          )}
          {profile.contact_mobile_phone && (
            <>
              <dt className="text-white/35">
                {t("admin.companies.fields.contactMobile")}
              </dt>
              <dd className="text-white/70">{profile.contact_mobile_phone}</dd>
            </>
          )}
          {profile.contact_landline_phone && (
            <>
              <dt className="text-white/35">
                {t("admin.companies.fields.contactLandline")}
              </dt>
              <dd className="text-white/70">{profile.contact_landline_phone}</dd>
            </>
          )}
          {profile.user_id == null && (
            <>
              <dt className="text-white/35">—</dt>
              <dd className="text-white/40">{t("admin.companies.noUserAccount")}</dd>
            </>
          )}
        </dl>

        <div className="border-t border-white/8 pt-4">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-copper">
            {t("admin.companies.jobsSection")}
          </p>
          {jobsError ? (
            <p className="mt-3 text-xs text-danger">
              {t("admin.companies.errors.jobsLoadFailed")}
            </p>
          ) : jobs == null ? (
            <p className="mt-3 text-xs text-white/35">{t("common.loading")}</p>
          ) : jobs.length === 0 ? (
            <p className="mt-3 text-xs text-white/35">{t("admin.companies.noJobs")}</p>
          ) : (
            <ul className="mt-3 space-y-1.5">
              {jobs.map((j) => (
                <li
                  key={j.id}
                  className="flex items-center justify-between rounded-sm border border-white/6 bg-card px-3 py-2"
                >
                  <span className="text-white/80">{j.title}</span>
                  <span className="text-xs text-white/40">{j.location}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Dialog>
  );
}

// ── Edit company dialog ────────────────────────────────────────────────────

interface EditProps {
  profile: CompanyProfileRead | null;
  onClose: () => void;
  onSaved: (next: CompanyProfileRead) => void;
}

function EditCompanyDialog({ profile, onClose, onSaved }: EditProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [form, setForm] = useState<CompanyProfileAdminUpdate>({});
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({
      name: profile.name,
      company_id: profile.company_id ?? "",
      address: profile.address ?? "",
      contact_first_name: profile.contact_first_name ?? "",
      contact_last_name: profile.contact_last_name ?? "",
      contact_mobile_phone: profile.contact_mobile_phone ?? "",
      contact_landline_phone: profile.contact_landline_phone ?? "",
    });
    setValidationError(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [profile]);

  function set<K extends keyof CompanyProfileAdminUpdate>(
    key: K,
    value: CompanyProfileAdminUpdate[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!profile) return;
    if (form.company_id && !COMPANY_ID_RE.test(form.company_id)) {
      setValidationError(t("admin.companies.validation.companyId"));
      return;
    }
    if (form.contact_mobile_phone && !MOBILE_RE.test(form.contact_mobile_phone)) {
      setValidationError(t("admin.companies.validation.mobile"));
      return;
    }
    setSaving(true);
    setValidationError(null);
    try {
      const updated = await updateCompanyProfile(profile.id, {
        ...form,
        contact_landline_phone: form.contact_landline_phone || null,
      });
      onSaved(updated);
    } catch {
      toast.error(t("admin.companies.errors.saveFailed"));
    } finally {
      setSaving(false);
    }
  }

  if (!profile) return null;

  return (
    <Dialog
      open={profile != null}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.companies.editModalTitle")}
      description={profile.name}
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
      <CompanyProfileFields
        form={form}
        setField={(k, v) =>
          set(
            k as keyof CompanyProfileAdminUpdate,
            v as CompanyProfileAdminUpdate[keyof CompanyProfileAdminUpdate],
          )
        }
      />
      {validationError && <p className="mt-3 text-xs text-danger">{validationError}</p>}
    </Dialog>
  );
}

// ── Create company dialog ──────────────────────────────────────────────────

interface CreateProps {
  open: boolean;
  onClose: () => void;
}

function CreateCompanyDialog({ open, onClose }: CreateProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [form, setForm] = useState<Partial<CompanyProfileAdminCreate>>({});
  const [saving, setSaving] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({});
    setValidationError(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [open]);

  function set<K extends keyof CompanyProfileAdminCreate>(
    key: K,
    value: CompanyProfileAdminCreate[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setValidationError(null);
    if (
      !form.name ||
      !form.company_id ||
      !form.address ||
      !form.contact_first_name ||
      !form.contact_last_name ||
      !form.contact_mobile_phone
    ) {
      return;
    }
    if (!COMPANY_ID_RE.test(form.company_id)) {
      setValidationError(t("admin.companies.validation.companyId"));
      return;
    }
    if (!MOBILE_RE.test(form.contact_mobile_phone)) {
      setValidationError(t("admin.companies.validation.mobile"));
      return;
    }
    setSaving(true);
    try {
      await adminCreateCompany({
        name: form.name,
        company_id: form.company_id,
        address: form.address,
        contact_first_name: form.contact_first_name,
        contact_last_name: form.contact_last_name,
        contact_mobile_phone: form.contact_mobile_phone,
        contact_landline_phone: form.contact_landline_phone || null,
      });
      toast.success(t("admin.companies.createdToast"));
      onClose();
      // The active list won't auto-refresh — admin-created companies don't
      // appear in the active list until they have a user account anyway.
    } catch {
      toast.error(t("admin.companies.errors.createFailed"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.companies.newCompanyModalTitle")}
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
      <CompanyProfileFields
        form={form}
        setField={(k, v) =>
          set(
            k as keyof CompanyProfileAdminCreate,
            v as CompanyProfileAdminCreate[keyof CompanyProfileAdminCreate],
          )
        }
      />
      {validationError && <p className="mt-3 text-xs text-danger">{validationError}</p>}
    </Dialog>
  );
}

// ── Shared profile field group ─────────────────────────────────────────────

interface ProfileFieldsProps {
  form: CompanyProfileAdminUpdate | Partial<CompanyProfileAdminCreate>;
  setField: (key: string, value: string) => void;
}

function CompanyProfileFields({ form, setField }: ProfileFieldsProps) {
  const { t } = useTranslation();
  return (
    <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
      <Field label={t("admin.companies.fields.name")} full>
        <input
          type="text"
          value={form.name ?? ""}
          onChange={(e) => setField("name", e.target.value)}
          className={inputCls}
        />
      </Field>
      <Field label={t("admin.companies.fields.companyId")}>
        <input
          type="text"
          inputMode="numeric"
          value={form.company_id ?? ""}
          onChange={(e) => setField("company_id", e.target.value)}
          className={inputCls}
          placeholder="123456789"
        />
      </Field>
      <Field label={t("admin.companies.fields.address")}>
        <input
          type="text"
          value={form.address ?? ""}
          onChange={(e) => setField("address", e.target.value)}
          className={inputCls}
        />
      </Field>
      <Field label={t("admin.companies.fields.contactFirstName")}>
        <input
          type="text"
          value={form.contact_first_name ?? ""}
          onChange={(e) => setField("contact_first_name", e.target.value)}
          className={inputCls}
        />
      </Field>
      <Field label={t("admin.companies.fields.contactLastName")}>
        <input
          type="text"
          value={form.contact_last_name ?? ""}
          onChange={(e) => setField("contact_last_name", e.target.value)}
          className={inputCls}
        />
      </Field>
      <Field label={t("admin.companies.fields.contactMobile")}>
        <input
          type="tel"
          value={form.contact_mobile_phone ?? ""}
          onChange={(e) => setField("contact_mobile_phone", e.target.value)}
          className={inputCls}
          placeholder="0501234567"
        />
      </Field>
      <Field label={t("admin.companies.fields.contactLandline")}>
        <input
          type="tel"
          value={form.contact_landline_phone ?? ""}
          onChange={(e) => setField("contact_landline_phone", e.target.value)}
          className={inputCls}
        />
      </Field>
    </div>
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

// ── Invite form dialog ─────────────────────────────────────────────────────

interface InviteFormProps {
  open: boolean;
  onClose: () => void;
  onCreated: (invite: InviteTokenRead) => void;
}

function InviteFormDialog({ open, onClose, onCreated }: InviteFormProps) {
  const { t } = useTranslation();
  const toast = useToast();
  const [form, setForm] = useState<InviteTokenCreate>({ email: "" });
  const [submitting, setSubmitting] = useState(false);
  const [errorKey, setErrorKey] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    /* eslint-disable react-hooks/set-state-in-effect */
    setForm({ email: "" });
    setErrorKey(null);
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [open]);

  async function handleSubmit() {
    setErrorKey(null);
    setSubmitting(true);
    try {
      const created = await createInvite(form);
      toast.success(t("admin.companies.inviteForm.successMessage"));
      onCreated(created);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response.data?.detail ?? "";
        if (
          typeof detail === "string" &&
          detail.toLowerCase().includes("pending invite")
        ) {
          setErrorKey("admin.companies.inviteForm.errorPendingInvite");
        } else {
          setErrorKey("admin.companies.inviteForm.errorEmailExists");
        }
      } else {
        setErrorKey("admin.companies.inviteForm.errorMessage");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={t("admin.companies.inviteForm.title")}
      size="md"
      footer={
        <>
          <button
            onClick={onClose}
            disabled={submitting}
            className="rounded-sm border border-white/20 px-4 py-2 text-sm text-white/60 hover:border-white/40 hover:text-white/90 disabled:opacity-60"
          >
            {t("admin.companies.inviteForm.cancelButton")}
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !form.email}
            className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white hover:bg-gold disabled:opacity-60"
          >
            {submitting
              ? t("admin.companies.inviteForm.submittingButton")
              : t("admin.companies.inviteForm.submitButton")}
          </button>
        </>
      }
    >
      <label className="block text-sm">
        <span className="block text-xs text-white/45">
          {t("admin.companies.inviteForm.emailLabel")}
        </span>
        <input
          type="email"
          value={form.email}
          onChange={(e) => setForm({ email: e.target.value })}
          className={`mt-1 ${inputCls}`}
          placeholder={t("admin.companies.inviteForm.emailPlaceholder")}
        />
      </label>
      {errorKey && <p className="mt-3 text-xs text-danger">{t(errorKey)}</p>}
    </Dialog>
  );
}
