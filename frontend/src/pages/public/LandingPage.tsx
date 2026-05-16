import { type CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "@/hooks/useAuth";
import { getPublicJobs } from "@/services/jobs";
import type { JobPublicRead } from "@/types/api";
import LogoBanner from "@/components/ui/LogoBanner";
import SeoHead, { SITE_URL } from "@/components/ui/SeoHead";
import FeaturedRibbon from "@/components/ui/FeaturedRibbon";

function useReveal(threshold = 0.05) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || !("IntersectionObserver" in window)) { setVisible(true); return; }
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setVisible(true); obs.disconnect(); } },
      { threshold, rootMargin: "0px 0px -60px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, visible] as const;
}

// ── Animation helpers (power3.out = cubic-bezier(0.215, 0.61, 0.355, 1)) ──

/** Card / panel rise — lighter than section */
function cardRise(visible: boolean, delay = "0s"): CSSProperties {
  return visible
    ? { animation: `card-reveal 0.75s cubic-bezier(0.215, 0.61, 0.355, 1) ${delay} both` }
    : { opacity: 0, transform: "translateY(36px)" };
}

/** Clip-based text reveal. Parent MUST have overflow-hidden.
 *  Text slides from below the clipping edge — never visible until it arrives.   */
function clipRise(visible: boolean, delay = "0s"): CSSProperties {
  return visible
    ? { animation: `text-clip-rise 0.8s cubic-bezier(0.215, 0.61, 0.355, 1) ${delay} both` }
    : { transform: "translateY(105%)" };
}


function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("he-IL", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const SEARCH_TAGS = ["תפקיד", "מיקום"] as const;
const LONG_PRESS_MS = 140;

// Combined Organization + WebSite schema via @graph. WebSite gives Google a
// canonical brand entity for the domain (helps consolidate the homepage and
// /jobs into a single SERP result with sitelinks instead of two separate
// entries). EmploymentAgency is a more specific Organization subtype that
// matches the niche.
const SITE_SCHEMA = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": ["Organization", "EmploymentAgency"],
      "@id": `${SITE_URL}/#organization`,
      name: "RS Recruiting",
      url: SITE_URL,
      logo: `${SITE_URL}/logo.svg`,
      description:
        "משרד גיוס והשמה בוטיקי המתמחה בגיוס לתפקידי ניהול ותפעול מבנים ונכסים בישראל",
      areaServed: "IL",
      knowsAbout: [
        "ניהול מבנים",
        "תפעול מבנים",
        "ניהול נכסים",
        "גיוס עובדים",
        "השמה",
      ],
      contactPoint: {
        "@type": "ContactPoint",
        email: "support@rs-recruiting.com",
        contactType: "כוח אדם וגיוס",
        areaServed: "IL",
        availableLanguage: "Hebrew",
      },
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "RS Recruiting",
      inLanguage: "he-IL",
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
  ],
};

export default function LandingPage() {
  const { t } = useTranslation();
  useAuth(); // keeps auth context initialised for child components
  const navigate = useNavigate();

  const [statsRef, statsVisible] = useReveal(0.3);
  const [audienceRef, audienceVisible] = useReveal(0.2);
  const [aboutTextRef, aboutTextVisible] = useReveal(0.2);
  const [jobsRef, jobsVisible] = useReveal(0.15);
  const [jobs, setJobs] = useState<JobPublicRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [heroLoaded, setHeroLoaded] = useState(false);
  const [aboutImgLoaded, setAboutImgLoaded] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [cardsVisible, setCardsVisible] = useState<boolean>(
    () => typeof window === "undefined" || !("IntersectionObserver" in window),
  );

  const cardsRef    = useRef<HTMLDivElement>(null);
  const scrollRef   = useRef<HTMLDivElement>(null);
  // Carousel drag state (all in refs to avoid re-renders)
  const isDragging  = useRef(false);
  const hasDragged  = useRef(false);
  const velocityRef = useRef(0);
  const longTimer   = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const rafId       = useRef(0);

  // Only featured jobs appear in the landing "משרות נבחרות" carousel.
  const featuredJobs = useMemo(() => jobs.filter((j) => j.is_featured), [jobs]);

  // Triple the array for the infinite loop
  const loopedJobs = useMemo(
    () =>
      featuredJobs.length > 0
        ? [...featuredJobs, ...featuredJobs, ...featuredJobs]
        : [],
    [featuredJobs],
  );

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    navigate(`/jobs${searchQuery.trim() ? `?q=${encodeURIComponent(searchQuery.trim())}` : ""}`);
  }

  // ── Initial scroll: park at the START of the middle set ──────────────
  useEffect(() => {
    if (loading || !featuredJobs.length) return;
    const el = scrollRef.current;
    if (!el) return;
    // rAF ensures layout (card widths) is settled
    const id = requestAnimationFrame(() => {
      el.scrollLeft = el.scrollWidth / 3;
    });
    return () => cancelAnimationFrame(id);
  }, [loading, featuredJobs.length]);

  // ── Infinite-loop carousel: drag + momentum + long-press ─────────────
  useEffect(() => {
    if (loading || !featuredJobs.length) return;
    const el = scrollRef.current;
    if (!el) return;

    let isMouseDown = false; // gate: only drag when button is actually held
    let startX      = 0;
    let startScroll = 0;
    let lastX       = 0;
    let lastT       = 0;
    let teleporting = false; // guard against re-entrant scroll events

    // Arrow expressions (not function declarations) so the `el` non-null
    // narrowing from the guard above propagates into these closures under
    // tsc -b strict mode.
    const enterDrag = (clientX: number) => {
      isDragging.current = true;
      hasDragged.current = true;
      startX      = clientX;
      startScroll = el.scrollLeft;
      lastX       = clientX;
      lastT       = performance.now();
      velocityRef.current = 0;
      cancelAnimationFrame(rafId.current);
      el.style.cursor     = "grabbing";
      el.style.userSelect = "none";
    };

    const onMouseDown = (e: MouseEvent) => {
      isMouseDown = true;
      hasDragged.current = false;
      startX      = e.clientX;
      startScroll = el.scrollLeft;

      // Long-press: enter drag even without significant movement
      longTimer.current = setTimeout(() => enterDrag(e.clientX), LONG_PRESS_MS);
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isDragging.current) {
        // Only consider dragging when the mouse button is held down
        if (isMouseDown && Math.abs(e.clientX - startX) > 5) {
          clearTimeout(longTimer.current);
          enterDrag(e.clientX);
        }
        return;
      }
      e.preventDefault();

      const now = performance.now();
      const dt  = now - lastT;
      if (dt > 0) velocityRef.current = (lastX - e.clientX) / dt; // px/ms
      lastX = e.clientX;
      lastT = now;

      el.scrollLeft = startScroll + (startX - e.clientX);
    };

    const onMouseUp = () => {
      isMouseDown = false;
      clearTimeout(longTimer.current);
      if (!isDragging.current) return;

      isDragging.current  = false;
      el.style.cursor     = "grab";
      el.style.userSelect = "";

      // Momentum: carry the last velocity and decelerate
      let v = velocityRef.current * 16; // convert px/ms → px/frame @60fps
      const step = () => {
        if (Math.abs(v) < 0.5) {
          hasDragged.current = false;
          return;
        }
        el.scrollLeft += v;
        v *= 0.90;
        rafId.current = requestAnimationFrame(step);
      };
      rafId.current = requestAnimationFrame(step);
    };

    const onScroll = () => {
      if (teleporting) return;
      const total     = el.scrollWidth;
      const oneSet    = total / 3;

      // Silent teleport to keep the user in the middle set
      if (el.scrollLeft < oneSet * 0.5) {
        teleporting = true;
        el.scrollLeft += oneSet;
        teleporting = false;
      } else if (el.scrollLeft > oneSet * 2 - el.clientWidth * 0.5) {
        teleporting = true;
        el.scrollLeft -= oneSet;
        teleporting = false;
      }

      // Progress bar: position within one set, 0–100 %
      const pos   = ((el.scrollLeft - oneSet) % oneSet + oneSet) % oneSet;
      const range = oneSet - el.clientWidth;
      setScrollProgress(range > 0 ? Math.min(100, Math.max(0, (pos / range) * 100)) : 0);
    };

    el.style.cursor = "grab";
    el.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mouseup", onMouseUp);
    el.addEventListener("mousemove", onMouseMove);
    el.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      clearTimeout(longTimer.current);
      cancelAnimationFrame(rafId.current);
      el.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mouseup", onMouseUp);
      el.removeEventListener("mousemove", onMouseMove);
      el.removeEventListener("scroll", onScroll);
    };
  }, [loading, featuredJobs.length]);

  // ── Feature-card entrance animations ─────────────────────────────────
  useEffect(() => {
    const el = cardsRef.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) { setCardsVisible(true); obs.disconnect(); } },
      { threshold: 0.15 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    getPublicJobs()
      .then((page) => { if (!cancelled) setJobs(page.items.slice(0, 10)); })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="bg-page">
      <SeoHead
        title={t("landing.seo.title")}
        description={t("landing.seo.description")}
        canonical={SITE_URL}
        structuredData={SITE_SCHEMA}
      />

      {/* ── Hero + audience panels share one image so they fade into each
            other without a visible seam where the sections meet. ─────────── */}
      <div className="relative overflow-hidden bg-void">
        <img
          src="/hero-city.jpg"
          alt=""
          aria-hidden="true"
          onLoad={() => setHeroLoaded(true)}
          className="pointer-events-none absolute inset-0 h-full w-full object-cover transition-opacity duration-[900ms] ease-out"
          style={{
            objectPosition: "center 60%",
            opacity: heroLoaded ? 1 : 0,
          }}
        />

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="texture-wave relative flex min-h-screen flex-col">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-void/80 via-page/60 to-void/55" />

        {/* Centered content */}
        <div className="relative z-10 mx-auto flex w-full max-w-3xl flex-1 flex-col items-center justify-center px-6 pb-16 text-center sm:pb-24">
          <LogoBanner />
          <h1 className="sr-only">{t("landing.seo.h1")}</h1>

          <div
            className="mx-auto mt-7 h-px w-32 sm:mt-8 sm:w-48"
            style={{
              background:
                "linear-gradient(to right, transparent, var(--color-copper), var(--color-gold), var(--color-copper), transparent)",
            }}
          />

          <p className="mt-5 text-base font-light tracking-wide text-white/72 sm:mt-6 sm:text-lg">
            {t("landing.hero.tagline")}
          </p>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="mt-9 w-full sm:mt-11">
            <div className="flex items-center overflow-hidden rounded-full border border-white/20 bg-black/45 shadow-xl backdrop-blur-md transition-colors focus-within:border-copper/50">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("landing.hero.searchPlaceholder")}
                className="min-w-0 flex-1 bg-transparent py-4 pe-4 ps-6 text-base text-white/90 placeholder:text-white/35 focus:outline-none sm:text-lg"
              />
              <button
                type="submit"
                aria-label={t("common.search")}
                className="m-1.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-copper text-white transition hover:bg-gold"
              >
                <svg
                  width="16" height="16" viewBox="0 0 24 24"
                  fill="none" stroke="currentColor" strokeWidth="2.5"
                  strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              </button>
            </div>

            <div className="mt-3.5 flex items-center justify-center gap-2 text-xs text-white/25">
              <span>חפש לפי:</span>
              {SEARCH_TAGS.map((tag) => (
                <span key={tag} className="rounded-full border border-white/10 px-2.5 py-0.5">
                  {tag}
                </span>
              ))}
            </div>
          </form>
        </div>
      </section>

      {/* ── Audience panels — image is shared with hero (above); just paint
            the gradient overlay that fades into the next dark section. ─── */}
      <section className="relative py-10 sm:py-14">
        {/* Front-loaded fade: void/55 → nearly dark by 35% → locked card-raised after that */}
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background: `linear-gradient(to bottom,
              color-mix(in srgb, var(--color-void) 55%, transparent) 0%,
              color-mix(in srgb, var(--color-void) 75%, transparent) 15%,
              color-mix(in srgb, var(--color-void) 92%, transparent) 28%,
              var(--color-card-raised) 38%
            )`,
          }}
        />

        <div className="relative z-10 mx-auto max-w-4xl px-6">
          <div className="grid gap-4 sm:grid-cols-[3fr_2fr] sm:gap-5" ref={audienceRef}>

            {/* Primary: job seekers — card rises first */}
            <div
              className="flex flex-col rounded-xl border border-copper/25 bg-card-raised p-6 text-start sm:p-8"
              style={cardRise(audienceVisible, "0s")}
            >
              <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70">
                {t("landing.hero.forSeekers")}
              </p>
              {/* Heading clip-reveal inside the already-risen card */}
              <div className="mt-2 overflow-hidden">
                <h2
                  className="text-xl font-semibold leading-tight text-white/95 sm:text-2xl"
                  style={clipRise(audienceVisible, "0.1s")}
                >
                  {t("landing.hero.seekersHeadline")}
                </h2>
              </div>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-white/60">
                {t("landing.hero.seekersBody")}
              </p>
              <Link
                to="/jobs"
                className="mt-6 inline-block rounded-sm bg-copper px-5 py-2.5 text-center text-sm font-medium text-white transition hover:bg-gold"
              >
                {t("landing.hero.seekersCta")}
              </Link>
            </div>

            {/* Secondary: companies — staggered 0.15s behind */}
            <div
              className="flex flex-col rounded-xl border border-white/8 bg-card p-6 text-start"
              style={cardRise(audienceVisible, "0.15s")}
            >
              <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/60">
                {t("landing.hero.forCompanies")}
              </p>
              <div className="mt-2 overflow-hidden">
                <h2
                  className="text-lg font-semibold leading-tight text-white/90"
                  style={clipRise(audienceVisible, "0.25s")}
                >
                  {t("landing.hero.companiesHeadline")}
                </h2>
              </div>
              <p className="mt-3 flex-1 text-sm leading-relaxed text-white/55">
                {t("landing.hero.companiesBody")}
              </p>
              <p className="mt-3 text-xs text-white/30">
                {t("landing.hero.companiesInviteOnly")}
              </p>
              <a
                href={`mailto:${t("landing.contact.email")}`}
                className="mt-5 inline-block rounded-sm border border-copper/35 px-4 py-2 text-center text-sm text-copper/70 transition hover:border-copper/60 hover:text-copper"
              >
                {t("landing.hero.companiesContactCta")}
              </a>
            </div>
          </div>
        </div>
      </section>
      </div>

      {/* ── Sectors — 3 specializations, clip reveal staggered 0.12s ────── */}
      <div className="border-y border-white/6 bg-void py-10 sm:py-12">
        <div className="mx-auto max-w-4xl px-6">
          <div className="overflow-hidden">
            <p
              className="mb-6 text-center text-[10px] font-semibold uppercase tracking-widest text-copper/55"
              style={clipRise(statsVisible, "0s")}
            >
              {t("landing.sectors.eyebrow")}
            </p>
          </div>
          <div ref={statsRef} className="grid grid-cols-3">
            {(
              [
                { titleKey: "landing.sectors.s1Title", subKey: "landing.sectors.s1Sub", i: 0 },
                { titleKey: "landing.sectors.s2Title", subKey: "landing.sectors.s2Sub", i: 1 },
                { titleKey: "landing.sectors.s3Title", subKey: "landing.sectors.s3Sub", i: 2 },
              ] as const
            ).map(({ titleKey, subKey, i }) => (
              <div
                key={titleKey}
                className="border-s border-white/8 px-4 text-center first:border-s-0 first:ps-0 last:pe-0 sm:px-6"
              >
                <div className="overflow-hidden">
                  <p
                    className="text-sm font-semibold text-white/80 sm:text-base"
                    style={clipRise(statsVisible, `${i * 0.12}s`)}
                  >
                    {t(titleKey)}
                  </p>
                </div>
                <div className="overflow-hidden">
                  <p
                    className="mt-1.5 text-[11px] leading-snug text-white/30 sm:text-xs"
                    style={clipRise(statsVisible, `${i * 0.12 + 0.08}s`)}
                  >
                    {t(subKey)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>


      {/* ── About — Western Rise split layout ─────────────────────────── */}
      <section className="texture-wave bg-card-raised py-20 sm:py-32">
        <div className="mx-auto max-w-4xl px-6">

          {/*
            Split layout: text on the visual right (reading start in RTL),
            photo on the visual left.
            RTL grid: first DOM child → rightmost visually.
          */}
          <div ref={aboutTextRef} className="grid items-center gap-10 sm:grid-cols-2 sm:gap-14">
            {/* Text column — clip-rise on headline, card-rise on body */}
            <div>
              <div className="h-px w-8 bg-copper/40" style={aboutTextVisible ? { animation: "line-expand-h 0.6s cubic-bezier(0.215,0.61,0.355,1) both", transformOrigin: "right" } : { transform: "scaleX(0)" }} />
              <div className="overflow-hidden">
                <p className="mt-3 text-xs font-semibold uppercase tracking-widest text-copper" style={clipRise(aboutTextVisible, "0.05s")}>
                  {t("landing.about.eyebrow")}
                </p>
              </div>
              <div className="mt-5 overflow-hidden">
                <h2 className="text-xl font-semibold leading-snug text-white/90 sm:text-2xl" style={clipRise(aboutTextVisible, "0.15s")}>
                  {t("landing.about.headline")}
                </h2>
              </div>
              <p className="mt-5 text-base leading-relaxed text-white/60" style={cardRise(aboutTextVisible, "0.28s")}>
                <span className="font-wordmark text-3xl font-light tracking-widest text-gold/60 sm:text-4xl">RS Recruiting</span>{" "}
                {t("landing.about.body")}
              </p>
              <p className="mt-4 text-sm leading-relaxed text-white/50" style={cardRise(aboutTextVisible, "0.38s")}>
                {t("landing.about.body2")}
              </p>
              <p className="mt-8 text-xs uppercase tracking-widest text-white/25" style={cardRise(aboutTextVisible, "0.48s")}>
                {t("landing.about.pillars")}
              </p>
            </div>

            {/* Photo — clip-path wipe reveal (no overlay, no corner bleeding).
                Clip starts at inset(0 0 0 100%) — fully hidden from right edge.
                Animates to inset(0 0 0 0%) — fully revealed, right to left.    */}
            <div className="overflow-hidden rounded-xl">
              <img
                src="/landing-about.jpg"
                alt=""
                aria-hidden="true"
                onLoad={() => setAboutImgLoaded(true)}
                className="aspect-[4/5] w-full object-cover object-center"
                style={
                  aboutTextVisible && aboutImgLoaded
                    ? { animation: "clip-wipe-reveal 1.1s cubic-bezier(0.76, 0, 0.24, 1) 0.08s both" }
                    : { clipPath: "inset(0 0 0 100% round 0.75rem)" }
                }
              />
            </div>
          </div>

          {/* Feature cards — below the split, full width */}
          <div
            ref={cardsRef}
            className="mt-12 -mx-6 flex gap-4 overflow-x-auto px-6 pb-4 sm:mx-0 sm:mt-16 sm:grid sm:grid-cols-3 sm:gap-5 sm:overflow-visible sm:px-0 sm:pb-0"
          >
            {(
              [
                { titleKey: "landing.about.feature1Title", bodyKey: "landing.about.feature1Body", num: "01" },
                { titleKey: "landing.about.feature2Title", bodyKey: "landing.about.feature2Body", num: "02" },
                { titleKey: "landing.about.feature3Title", bodyKey: "landing.about.feature3Body", num: "03" },
              ] as const
            ).map((f, idx) => (
              <div
                key={f.titleKey}
                className="w-[78vw] shrink-0 snap-start sm:w-auto"
                style={{
                  animation: cardsVisible
                    ? `${["card-tilt-in", "card-rise-in", "card-swing-in"][idx]} 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) ${idx * 160}ms both`
                    : "none",
                  opacity: cardsVisible ? undefined : 0,
                }}
              >
                <div className="feature-card feature-card-shimmer h-full rounded-lg border border-white/10 bg-card-raised p-6">
                  <p className="select-none text-4xl font-semibold leading-none text-copper/25">{f.num}</p>
                  <div
                    className="mt-4 h-px bg-copper/60 transition-all duration-500"
                    style={{
                      width: cardsVisible ? "1.5rem" : "0",
                      transitionDelay: cardsVisible ? `${idx * 160 + 380}ms` : "0ms",
                    }}
                  />
                  <p className="mt-3 font-semibold text-white/90">{t(f.titleKey)}</p>
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{t(f.bodyKey)}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Featured Jobs — infinite free-scroll carousel ─────────────── */}
      {!loading && featuredJobs.length > 0 && (
        <section className="bg-void py-20 sm:py-32">
          <div className="mx-auto max-w-4xl px-6">
            <div ref={jobsRef}>
            {/* Heading — clip-rise; link card-rises alongside */}
            <div className="flex items-end justify-between">
              <div>
                <div className="overflow-hidden">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-copper/70" style={clipRise(jobsVisible, "0s")}>
                    RS Recruiting
                  </p>
                </div>
                <div className="mt-2 overflow-hidden">
                  <h2 className="text-2xl font-semibold text-white/92 sm:text-3xl" style={clipRise(jobsVisible, "0.1s")}>
                    {t("landing.featuredJobs.title")}
                  </h2>
                </div>
              </div>
              <Link
                to="/jobs"
                className="mb-1 shrink-0 text-sm text-copper/70 transition hover:text-copper"
                style={cardRise(jobsVisible, "0.15s")}
              >
                {t("landing.featuredJobs.viewAll")} ←
              </Link>
            </div>

            {/*
              dir="ltr" forces a predictable scrollLeft (0 = left edge, positive = scrolled right).
              Each card gets dir="rtl" so Hebrew text renders correctly.
              onClickCapture prevents Link navigation when the user was dragging.
            */}
            <div
              ref={scrollRef}
              dir="ltr"
              className="scrollbar-none mt-8 flex gap-4 overflow-x-scroll pb-2"
              style={{
                ...cardRise(jobsVisible, "0.22s"),
                WebkitOverflowScrolling: "touch" as React.CSSProperties["WebkitOverflowScrolling"],
              }}
              onClickCapture={(e) => {
                if (hasDragged.current) {
                  e.preventDefault();
                  e.stopPropagation();
                }
              }}
            >
              {loopedJobs.map((job, i) => (
                <Link
                  key={`${job.id}-${i}`}
                  to={`/jobs/${job.id}`}
                  dir="rtl"
                  draggable={false}
                  className="group relative flex min-h-[210px] w-[75vw] shrink-0 flex-col rounded-xl border border-gold/40 bg-card p-5 transition-colors hover:border-gold/60 sm:w-72"
                >
                  <FeaturedRibbon label={t("publicJobs.board.featured")} />
                  <h3 className="font-medium text-white/90">{job.title}</h3>
                  <p className="mt-1 text-sm text-white/40">{job.location}</p>
                  <p className="mt-3 line-clamp-3 text-sm leading-relaxed text-white/60">
                    {job.short_description}
                  </p>
                  {job.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {job.tags.slice(0, 3).map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-copper/25 bg-copper/10 px-2 py-0.5 text-[11px] font-medium text-copper/90"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                  <p className="mt-auto pt-4 text-xs text-white/30">
                    {t("common.posted")} {formatDate(job.created_at)}
                  </p>
                </Link>
              ))}
            </div>

            {/* Progress bar */}
            <div className="mt-5 h-px overflow-hidden rounded-full bg-white/8">
              <div
                className="h-full rounded-full bg-copper/50 transition-all duration-100"
                style={{ width: `${scrollProgress}%` }}
              />
            </div>
            </div>
          </div>
        </section>
      )}

    </div>
  );
}
