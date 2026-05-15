import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import { PublicHeader, PublicFooter } from "@/components/layout/AppShell";

const EMAIL = "support@rs-recruiting.com";

function useReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { setVisible(true); return; }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, visible] as const;
}

function rise(visible: boolean, delay = "0s", duration = "0.85s"): CSSProperties {
  return visible
    ? { animation: `text-rise ${duration} cubic-bezier(0.16, 1, 0.3, 1) ${delay} both` }
    : { transform: "translateY(110%)" };
}

function revealUp(visible: boolean, delay = "0s"): CSSProperties {
  return visible
    ? { animation: `reveal-up 0.8s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both` }
    : { opacity: 0 };
}

function ruleDraw(visible: boolean, delay = "0s"): CSSProperties {
  return visible
    ? { animation: `line-expand-h 0.75s cubic-bezier(0.22, 1, 0.36, 1) ${delay} both`, transformOrigin: "right" }
    : { transform: "scaleX(0)" };
}

export default function ContactPage() {
  const { t } = useTranslation();
  const [cardsRef, cardsVisible] = useReveal(0.15);

  return (
    <div className="flex min-h-screen flex-col bg-void page-enter">
      <SeoHead
        title={t("contact.seo.title")}
        description={t("contact.seo.description")}
        canonical={`${SITE_URL}/contact`}
      />

      <PublicHeader />

      {/* ── Hero ─────────────────────────────────────────────────────────── */}
      <section className="texture-wave relative flex flex-1 flex-col items-center justify-center overflow-hidden px-6 py-32 text-center">
        {/* Copper radial glow */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(ellipse 70% 60% at 50% 50%, color-mix(in srgb, var(--color-copper) 9%, transparent), transparent)",
          }}
        />

        <div className="relative mx-auto max-w-xl">
          {/* Eyebrow rule + label */}
          <div className="flex flex-col items-center gap-2">
            <div className="h-px w-10 bg-copper/50" style={ruleDraw(true, "0.2s")} />
            <div className="overflow-hidden">
              <p
                className="text-xs font-semibold uppercase tracking-widest text-copper/75"
                style={rise(true, "0.4s", "0.6s")}
              >
                {t("contact.eyebrow")}
              </p>
            </div>
          </div>

          {/* Headline */}
          <div className="mt-8 overflow-hidden">
            <h1
              className="font-wordmark text-[clamp(2.8rem,8vw,5.5rem)] font-light leading-tight text-white/88"
              style={rise(true, "0.55s", "0.9s")}
            >
              {t("contact.headline")}
            </h1>
          </div>

          {/* Subtitle */}
          <p
            className="mx-auto mt-6 max-w-sm text-base leading-relaxed text-white/40"
            style={revealUp(true, "0.9s")}
          >
            {t("contact.subtitle")}
          </p>

          {/* Primary CTA — large email link */}
          <div className="mt-12 overflow-hidden">
            <a
              href={`mailto:${EMAIL}`}
              className="font-wordmark text-[clamp(1.1rem,3vw,1.6rem)] font-light tracking-wide text-copper/80 transition-colors duration-300 hover:text-gold"
              style={rise(true, "1.05s")}
            >
              {EMAIL}
            </a>
          </div>

          {/* Thin copper line */}
          <div
            className="mx-auto mt-8 h-px w-16 bg-copper/30"
            style={{
              animation: "line-expand-h 1s cubic-bezier(0.22, 1, 0.36, 1) 1.2s both",
              transformOrigin: "center",
            }}
          />
        </div>
      </section>

      {/* ── Info cards ───────────────────────────────────────────────────── */}
      <div ref={cardsRef} className="bg-page px-6 py-16">
        <div className="mx-auto grid max-w-2xl gap-4 sm:grid-cols-2">
          {/* Email card */}
          <div
            className="group rounded-xl border border-white/8 bg-card p-7 transition-colors duration-300 hover:border-copper/25 hover:bg-card-raised"
            style={revealUp(cardsVisible, "0.1s")}
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70">
              {t("contact.emailLabel")}
            </p>
            <div className="mt-3 h-px w-6 bg-copper/30" style={ruleDraw(cardsVisible, "0.2s")} />
            <a
              href={`mailto:${EMAIL}`}
              className="mt-4 block text-sm font-medium text-white/70 transition-colors duration-200 group-hover:text-copper"
            >
              {EMAIL}
            </a>
          </div>

          {/* Address card */}
          <div
            className="rounded-xl border border-white/8 bg-card p-7 transition-colors duration-300 hover:border-white/15 hover:bg-card-raised"
            style={revealUp(cardsVisible, "0.25s")}
          >
            <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70">
              {t("contact.addressLabel")}
            </p>
            <div className="mt-3 h-px w-6 bg-copper/30" style={ruleDraw(cardsVisible, "0.35s")} />
            <p className="mt-4 text-sm text-white/70">{t("contact.address")}</p>
          </div>
        </div>

        {/* Back to jobs nudge */}
        <p className="mt-10 text-center text-sm text-white/25" style={revealUp(cardsVisible, "0.4s")}>
          <Link to="/jobs" className="text-white/40 underline-offset-4 transition hover:text-white/70 hover:underline">
            {t("nav.jobs")}
          </Link>
          {" "}·{" "}
          <Link to="/about" className="text-white/40 underline-offset-4 transition hover:text-white/70 hover:underline">
            {t("nav.about")}
          </Link>
        </p>
      </div>

      <PublicFooter />
    </div>
  );
}
