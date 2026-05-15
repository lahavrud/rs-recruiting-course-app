import { useTranslation } from "react-i18next";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";

const EMAIL = "support@rs-recruiting.com";

export default function ContactPage() {
  const { t } = useTranslation();

  return (
    <>
      <SeoHead
        title={t("contact.seo.title")}
        description={t("contact.seo.description")}
        canonical={`${SITE_URL}/contact`}
      />

      <p className="text-xs font-semibold uppercase tracking-widest text-copper">
        {t("contact.eyebrow")}
      </p>
      <div className="mt-3 h-px w-8 bg-copper/40" />
      <p className="mt-5 text-2xl font-semibold leading-snug text-white/90 sm:text-3xl">
        {t("contact.headline")}
      </p>
      <p className="mt-4 text-base leading-relaxed text-white/55">
        {t("contact.subtitle")}
      </p>

      <div className="mt-10 grid gap-5 sm:grid-cols-2">
        <div className="rounded-xl border border-white/8 bg-card p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-copper">
            {t("contact.emailLabel")}
          </p>
          <a
            href={`mailto:${EMAIL}`}
            className="mt-3 block text-base font-medium text-white/80 transition hover:text-copper"
          >
            {EMAIL}
          </a>
        </div>

        <div className="rounded-xl border border-white/8 bg-card p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-copper">
            {t("contact.addressLabel")}
          </p>
          <p className="mt-3 text-base text-white/80">{t("contact.address")}</p>
        </div>
      </div>
    </>
  );
}
