import axios from "axios";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  approveCompany,
  createInvite,
  deleteCompany,
  getActiveCompanies,
  getInvites,
  getPendingCompanies,
  rejectCompany,
  resendInvite,
  revokeInvite,
} from "@/services/admin";
import type {
  ActiveCompanyRead,
  InviteTokenCreate,
  InviteTokenRead,
  PendingCompanyRead,
} from "@/types/api";
import { InviteTokenStatus } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import { inputCls, selectCls } from "@/styles/forms";

type Tab = "pending" | "active" | "invites";
type CompanySort = "name_asc" | "name_desc" | "date_newest" | "date_oldest";

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
  const cls =
    status === InviteTokenStatus.PENDING
      ? "bg-warning/10 text-warning"
      : status === InviteTokenStatus.USED
        ? "bg-success/10 text-success"
        : status === InviteTokenStatus.EXPIRED
          ? "bg-white/10 text-white/40"
          : "bg-danger/10 text-danger";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {t(`admin.companies.inviteStatusLabels.${status}`)}
    </span>
  );
}

const EMPTY_INVITE: InviteTokenCreate = {
  email: "",
  company_name: "",
  contact_first_name: "",
  contact_last_name: "",
  note: "",
};

export default function AdminCompaniesPage() {
  const { t } = useTranslation();

  // ── Tab state ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>("pending");

  // ── Pending companies ──────────────────────────────────────────────────────
  const [companies, setCompanies] = useState<PendingCompanyRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);

  useEffect(() => {
    getPendingCompanies()
      .then(setCompanies)
      .catch(() => setError(t("admin.companies.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleApprove(userId: number) {
    setActing(userId);
    try {
      await approveCompany(userId);
      setCompanies((prev) => prev.filter((c) => c.user.id !== userId));
    } catch {
      setError(t("admin.companies.approveError"));
    } finally {
      setActing(null);
    }
  }

  async function handleReject(userId: number) {
    if (!confirm(t("admin.companies.rejectConfirm"))) return;
    setActing(userId);
    try {
      await rejectCompany(userId);
      setCompanies((prev) => prev.filter((c) => c.user.id !== userId));
    } catch {
      setError(t("admin.companies.rejectError"));
    } finally {
      setActing(null);
    }
  }

  // ── Invites ────────────────────────────────────────────────────────────────
  const [invites, setInvites] = useState<InviteTokenRead[]>([]);
  const [invitesLoading, setInvitesLoading] = useState(true);
  const [invitesError, setInvitesError] = useState<string | null>(null);
  const [showInviteForm, setShowInviteForm] = useState(false);
  const [inviteForm, setInviteForm] = useState<InviteTokenCreate>(EMPTY_INVITE);
  const [submittingInvite, setSubmittingInvite] = useState(false);
  const [inviteFormError, setInviteFormError] = useState<string | null>(null);
  const [inviteFormSuccess, setInviteFormSuccess] = useState(false);
  const [actingInvite, setActingInvite] = useState<number | null>(null);

  const [invitesVersion, setInvitesVersion] = useState(0);

  function reloadInvites() {
    setInvitesLoading(true);
    setInvitesVersion((v) => v + 1);
  }

  useEffect(() => {
    if (activeTab !== "invites") return;
    getInvites()
      .then((data) => {
        setInvites(data);
        setInvitesError(null);
      })
      .catch(() => setInvitesError(t("admin.companies.inviteList.loadError")))
      .finally(() => setInvitesLoading(false));
  }, [activeTab, invitesVersion, t]);

  async function handleSendInvite(e: React.FormEvent) {
    e.preventDefault();
    setSubmittingInvite(true);
    setInviteFormError(null);
    try {
      const payload: InviteTokenCreate = {
        email: inviteForm.email,
        company_name: inviteForm.company_name || null,
        contact_first_name: inviteForm.contact_first_name || null,
        contact_last_name: inviteForm.contact_last_name || null,
        note: inviteForm.note || null,
      };
      const created = await createInvite(payload);
      setInvites((prev) => [created, ...prev]);
      setInviteForm(EMPTY_INVITE);
      setShowInviteForm(false);
      setInviteFormSuccess(true);
      setTimeout(() => setInviteFormSuccess(false), 3000);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 409) {
        const detail = err.response.data?.detail ?? "";
        if (detail.toLowerCase().includes("pending invite")) {
          setInviteFormError(t("admin.companies.inviteForm.errorPendingInvite"));
        } else {
          setInviteFormError(t("admin.companies.inviteForm.errorEmailExists"));
        }
      } else {
        setInviteFormError(t("admin.companies.inviteForm.errorMessage"));
      }
    } finally {
      setSubmittingInvite(false);
    }
  }

  async function handleRevokeInvite(invite: InviteTokenRead) {
    if (!confirm(t("admin.companies.inviteList.revokeConfirm"))) return;
    setActingInvite(invite.id);
    try {
      await revokeInvite(invite.id);
      setInvites((prev) =>
        prev.map((i) =>
          i.id === invite.id ? { ...i, status: InviteTokenStatus.REVOKED } : i,
        ),
      );
    } catch {
      setInvitesError(t("admin.companies.inviteList.revokeError"));
    } finally {
      setActingInvite(null);
    }
  }

  async function handleResendInvite(invite: InviteTokenRead) {
    setActingInvite(invite.id);
    try {
      await resendInvite(invite.id);
      reloadInvites();
    } catch {
      setInvitesError(t("admin.companies.inviteList.resendError"));
    } finally {
      setActingInvite(null);
    }
  }

  // ── Active companies ────────────────────────────────────────────────────────
  const [activeCompanies, setActiveCompanies] = useState<ActiveCompanyRead[]>([]);
  const [activeCompaniesLoading, setActiveCompaniesLoading] = useState(false);
  const [activeCompaniesError, setActiveCompaniesError] = useState<string | null>(null);
  const [companySearch, setCompanySearch] = useState("");
  const [companySort, setCompanySort] = useState<CompanySort>("date_newest");
  const [actingCompany, setActingCompany] = useState<number | null>(null);

  useEffect(() => {
    if (activeTab !== "active") return;
    getActiveCompanies()
      .then((data) => {
        setActiveCompanies(data);
        setActiveCompaniesError(null);
      })
      .catch(() => setActiveCompaniesError(t("admin.companies.active.loadError")))
      .finally(() => setActiveCompaniesLoading(false));
  }, [activeTab, t]);

  const displayedCompanies = useMemo(() => {
    let list = activeCompanies;
    const q = companySearch.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (c) =>
          c.company_profile.name.toLowerCase().includes(q) ||
          c.user.email.toLowerCase().includes(q),
      );
    }
    return [...list].sort((a, b) => {
      if (companySort === "name_asc")
        return a.company_profile.name.localeCompare(b.company_profile.name, "he");
      if (companySort === "name_desc")
        return b.company_profile.name.localeCompare(a.company_profile.name, "he");
      if (companySort === "date_oldest")
        return new Date(a.user.created_at).getTime() - new Date(b.user.created_at).getTime();
      return new Date(b.user.created_at).getTime() - new Date(a.user.created_at).getTime();
    });
  }, [activeCompanies, companySearch, companySort]);

  async function handleDeleteCompany(userId: number) {
    if (!confirm(t("admin.companies.active.deleteConfirm"))) return;
    setActingCompany(userId);
    try {
      await deleteCompany(userId);
      setActiveCompanies((prev) => prev.filter((c) => c.user.id !== userId));
    } catch {
      setActiveCompaniesError(t("admin.companies.active.deleteError"));
    } finally {
      setActingCompany(null);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow={t("admin.companies.title")}
        subtitle={t("admin.companies.subtitle")}
      />

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 border-b border-white/8">
        <button
          onClick={() => setActiveTab("pending")}
          className={`px-4 py-2 text-sm font-medium transition ${
            activeTab === "pending"
              ? "border-b-2 border-copper text-copper"
              : "text-white/50 hover:text-white/75"
          }`}
        >
          {t("admin.companies.tabs.pending")}
          {!loading && companies.length > 0 && (
            <span className="mr-2 rounded-full bg-warning/15 px-2 py-0.5 text-xs text-warning">
              {companies.length}
            </span>
          )}
        </button>
        <button
          onClick={() => {
            setActiveTab("active");
            setActiveCompaniesLoading(true);
          }}
          className={`px-4 py-2 text-sm font-medium transition ${
            activeTab === "active"
              ? "border-b-2 border-copper text-copper"
              : "text-white/50 hover:text-white/75"
          }`}
        >
          {t("admin.companies.tabs.active")}
        </button>
        <button
          onClick={() => {
            setActiveTab("invites");
            setInvitesLoading(true);
          }}
          className={`px-4 py-2 text-sm font-medium transition ${
            activeTab === "invites"
              ? "border-b-2 border-copper text-copper"
              : "text-white/50 hover:text-white/75"
          }`}
        >
          {t("admin.companies.tabs.invites")}
        </button>
      </div>

      {/* ── Pending tab ─────────────────────────────────────────────────────── */}
      {activeTab === "pending" && (
        <>
          {error && (
            <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
              {error}
            </div>
          )}
          {loading ? (
            <div className="flex justify-center py-16 text-white/25">
              {t("admin.companies.loading")}
            </div>
          ) : companies.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
              {t("admin.companies.empty")}
            </div>
          ) : (
            <div className="space-y-3">
              {companies.map((c) => {
                const busy = acting === c.user.id;
                return (
                  <div
                    key={c.user.id}
                    className="flex flex-col gap-4 rounded-xl border border-white/8 bg-card p-5 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="font-medium text-white/85">{c.company_profile.name}</p>
                      <p className="mt-0.5 text-sm text-white/45">{c.user.email}</p>
                      {(c.company_profile.contact_first_name ||
                        c.company_profile.contact_last_name) && (
                        <p className="text-sm text-white/45">
                          {t("admin.companies.contactLabel")}:{" "}
                          {[
                            c.company_profile.contact_first_name,
                            c.company_profile.contact_last_name,
                          ]
                            .filter(Boolean)
                            .join(" ")}
                          {c.company_profile.contact_mobile_phone &&
                            ` · ${c.company_profile.contact_mobile_phone}`}
                        </p>
                      )}
                      <p className="mt-1 text-xs text-white/25">
                        {t("admin.companies.registeredLabel")} {formatDate(c.user.created_at)}
                      </p>
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <button
                        onClick={() => handleApprove(c.user.id)}
                        disabled={busy}
                        className="rounded-sm bg-success/15 px-4 py-1.5 text-sm font-medium text-success transition hover:bg-success/25 disabled:opacity-40"
                      >
                        {busy ? "…" : t("admin.companies.approve")}
                      </button>
                      <button
                        onClick={() => handleReject(c.user.id)}
                        disabled={busy}
                        className="rounded-sm border border-danger/25 px-4 py-1.5 text-sm font-medium text-danger transition hover:bg-danger/10 disabled:opacity-40"
                      >
                        {busy ? "…" : t("admin.companies.reject")}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ── Active companies tab ────────────────────────────────────────────── */}
      {activeTab === "active" && (
        <div>
          {activeCompaniesError && (
            <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
              {activeCompaniesError}
            </div>
          )}

          {/* Controls: search + sort */}
          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={companySearch}
              onChange={(e) => setCompanySearch(e.target.value)}
              placeholder={t("admin.companies.active.searchPlaceholder")}
              className="w-full rounded-lg border border-white/10 bg-well px-4 py-2 text-sm text-white/80 placeholder:text-white/25 focus:border-copper/40 focus:outline-none sm:max-w-xs"
            />
            <select
              value={companySort}
              onChange={(e) => setCompanySort(e.target.value as CompanySort)}
              className={`${selectCls} sm:w-56`}
            >
              <option value="date_newest">{t("admin.companies.active.sortDateNewest")}</option>
              <option value="date_oldest">{t("admin.companies.active.sortDateOldest")}</option>
              <option value="name_asc">{t("admin.companies.active.sortNameAsc")}</option>
              <option value="name_desc">{t("admin.companies.active.sortNameDesc")}</option>
            </select>
          </div>

          {activeCompaniesLoading ? (
            <div className="flex justify-center py-16 text-white/25">
              {t("admin.companies.active.loading")}
            </div>
          ) : displayedCompanies.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
              {t("admin.companies.active.empty")}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/8">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/8 bg-well text-left text-xs text-white/40">
                    <th className="px-4 py-3">{t("admin.companies.active.table.company")}</th>
                    <th className="px-4 py-3">{t("admin.companies.active.table.contact")}</th>
                    <th className="px-4 py-3">{t("admin.companies.active.table.joined")}</th>
                    <th className="px-4 py-3">{t("admin.companies.active.table.actions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedCompanies.map((c) => {
                    const busy = actingCompany === c.user.id;
                    const contact = [
                      c.company_profile.contact_first_name,
                      c.company_profile.contact_last_name,
                    ]
                      .filter(Boolean)
                      .join(" ");
                    return (
                      <tr
                        key={c.user.id}
                        className="border-b border-white/5 last:border-0 hover:bg-card-raised/50"
                      >
                        <td className="px-4 py-3">
                          <p className="font-medium text-white/85">{c.company_profile.name}</p>
                          <p className="text-xs text-white/40">{c.user.email}</p>
                        </td>
                        <td className="px-4 py-3 text-white/50">{contact || "—"}</td>
                        <td className="px-4 py-3 text-white/40">{formatDate(c.user.created_at)}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => handleDeleteCompany(c.user.id)}
                            disabled={busy}
                            className="rounded-sm border border-danger/25 px-3 py-1 text-xs text-danger transition hover:bg-danger/10 disabled:opacity-40"
                          >
                            {busy ? "…" : t("admin.companies.active.delete")}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Invites tab ─────────────────────────────────────────────────────── */}
      {activeTab === "invites" && (
        <div>
          {/* Top action row */}
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-white/40">{t("admin.companies.inviteList.title")}</p>
            <div className="flex items-center gap-3">
              {inviteFormSuccess && (
                <span className="text-sm text-success">
                  {t("admin.companies.inviteForm.successMessage")}
                </span>
              )}
              <button
                onClick={() => {
                  setShowInviteForm((v) => !v);
                  setInviteFormError(null);
                }}
                className="rounded-sm bg-copper px-4 py-1.5 text-sm font-medium text-white transition hover:bg-gold"
              >
                {showInviteForm
                  ? t("admin.companies.inviteForm.cancelButton")
                  : t("admin.companies.inviteForm.newInviteButton")}
              </button>
            </div>
          </div>

          {/* Create invite form */}
          {showInviteForm && (
            <form
              onSubmit={handleSendInvite}
              className="mb-6 rounded-xl border border-white/8 bg-card p-5"
            >
              <p className="mb-4 text-sm font-medium text-white/75">
                {t("admin.companies.inviteForm.title")}
              </p>
              {inviteFormError && (
                <div className="mb-4 rounded-lg border border-danger/25 bg-danger/10 px-4 py-3 text-sm text-danger">
                  {inviteFormError}
                </div>
              )}
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    {t("admin.companies.inviteForm.emailLabel")} *
                  </label>
                  <input
                    type="email"
                    required
                    value={inviteForm.email}
                    onChange={(e) =>
                      setInviteForm((p) => ({ ...p, email: e.target.value }))
                    }
                    placeholder={t("admin.companies.inviteForm.emailPlaceholder")}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    {t("admin.companies.inviteForm.companyNameLabel")}
                  </label>
                  <input
                    type="text"
                    value={inviteForm.company_name ?? ""}
                    onChange={(e) =>
                      setInviteForm((p) => ({ ...p, company_name: e.target.value }))
                    }
                    placeholder={t("admin.companies.inviteForm.companyNamePlaceholder")}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    {t("admin.companies.inviteForm.contactFirstNameLabel")}
                  </label>
                  <input
                    type="text"
                    value={inviteForm.contact_first_name ?? ""}
                    onChange={(e) =>
                      setInviteForm((p) => ({
                        ...p,
                        contact_first_name: e.target.value,
                      }))
                    }
                    placeholder={t(
                      "admin.companies.inviteForm.contactFirstNamePlaceholder",
                    )}
                    className={inputCls}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-white/50">
                    {t("admin.companies.inviteForm.contactLastNameLabel")}
                  </label>
                  <input
                    type="text"
                    value={inviteForm.contact_last_name ?? ""}
                    onChange={(e) =>
                      setInviteForm((p) => ({
                        ...p,
                        contact_last_name: e.target.value,
                      }))
                    }
                    placeholder={t(
                      "admin.companies.inviteForm.contactLastNamePlaceholder",
                    )}
                    className={inputCls}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-xs text-white/50">
                    {t("admin.companies.inviteForm.noteLabel")}
                  </label>
                  <input
                    type="text"
                    value={inviteForm.note ?? ""}
                    onChange={(e) =>
                      setInviteForm((p) => ({ ...p, note: e.target.value }))
                    }
                    placeholder={t("admin.companies.inviteForm.notePlaceholder")}
                    className={inputCls}
                  />
                </div>
              </div>
              <div className="mt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={submittingInvite}
                  className="rounded-sm bg-copper px-5 py-2 text-sm font-medium text-white transition hover:bg-gold disabled:opacity-40"
                >
                  {submittingInvite
                    ? t("admin.companies.inviteForm.submittingButton")
                    : t("admin.companies.inviteForm.submitButton")}
                </button>
              </div>
            </form>
          )}

          {/* Error banner */}
          {invitesError && (
            <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">
              {invitesError}
            </div>
          )}

          {/* Invite list */}
          {invitesLoading ? (
            <div className="flex justify-center py-16 text-white/25">
              {t("admin.companies.loading")}
            </div>
          ) : invites.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
              {t("admin.companies.inviteList.empty")}
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/8">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/8 bg-well text-left text-xs text-white/40">
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnEmail")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnCompany")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnContact")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnStatus")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnCreated")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnExpires")}</th>
                    <th className="px-4 py-3">{t("admin.companies.inviteList.columnActions")}</th>
                  </tr>
                </thead>
                <tbody>
                  {invites.map((inv) => {
                    const busy = actingInvite === inv.id;
                    const contactName = [inv.contact_first_name, inv.contact_last_name]
                      .filter(Boolean)
                      .join(" ");
                    return (
                      <tr
                        key={inv.id}
                        className="border-b border-white/5 last:border-0 hover:bg-card-raised/50"
                      >
                        <td className="px-4 py-3 text-white/75">{inv.email}</td>
                        <td className="px-4 py-3 text-white/50">{inv.company_name || "—"}</td>
                        <td className="px-4 py-3 text-white/50">{contactName || "—"}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={inv.status} />
                        </td>
                        <td className="px-4 py-3 text-white/40">
                          {formatDate(inv.created_at)}
                        </td>
                        <td className="px-4 py-3 text-white/40">
                          {formatDate(inv.expires_at)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex gap-2">
                            {inv.status === InviteTokenStatus.PENDING && (
                              <button
                                onClick={() => handleRevokeInvite(inv)}
                                disabled={busy}
                                className="rounded-sm border border-danger/25 px-3 py-1 text-xs text-danger transition hover:bg-danger/10 disabled:opacity-40"
                              >
                                {t("admin.companies.inviteList.revokeButton")}
                              </button>
                            )}
                            {(inv.status === InviteTokenStatus.PENDING ||
                              inv.status === InviteTokenStatus.EXPIRED) && (
                              <button
                                onClick={() => handleResendInvite(inv)}
                                disabled={busy}
                                className="rounded-sm border border-white/15 px-3 py-1 text-xs text-white/60 transition hover:border-white/30 hover:text-white/85 disabled:opacity-40"
                              >
                                {busy
                                  ? "…"
                                  : t("admin.companies.inviteList.resendButton")}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
