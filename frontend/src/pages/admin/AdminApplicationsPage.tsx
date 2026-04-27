import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getApplications, updateApplicationStatus } from "@/services/admin";
import { ApplicationStatus } from "@/types/api";
import type { ApplicationStatusUpdate, ApplicationWithDetails } from "@/types/api";
import PageHeader from "@/components/ui/PageHeader";
import { selectCls, textareaCls } from "@/styles/forms";

const NEXT_STATUSES: Record<string, string[]> = {
  NEW: [ApplicationStatus.APPROVED_BY_ADMIN, ApplicationStatus.REJECTED],
  APPROVED_BY_ADMIN: [ApplicationStatus.HIRED, ApplicationStatus.REJECTED],
  REJECTED: [],
  HIRED: [],
};

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-copper/10 text-copper",
  APPROVED_BY_ADMIN: "bg-success/10 text-success",
  REJECTED: "bg-danger/10 text-danger",
  HIRED: "bg-hired/10 text-hired",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const ALL_FILTER = "ALL";
type FilterValue = string;

interface UpdateModal {
  app: ApplicationWithDetails;
}

export default function AdminApplicationsPage() {
  const { t } = useTranslation();
  const [applications, setApplications] = useState<ApplicationWithDetails[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterValue>(ALL_FILTER);

  const [modal, setModal] = useState<UpdateModal | null>(null);
  const [newStatus, setNewStatus] = useState<string>("");
  const [adminNotes, setAdminNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    getApplications()
      .then(setApplications)
      .catch(() => setError(t("admin.applications.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  const filtered =
    filter === ALL_FILTER
      ? applications
      : applications.filter((a) => a.status === filter);

  const STATUS_LABELS: Record<string, string> = {
    NEW: t("admin.applications.statusLabels.NEW"),
    APPROVED_BY_ADMIN: t("admin.applications.statusLabels.APPROVED_BY_ADMIN"),
    REJECTED: t("admin.applications.statusLabels.REJECTED"),
    HIRED: t("admin.applications.statusLabels.HIRED"),
  };

  function openModal(app: ApplicationWithDetails) {
    const nexts = NEXT_STATUSES[app.status] ?? [];
    setModal({ app });
    setNewStatus(nexts[0] ?? "");
    setAdminNotes(app.admin_notes ?? "");
    setSaveError(null);
  }

  function closeModal() {
    setModal(null);
    setSaveError(null);
  }

  async function handleSaveStatus() {
    if (!modal || !newStatus) return;
    setSaving(true);
    setSaveError(null);
    const body: ApplicationStatusUpdate = {
      status: newStatus as ApplicationStatusUpdate["status"],
      admin_notes: adminNotes.trim() || null,
    };
    try {
      const updated = await updateApplicationStatus(modal.app.id, body);
      setApplications((prev) =>
        prev.map((a) =>
          a.id === modal.app.id
            ? { ...a, status: updated.status, admin_notes: updated.admin_notes }
            : a,
        ),
      );
      closeModal();
    } catch {
      setSaveError(t("admin.applications.errors.updateFailed"));
    } finally {
      setSaving(false);
    }
  }

  const filterTabs: FilterValue[] = [
    ALL_FILTER,
    ApplicationStatus.NEW,
    ApplicationStatus.APPROVED_BY_ADMIN,
    ApplicationStatus.REJECTED,
    ApplicationStatus.HIRED,
  ];

  return (
    <div>
      <PageHeader
        eyebrow={t("admin.applications.title")}
        subtitle={t("admin.applications.subtitle")}
      />

      {error && (
        <div className="mb-4 rounded-lg border border-danger/20 bg-danger/10 p-4 text-sm text-danger">{error}</div>
      )}

      <div className="mb-5 flex flex-wrap gap-2">
        {filterTabs.map((tab) => {
          const count =
            tab === ALL_FILTER
              ? applications.length
              : applications.filter((a) => a.status === tab).length;
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
              {tab === ALL_FILTER ? t("admin.applications.filterAll") : STATUS_LABELS[tab]} ({count})
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="flex justify-center py-16 text-white/25">{t("admin.applications.loading")}</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-white/10 py-20 text-center text-sm text-white/25">
          {t("admin.applications.empty")}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-white/8 bg-card">
          <table className="min-w-full divide-y divide-white/6 text-sm">
            <thead className="bg-well text-xs font-medium uppercase tracking-wide text-white/35">
              <tr>
                <th className="px-4 py-3 text-start">{t("admin.applications.table.candidate")}</th>
                <th className="px-4 py-3 text-start">{t("admin.applications.table.job")}</th>
                <th className="px-4 py-3 text-start">{t("admin.applications.table.status")}</th>
                <th className="px-4 py-3 text-start">{t("admin.applications.table.date")}</th>
                <th className="px-4 py-3 text-start">{t("admin.applications.table.action")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/6">
              {filtered.map((app) => {
                const canUpdate = (NEXT_STATUSES[app.status] ?? []).length > 0;
                return (
                  <tr key={app.id} className="transition hover:bg-white/3">
                    <td className="px-4 py-3">
                      <p className="font-medium text-white/80">{app.candidate.full_name}</p>
                      <p className="text-xs text-white/40">{app.candidate.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-white/80">{app.job.title}</p>
                      <p className="text-xs text-white/40">{app.job.location}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_COLORS[app.status]}`}>
                        {STATUS_LABELS[app.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-white/40">{formatDate(app.created_at)}</td>
                    <td className="px-4 py-3">
                      {canUpdate ? (
                        <button
                          onClick={() => openModal(app)}
                          className="rounded-sm border border-white/15 px-3 py-1 text-xs text-white/50 transition hover:border-copper/30 hover:text-copper"
                        >
                          {t("common.edit")}
                        </button>
                      ) : (
                        <span className="text-xs text-white/20">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="w-full max-w-md rounded-xl border border-white/10 bg-card-raised p-6">
            <h2 className="text-base font-semibold text-white/85">{t("admin.applications.modal.title")}</h2>
            <div className="mt-3 space-y-0.5 text-sm text-white/50">
              <p>
                <span className="text-white/65">{t("admin.applications.modal.candidateLabel")}:</span>{" "}
                {modal.app.candidate.full_name}
              </p>
              <p>
                <span className="text-white/65">{t("admin.applications.modal.jobLabel")}:</span>{" "}
                {modal.app.job.title}
              </p>
              <p>
                <span className="text-white/65">{t("admin.applications.modal.currentStatusLabel")}:</span>{" "}
                <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[modal.app.status]}`}>
                  {STATUS_LABELS[modal.app.status]}
                </span>
              </p>
            </div>

            <div className="mt-5 space-y-3">
              <div>
                <label className="block text-sm text-white/50">
                  {t("admin.applications.modal.newStatusLabel")}
                </label>
                <select
                  value={newStatus}
                  onChange={(e) => setNewStatus(e.target.value)}
                  className={`mt-1 ${selectCls}`}
                >
                  {(NEXT_STATUSES[modal.app.status] ?? []).map((s) => (
                    <option key={s} value={s} className="bg-well">
                      {STATUS_LABELS[s]}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm text-white/50">
                  {t("admin.applications.modal.adminNotes")}{" "}
                  <span className="text-white/25">({t("common.optional")})</span>
                </label>
                <textarea
                  value={adminNotes}
                  onChange={(e) => setAdminNotes(e.target.value)}
                  rows={3}
                  className={`mt-1 ${textareaCls}`}
                  placeholder={t("admin.applications.modal.notesPlaceholder")}
                />
              </div>
            </div>

            {saveError && <p className="mt-3 text-sm text-danger">{saveError}</p>}

            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={closeModal}
                disabled={saving}
                className="rounded-sm px-4 py-2 text-sm text-white/40 transition hover:bg-white/5 hover:text-white/70 disabled:opacity-40"
              >
                {t("admin.applications.modal.cancel")}
              </button>
              <button
                onClick={handleSaveStatus}
                disabled={saving || !newStatus}
                className="rounded-sm bg-copper px-4 py-2 text-sm font-medium text-white transition hover:bg-gold disabled:opacity-40"
              >
                {saving ? t("admin.applications.modal.saving") : t("admin.applications.modal.save")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
