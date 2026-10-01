import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Box,
  FileText,
  Layers3,
  ScanLine,
  ShieldCheck,
} from "lucide-react";
import { CouponVisual } from "@/components/coupon-visual";
export const metadata = { title: "Services — Anisotropy AI" };
const offerings = [
  [
    Layers3,
    "Define the problem",
    "Capture geometry, material, ply sequence, loads, boundary conditions, and manufacturing constraints in one structured scope.",
    "01 / SCOPE",
  ],
  [
    BookOpen,
    "Choose a material basis",
    "Explore composite properties, thicknesses, architectures, and source references. Keep missing values and review status visible.",
    "02 / MATERIALS LIBRARY",
  ],
  [
    Box,
    "Build the geometry",
    "Create a parametric coupon, inspect dimensions and the load path, and carry a consistent geometry into CAD and meshing.",
    "03 / CAD & GEOMETRY",
  ],
  [
    ScanLine,
    "Investigate the response",
    "Connect laminate theory with finite element analysis to inspect stress, strain, critical plies, and possible failure regions.",
    "04 / ENGINEERING ANALYSIS",
  ],
  [
    Layers3,
    "Compare candidate layups",
    "Search for lighter stacks within the specified load, stiffness, symmetry, balance, and manufacturing constraints.",
    "05 / DESIGN EXPLORATION",
  ],
  [
    FileText,
    "Understand the conclusion",
    "Follow a detailed solution from assumptions and equations to verification, test comparison, and a reproducible report.",
    "06 / DOCUMENTATION & LEARNING",
  ],
] as const;
export default function Services() {
  return (
    <main id="main" className="inner-page services-page">
      <section className="section page-intro">
        <span className="eyebrow">
          SERVICES / ONE COMPOSITE DEVELOPMENT WORKFLOW
        </span>
        <div className="intro-grid">
          <div>
            <h1>
              From an engineering question
              <br />
              to <em>a documented answer.</em>
            </h1>
            <p>
              Bring the steps of composite development together: a material
              library, a clear specification, CAD, physics, FEA, and
              explanations that make the result understandable.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>RESEARCH-FIRST PRODUCT</span>
            <p>
              Start with the material.
              <br />
              Follow the physics.
              <br />
              Check against the experiment.
            </p>
          </div>
        </div>
        <div className="service-selectors">
          <Link href="/chat">
            <Layers3 size={23} />
            <div>
              <span>TRY THE EXPERIENCE</span>
              <h3>Engineering scope studio</h3>
            </div>
            <ArrowUpRight size={18} />
          </Link>
          <Link href="/library">
            <BookOpen size={23} />
            <div>
              <span>EXPLORE THE FOUNDATION</span>
              <h3>Materials & physics library</h3>
            </div>
            <ArrowUpRight size={18} />
          </Link>
        </div>
      </section>
      <section className="section product-offerings">
        <div className="section-heading">
          <div>
            <span className="eyebrow">LESS FRICTION BETWEEN STEPS</span>
            <h2>
              One question.
              <br />A connected process.
            </h2>
          </div>
          <p>
            The product we are developing keeps the inputs, methods, and
            evidence together as a composite moves from an idea to a testable
            design.
          </p>
        </div>
        <div className="offering-grid">
          {offerings.map(([Icon, title, desc, label]) => (
            <article key={title}>
              <div>
                <Icon size={25} strokeWidth={1.4} />
                <span>{label}</span>
              </div>
              <h3>{title}</h3>
              <p>{desc}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="engine-section">
        <div className="section">
          <div className="section-heading">
            <div>
              <span className="eyebrow">A CLOSER LOOK / YOUR ANALYSIS</span>
              <h2>
                Inspectable physics.
                <br />
                Traceable decisions.
              </h2>
            </div>
            <p>
              Follow your design from laminate response to a candidate layup,
              with the calculations, assumptions, and verification behind each
              decision available for review.
            </p>
          </div>
          <div className="engine-grid">
            <article>
              <span>01</span>
              <h3>Laminate physics</h3>
              <p>
                Classical Laminate Theory, Q and ABD matrices, local stress and
                strain recovery, maximum stress, Tsai–Hill, Tsai–Wu, and Hashin
                initiation.
              </p>
              <small>
                Open-hole models require calibration. Progressive damage is a
                later research phase.
              </small>
            </article>
            <article>
              <span>02</span>
              <h3>CAD & finite elements</h3>
              <p>
                Review coupon geometry, ply orientations, loads, and restraints
                alongside the resulting stress and strain fields.
              </p>
              <small>
                Understand local stress concentrations and compare the finite
                element response with laminate theory.
              </small>
            </article>
            <article>
              <span>03</span>
              <h3>Candidate screening</h3>
              <p>
                Compare many possible stacks against the same material basis,
                load cases, and design requirements. Identify candidates worth a
                detailed solve.
              </p>
              <small>
                Screening supports the search; shortlisted designs still pass
                engineering verification.
              </small>
            </article>
            <article>
              <span>04</span>
              <h3>Layup optimization</h3>
              <p>
                Find a light candidate that meets the specified constraints,
                with permitted orientations and symmetric or balanced stacking
                rules when required.
              </p>
              <small>
                Compare mass, stiffness, and failure margins with a clear record
                of the design requirements.
              </small>
            </article>
          </div>
          <div className="tool-note verification-note">
            <ShieldCheck size={27} />
            <div>
              <h3>The verification gate</h3>
              <p>
                Reviewed inputs. Nonnegative margins for a passing design. Mesh
                convergence. Comparable CLT and FEA results. A failed or
                unresolved check returns an investigation record with the
                reason, before a design can be reported as passing.
              </p>
            </div>
          </div>
        </div>
      </section>
      <section className="section solution-section">
        <div>
          <span className="eyebrow">THE ANSWER SHOULD TEACH YOU SOMETHING</span>
          <h2>
            See the result.
            <br />
            Understand the route.
          </h2>
          <p>
            For researchers, students, and engineering teams, a detailed
            solution is part of the product. Follow the transformations from
            global loads to local ply stresses and see why a criterion
            identifies a critical ply.
          </p>
          <ul className="solution-list">
            <li>Geometry and boundary-condition review</li>
            <li>Stress, strain, and failure-mode assessment</li>
            <li>Equations, substitutions, assumptions, and units</li>
            <li>Material references and reproducible inputs</li>
            <li>Verification history and a LaTeX report package</li>
          </ul>
          <Link className="text-button" href="/library">
            Inspect the physics catalog <ArrowRight size={16} />
          </Link>
        </div>
        <div className="concept-panel">
          <div className="concept-top">
            <span>COUPON / CRITICAL REGION</span>
            <span className="sample-badge">CONCEPT</span>
          </div>
          <CouponVisual mode="failure" />
          <p>
            Illustrative visualization. Numerical analysis and generated CAD
            files are planned capabilities.
          </p>
        </div>
      </section>
      <section className="section library-callout">
        <div>
          <span className="eyebrow">
            A CORE PRODUCT / THE MATERIALS LIBRARY
          </span>
          <h2>
            Build on knowledge.
            <br />
            Keep its source.
          </h2>
          <p>
            Carbon and glass composites, sandwich cores, ply thicknesses, and
            manufacturing context—connected to the methods used to understand
            them.
          </p>
          <Link className="button primary" href="/library">
            Explore the library <ArrowUpRight size={17} />
          </Link>
        </div>
        <div className="library-preview-list">
          {[
            "22 initial source material records",
            "Layup sequences & thickness context",
            "Topic-based functions & governing equations",
            "Source pages, units & review notes",
          ].map((s, i) => (
            <div key={s}>
              <span>0{i + 1}</span>
              {s}
              <BookOpen size={16} />
            </div>
          ))}
        </div>
      </section>
      <section className="section service-preview-note">
        <p>
          Explore the product preview. The scope conversation, source library,
          and local CSV review are interactive; production analysis, CAD
          generation, optimization, and automated detailed solutions will follow
          the engineering validation work.
        </p>
        <Link href="/data">
          Explore test-data submission <ArrowUpRight size={15} />
        </Link>
      </section>
    </main>
  );
}
