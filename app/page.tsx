"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Expand,
  FileText,
  FlaskConical,
  Layers3,
  Microscope,
  MoveUpRight,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { HomeComposer } from "@/components/home-composer";
import Link from "next/link";
import { useRouter } from "next/navigation";

const research = [
  {
    image: "/assets/images/coupon-01.jpg",
    label: "01 / COUPON STUDY",
    title: "A closer look at the material.",
    text: "Coupon imagery makes the material visible: surface condition, preparation, and the details behind every test record.",
    name: "CSAI-01 · Source coupon image",
    type: "Specimen imagery",
  },
  {
    image: "/assets/images/coupon-04.jpg",
    label: "02 / SPECIMEN SERIES",
    title: "One specimen. More context.",
    text: "A second view from the supplied specimen series. Connecting images with panel IDs and test conditions is part of the data foundation we’re building.",
    name: "CSAI-04 · Source coupon image",
    type: "Specimen imagery",
  },
  {
    image: "/assets/images/microscopy.jpg",
    label: "03 / MICROSCOPY",
    title: "The evidence is in the details.",
    text: "Microscopy reveals the local features that aggregate numbers can miss. These observations will sit alongside measured results and engineering review.",
    name: "NV-01 · Sharp ×100",
    type: "Microscopy",
  },
];
const gallery = [
  {
    image: "/assets/figures/vacuum-jig.svg",
    title: "Vacuum jig setup",
    subtitle: "Experimental setup / source diagram",
  },
  {
    image: "/assets/figures/surface-evaluation.svg",
    title: "Twist drill surface evaluation",
    subtitle: "Surface investigation / source diagram",
  },
  {
    image: "/assets/figures/python-plots.svg",
    title: "Research visualization study",
    subtitle: "Data visualization / source diagram",
  },
];
const steps = [
  {
    icon: Layers3,
    title: "Define the coupon",
    text: "Geometry, material, loads, and design constraints. A clear engineering question comes first.",
    tag: "SPECIFICATION",
  },
  {
    icon: Sparkles,
    title: "Analyze with physics",
    text: "Search candidate layups, evaluate laminate behavior, and cross-check with finite element analysis.",
    tag: "ANALYSIS WORKFLOW",
  },
  {
    icon: FlaskConical,
    title: "Build. Test. Compare.",
    text: "Fabricate coupons and compare physical measurements against predictions made before the test.",
    tag: "LAB VALIDATION",
  },
  {
    icon: FileText,
    title: "Make it traceable",
    text: "Connect every result to its inputs, analysis record, and source data. Let the evidence guide the next iteration.",
    tag: "DOCUMENTED RESULTS",
  },
];

export default function Home() {
  const router = useRouter();
  const [selected, setSelected] = useState(0);
  const [lightbox, setLightbox] = useState<{
    image: string;
    title: string;
  } | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (lightbox) {
      dialog.current?.showModal();
      const old = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = old;
      };
    } else dialog.current?.close();
  }, [lightbox]);
  function openWorkspace(t: "assistant" | "data" = "assistant") {
    router.push(t === "data" ? "/data" : "/chat");
  }
  const current = research[selected];
  return (
    <>
      <main id="main">
        <section className="hero" id="overview">
          <div className="hero-image" />
          <div className="hero-grid" />
          <div className="hero-content">
            <span className="eyebrow">
              <span className="status-dot" /> ENGINEERING INTELLIGENCE, GROUNDED
              IN EVIDENCE
            </span>
            <h1>
              From material
              <br />
              to <span>understanding.</span>
            </h1>
            <p>
              A clearer path from composite coupon to confident design.
              <br className="desktop-break" /> Connecting physics, physical
              testing, and research—one layer at a time.
            </p>
            <HomeComposer />
            <div className="hero-footnote">
              <span className="hero-line" />
              <span>COUPONS FIRST. EVIDENCE ALWAYS.</span>
            </div>
          </div>
          <div className="hero-annotation">
            <span className="annotation-cross">+</span>
            <span>
              CARBON FIBER
              <br />
              <span className="muted">The material is the starting point.</span>
            </span>
          </div>
          <div className="hero-bottom">
            <span>01 — THE FIRST CHAPTER</span>
            <a href="#workflow">
              SCROLL TO DISCOVER <ArrowDown size={13} />
            </a>
            <span>BUILT TO BE TESTED.</span>
          </div>
        </section>
        <div className="principles-strip">
          <span>
            <span className="status-dot" /> PHYSICS AT THE CORE
          </span>
          <span>LAB DATA AS THE FOUNDATION</span>
          <span>RESEARCH BEFORE ASSUMPTIONS</span>
          <span>
            EVERY RESULT, TRACEABLE <MoveUpRight size={15} />
          </span>
        </div>
        <section className="section workflow-section" id="workflow">
          <div className="section-heading">
            <div>
              <span className="eyebrow">01 / THE IDEA</span>
              <h2>
                Better decisions.
                <br />
                Built layer by layer.
              </h2>
            </div>
            <div className="heading-description">
              <p>
                Composite design is a conversation between what we predict and
                what we can prove.
              </p>
              <p className="muted">
                We’re building a continuous workflow that brings those two
                worlds together—from the first specification to the next
                physical test.
              </p>
            </div>
          </div>
          <div className="workflow-grid">
            {steps.map((s, i) => (
              <article className="workflow-step" key={s.title}>
                <div className="step-top">
                  <s.icon size={25} strokeWidth={1.4} />
                  <span>0{i + 1}</span>
                </div>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
                <span className="step-tag">
                  {s.tag}
                  {i < 3 && <ArrowRight size={15} />}
                </span>
              </article>
            ))}
          </div>
          <div className="core-rule">
            <ShieldCheck size={20} />
            <p>
              <strong>Physics produces the numbers.</strong> Every conclusion
              should connect to its material basis, method, and supporting
              evidence.
            </p>
            <span>OUR CORE PRINCIPLE</span>
          </div>
        </section>
        <section className="lab-section" id="lab">
          <div className="section lab-inner">
            <div className="section-heading">
              <div>
                <span className="eyebrow">02 / FROM THE LAB</span>
                <h2>
                  Real materials.
                  <br />
                  Real questions.
                </h2>
              </div>
              <p>
                The work starts at the specimen.
                <br />A look at the research behind the vision.
              </p>
            </div>
            <div className="research-feature">
              <button
                className="research-image"
                onClick={() =>
                  setLightbox({ image: current.image, title: current.name })
                }
                aria-label={`Enlarge ${current.name}`}
              >
                <img src={current.image} alt={current.name} loading="lazy" />
                <span className="image-index">
                  SOURCE IMAGE / {String(selected + 1).padStart(2, "0")}
                </span>
                <span className="expand-icon">
                  <Expand size={18} />
                </span>
                <span className="image-caption">{current.name}</span>
              </button>
              <div className="research-copy">
                <span className="tiny-label">{current.label}</span>
                <h3>{current.title}</h3>
                <p>{current.text}</p>
                <div className="research-meta">
                  <span>RESEARCH ASSET</span>
                  <span>{current.type}</span>
                </div>
                <div className="research-controls">
                  <div className="slide-dots">
                    {research.map((r, i) => (
                      <button
                        key={r.name}
                        aria-label={`Show ${r.name}`}
                        aria-pressed={i === selected}
                        className={i === selected ? "active" : ""}
                        onClick={() => setSelected(i)}
                      />
                    ))}
                  </div>
                  <div>
                    <button
                      className="icon-button"
                      aria-label="Previous research image"
                      onClick={() => setSelected((selected + 2) % 3)}
                    >
                      <ChevronLeft size={20} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Next research image"
                      onClick={() => setSelected((selected + 1) % 3)}
                    >
                      <ChevronRight size={20} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div className="research-bottom">
              <div className="source-studies">
                <span className="tiny-label">ON THE RESEARCH BENCH</span>
                {gallery.map((g) => (
                  <button key={g.title} onClick={() => setLightbox(g)}>
                    <span className="study-icon">
                      <Microscope size={18} />
                    </span>
                    <span>
                      <strong>{g.title}</strong>
                      <small>{g.subtitle}</small>
                    </span>
                    <ArrowUpRight size={18} />
                  </button>
                ))}
              </div>
              <div className="data-story">
                <div>
                  <span className="tiny-label">FROM OBSERVATION TO DATA</span>
                  <span className="sample-badge">ILLUSTRATIVE</span>
                </div>
                <div
                  className="mini-chart"
                  aria-label="Illustrative stress-strain trend; not measured test data"
                >
                  <span>STRESS</span>
                  <svg viewBox="0 0 520 120" role="img">
                    <title>Illustrative rising stress-strain trend</title>
                    <defs>
                      <linearGradient
                        id="chartFill"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop stopColor="#b8d7b0" stopOpacity=".2" />
                        <stop offset="1" stopColor="#b8d7b0" stopOpacity="0" />
                      </linearGradient>
                    </defs>
                    {[20, 50, 80, 110].map((y) => (
                      <path
                        key={y}
                        d={`M0 ${y}H520`}
                        stroke="#303330"
                        strokeDasharray="3 5"
                      />
                    ))}
                    <path
                      d="M0 110 40 105 90 93 140 81 190 67 245 54 300 40 350 25 397 12 426 5 439 95 520 110V120H0Z"
                      fill="url(#chartFill)"
                    />
                    <path
                      d="M0 110 40 105 90 93 140 81 190 67 245 54 300 40 350 25 397 12 426 5 439 95 520 110"
                      fill="none"
                      stroke="#b8d7b0"
                      strokeWidth="2"
                    />
                  </svg>
                  <span>STRAIN →</span>
                </div>
                <button
                  className="text-button"
                  onClick={() => openWorkspace("data")}
                >
                  Explore the test-data workflow <ArrowRight size={15} />
                </button>
              </div>
            </div>
          </div>
        </section>
        <section className="section research-foundation">
          <div className="section-heading">
            <div>
              <span className="eyebrow">03 / THE RESEARCH FOUNDATION</span>
              <h2>
                Knowledge worth
                <br />
                building on.
              </h2>
            </div>
            <p>
              Research comes first. Explore a growing foundation of reviewed
              open-source datasets, data from published research studies, and
              evidence generated in our own lab.
            </p>
          </div>
          <div className="evidence-grid">
            <article>
              <span>01 / PUBLISHED EVIDENCE</span>
              <h3>Start with what is known.</h3>
              <p>
                Gather openly available composite research and datasets. Record
                the original source, reuse permissions, material system, units,
                and test conditions so you can understand the evidence behind
                each material record.
              </p>
            </article>
            <article>
              <span>02 / PHYSICAL RESEARCH</span>
              <h3>Ask what is missing.</h3>
              <p>
                Fabricate, test, and inspect specimens to fill gaps in the
                evidence. Compare predictions against independent tests and use
                the discrepancies to guide the next experiment.
              </p>
            </article>
            <article className="evidence-library">
              <span>03 / THE MATERIALS LIBRARY</span>
              <h3>Keep the evidence close.</h3>
              <p>
                Explore 22 initial source records for carbon, glass, and
                sandwich cores, alongside layups, governing equations, and
                topic-by-topic explanations.
              </p>
              <Link className="text-button" href="/library">
                Explore the materials library <ArrowUpRight size={16} />
              </Link>
            </article>
          </div>
        </section>
        <section className="direction-section section" id="direction">
          <div className="section-heading">
            <div>
              <span className="eyebrow">04 / OUR DIRECTION</span>
              <h2>
                Start small.
                <br />
                Prove it. Build forward.
              </h2>
            </div>
            <p>
              This is the first chapter, not the final blueprint.
              <br />
              Real test results will shape what comes next.
            </p>
          </div>
          <div className="roadmap">
            {[
              [
                "01",
                "The foundation",
                "Coupons",
                "Unnotched and open-hole tension. One material system. A physics pipeline validated against blind lab tests.",
                "CURRENT FOCUS",
              ],
              [
                "02",
                "Broaden the evidence",
                "More test families",
                "Compression, shear, and additional materials. Use uncertainty to guide the next tests.",
                "AFTER COUPON VALIDATION",
              ],
              [
                "03",
                "Understand the damage",
                "Elements & joints",
                "Progressive damage, joints, and future repair analysis, developed through relevant element tests.",
                "FUTURE EXPLORATION",
              ],
              [
                "04",
                "Scale the insight",
                "Panels & structures",
                "Carry the verified foundation toward stiffened panels, buckling, and wing optimization.",
                "LONG-TERM DIRECTION",
              ],
            ].map(([num, subtitle, title, desc, status], i) => (
              <article
                className={i === 0 ? "roadmap-card current" : "roadmap-card"}
                key={num}
              >
                <div className="roadmap-number">
                  {num}
                  <span>
                    {i === 0 ? <span className="status-dot" /> : <PlusMark />}
                  </span>
                </div>
                <span className="roadmap-subtitle">{subtitle}</span>
                <h3>{title}</h3>
                <p>{desc}</p>
                <span className="roadmap-status">{status}</span>
              </article>
            ))}
          </div>
          <div className="validation-gate">
            <Check size={16} />
            <span>
              The first gate: blind predictions checked against 10–20 lab
              coupons, with the acceptance band agreed from real data.
            </span>
          </div>
        </section>
        <section className="closing-section section">
          <span className="eyebrow">
            THE NEXT LAYER STARTS WITH A QUESTION.
          </span>
          <div>
            <h2>
              Let’s define what
              <br />
              comes next.
            </h2>
            <button className="button primary" onClick={() => openWorkspace()}>
              Start a conversation <ArrowUpRight size={18} />
            </button>
          </div>
          <div className="document-links">
            <span>EXPLORE THE RESEARCH</span>
            <Link href="/library">
              Materials & physics library <ArrowUpRight size={15} />
            </Link>
            <Link href="/about">
              Our research approach <ArrowUpRight size={15} />
            </Link>
          </div>
        </section>
      </main>
      <dialog
        ref={dialog}
        className="lightbox"
        onCancel={() => setLightbox(null)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setLightbox(null);
        }}
        aria-label={lightbox?.title || "Research image"}
      >
        <div className="lightbox-header">
          <span>{lightbox?.title}</span>
          <div>
            <a
              className="icon-button"
              href={lightbox?.image}
              download
              aria-label="Download source image"
            >
              <ArrowDownToLine size={18} />
            </a>
            <button
              className="icon-button"
              onClick={() => setLightbox(null)}
              aria-label="Close image viewer"
            >
              <X size={22} />
            </button>
          </div>
        </div>
        {lightbox && <img src={lightbox.image} alt={lightbox.title} />}
        <div className="lightbox-footer">
          SOURCE RESEARCH ASSET <span>Anisotropy AI / Research library</span>
        </div>
      </dialog>
    </>
  );
}
function PlusMark() {
  return <span className="plus-mark">+</span>;
}
