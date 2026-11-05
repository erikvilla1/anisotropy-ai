import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FlaskConical,
  Layers3,
  Microscope,
  Repeat2,
  ShieldCheck,
} from "lucide-react";
import { CouponVisual } from "@/components/coupon-visual";
import { MediaSlot } from "@/components/media-slot";
import { roadmap, validationGate, workflowSteps } from "@/lib/about-content";
import { statusLabel, type ServiceStatus } from "@/lib/services";
import { team } from "@/lib/team";
import "../services/services.css";
import "./about.css";

export const metadata = {
  title: "About — Anisotropy",
  description:
    "Anisotropy is an engineering platform built only for composite structures: design, analysis, testing, fabrication and repair in one workflow, grounded in composite theory and real mechanical test data.",
};

/** The five parts of the workflow the platform is built for, each labelled as the service pages label them. */
const pillars: { title: string; status: ServiceStatus; text: string; href?: string }[] = [
  {
    title: "Design",
    status: "partly",
    text: "A laminate stated as its layup and material, a coupon as a few dimensions; the stiffness and the mesh follow from them. A CAD file to take elsewhere is planned.",
    href: "/services/computer-aided-design",
  },
  {
    title: "Analysis",
    status: "built",
    text: "Classical laminate theory for the stack and finite elements for the coupon, with CalculiX as the reference and first-ply failure by the criterion you choose.",
    href: "/services/finite-element-modeling",
  },
  {
    title: "Testing",
    status: "partly",
    text: "Coupons in the proportions of the ASTM standards, a checklist before any run, and our own tensile tests and microscopy to check the model against. The test-plan document is planned.",
    href: "/services/test-plans",
  },
  {
    title: "Fabrication",
    status: "planned",
    text: "The ply book and the cure cycle from the same record. Not built; the lab lays up its own coupons by hand today.",
    href: "/services/manufacturing-plans",
  },
  {
    title: "Repair",
    status: "planned",
    text: "Repair analysis comes after joints and damage, developed through element tests. Named here so the workflow is complete, not because it exists.",
  },
];

export default function About() {
  return (
    <main id="main" className="inner-page about-page">
      <section className="section page-intro">
        <span className="eyebrow">ABOUT / WHAT WE ARE BUILDING</span>
        <div className="intro-grid">
          <div>
            <h1>
              Engineering built
              <br />
              on <em>physical evidence.</em>
            </h1>
            <p>
              Anisotropy is an engineering platform built only for composite structures. Design, analysis, testing,
              fabrication and repair live in one workflow, grounded in composite theory and real mechanical test data.
            </p>
            <p>
              Every answer comes with its assumptions and references, so engineers can verify results and students can
              learn from them. Less time on repetitive setup and documentation, more time optimizing the structure.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>ONE WORKFLOW</span>
            <p>
              Design. Analyze. Test.
              <br />
              Fabricate. Repair.
              <br />
              One record through all of it.
            </p>
          </div>
        </div>
      </section>
      <section className="section about-building">
        <div className="section-heading">
          <div>
            <span className="eyebrow">WHAT WE ARE BUILDING</span>
            <h2>
              One platform,
              <br />
              only for composites.
            </h2>
          </div>
          <p>
            A composite part is designed, analyzed, tested, built and sometimes repaired by different people with
            different tools. We keep those steps on one record, so the layup the analyst used is the layup the lab laid
            up, and the number in the report is the number the engine computed.
          </p>
        </div>
        <div className="about-building-grid">
          <div className="about-pillars">
            {pillars.map((pillar) => (
              <article key={pillar.title}>
                <div>
                  <h3>{pillar.title}</h3>
                  <span className={`service-status service-status-${pillar.status}`}>{statusLabel[pillar.status]}</span>
                </div>
                <p>{pillar.text}</p>
                {pillar.href ? (
                  <Link href={pillar.href}>
                    The service page <ArrowUpRight size={13} />
                  </Link>
                ) : null}
              </article>
            ))}
          </div>
          <MediaSlot
            label="Microscopy of a tested coupon"
            src="/assets/images/microscopy.jpg"
            alt="Microscopy image of a composite specimen"
            ratio="4/3"
            caption="Where the model is checked: the lab's own specimens under the microscope."
          />
        </div>
      </section>
      <section className="section about-workflow">
        <div className="section-heading">
          <div>
            <span className="eyebrow">THE WORKFLOW</span>
            <h2>
              Better decisions.
              <br />
              Built layer by layer.
            </h2>
          </div>
          <div className="heading-description">
            <p>Composite design is a conversation between what we predict and what we can prove.</p>
            <p className="muted">
              The workflow brings those two worlds together, from the first specification to the next physical test.
            </p>
          </div>
        </div>
        <div className="workflow-grid">
          {workflowSteps.map((step, i) => (
            <article className="workflow-step" key={step.title}>
              <div className="step-top">
                <step.icon size={25} strokeWidth={1.4} />
                <span>0{i + 1}</span>
              </div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
              <span className="step-tag">
                {step.tag}
                {i < workflowSteps.length - 1 && <ArrowRight size={15} />}
              </span>
            </article>
          ))}
        </div>
        <div className="core-rule">
          <ShieldCheck size={20} />
          <p>
            <strong>Physics produces the numbers.</strong> Every conclusion connects to its material basis, method, and
            supporting evidence. A language model may draft an input or explain a result; it never produces a number.
          </p>
          <span>OUR CORE PRINCIPLE</span>
        </div>
      </section>
      <section className="section about-direction" id="direction">
        <div className="section-heading">
          <div>
            <span className="eyebrow">OUR DIRECTION</span>
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
          {roadmap.map((stage, i) => (
            <article className={i === 0 ? "roadmap-card current" : "roadmap-card"} key={stage.number}>
              <div className="roadmap-number">
                {stage.number}
                <span>{i === 0 ? <span className="status-dot" /> : <span className="plus-mark">+</span>}</span>
              </div>
              <span className="roadmap-subtitle">{stage.subtitle}</span>
              <h3>{stage.title}</h3>
              <p>{stage.text}</p>
              <span className="roadmap-status">{stage.status}</span>
            </article>
          ))}
        </div>
        <div className="validation-gate">
          <Check size={16} />
          <span>{validationGate}</span>
        </div>
      </section>
      <section className="section about-thesis">
        <div>
          <span className="tiny-label">ONE CONTINUOUS ENGINEERING LOOP</span>
          <h2>
            The model meets
            <br />
            the test bench.
          </h2>
          <p>
            Our lab connects fabrication, tensile testing, and microscopy. Each specimen can become a linked record of its
            geometry, process, measured response, and observed failure location.
          </p>
          <p>
            We compare predictions with physical tests, then use reviewed evidence to refine and evaluate the engineering
            model. Failure location and failure mode are central research questions; agreement must be demonstrated with
            independent experiments.
          </p>
          <MediaSlot label="A coupon in the tensile frame" ratio="16/9" />
        </div>
        <div className="lab-cycle">
          {[
            [Layers3, "Fabricate", "Geometry, material, layup, and process."],
            [FlaskConical, "Test", "Capture the response and where failure occurs."],
            [Microscope, "Investigate", "Connect fracture observations to the specimen."],
            [Repeat2, "Compare & learn", "Check predictions, review evidence, refine the model."],
          ].map(([Icon, title, description]) => {
            const I = Icon as typeof Layers3;
            return (
              <article key={String(title)}>
                <I size={21} />
                <div>
                  <h3>{String(title)}</h3>
                  <p>{String(description)}</p>
                </div>
                <ArrowRight size={15} />
              </article>
            );
          })}
        </div>
      </section>
      <section className="section research-context">
        <div className="section-heading">
          <div>
            <span className="eyebrow">RESEARCH CONTEXT</span>
            <h2>
              Where it fails
              <br />
              is part of the answer.
            </h2>
          </div>
          <p>
            Inspired by our specimen-shape studies, tensile tests, and microscopy. Research observations guide the
            questions we ask next.
          </p>
        </div>
        <div className="research-context-grid">
          <div className="concept-panel">
            <div className="concept-top">
              <span>SPECIMEN SHAPE / LOAD PATH</span>
              <span className="sample-badge">CONCEPT</span>
            </div>
            <CouponVisual mode="failure" />
            <p>Investigate how geometry changes local stress and the region in which a specimen fails.</p>
          </div>
          <div className="context-notes">
            <article>
              <span>OBSERVE</span>
              <h3>Locate the fracture.</h3>
              <p>
                Relate the observed failure region to the gauge section, specimen geometry, and local features seen under
                microscopy.
              </p>
            </article>
            <article>
              <span>INVESTIGATE</span>
              <h3>Connect the mechanisms.</h3>
              <p>
                Compare the load path and predicted stress concentrations with test observations. A contour alone does not
                establish the cause of failure.
              </p>
            </article>
            <article>
              <span>VALIDATE</span>
              <h3>Test the revised design.</h3>
              <p>
                Fabricate again and compare measured behavior with predictions. Report uncertainty, limitations, and
                unexpected outcomes.
              </p>
            </article>
          </div>
        </div>
        <p className="context-disclosure">
          The supplied printed-polymer studies inform our experimental approach. They are not validation of the planned
          composite-laminate model. Study-specific measurements and performance percentages are not published here.
        </p>
      </section>
      <section className="section learning-section">
        <div>
          <span className="eyebrow">WHAT THE MODEL DESCRIBES</span>
          <h2>
            More than
            <br />a predicted number.
          </h2>
        </div>
        <div>
          <p>
            The model follows a composite from its material properties and ply sequence to its response under a defined
            load. Laminate theory establishes the global response, local stress recovery examines each ply, and finite
            element analysis investigates geometry and critical regions.
          </p>
          <div className="learning-tags">
            <span>Strength & stiffness</span>
            <span>Failure location & mode</span>
            <span>Prediction uncertainty</span>
            <span>Physics–test discrepancy</span>
          </div>
          <p>
            Our research starts with coupons and documented assumptions. Published studies inform the material basis;
            fabrication, tensile testing, and microscopy help test the model against physical evidence. Reported values
            remain tied to inspectable calculations and reviewed source records.
          </p>
        </div>
      </section>
      <section className="section team-section" id="team">
        <div className="section-heading">
          <div>
            <span className="eyebrow">ABOUT US</span>
            <h2>The team.</h2>
          </div>
          <p>
            Five people, two seats each: one technical, one for the company. A lead decides alone inside the seat and
            checks with the CEO on anything that could alter results, cost, security, test plans or spending.
          </p>
        </div>
        <div className="team-grid">
          {team.map((person) => (
            <article className="team-card" key={person.name}>
              <MediaSlot label={`Portrait of ${person.name}`} ratio="1/1" />
              <h3>{person.name}</h3>
              {person.role ? <span className="tiny-label team-role">{person.role.toUpperCase()}</span> : null}
              <p>{person.technical.charAt(0).toUpperCase() + person.technical.slice(1)}.</p>
              {person.company ? <p>{person.company.charAt(0).toUpperCase() + person.company.slice(1)}.</p> : null}
            </article>
          ))}
        </div>
        <p className="team-note">
          The repository is public: the team's decisions, their reasons and the evidence behind every result are in it.
        </p>
      </section>
    </main>
  );
}
