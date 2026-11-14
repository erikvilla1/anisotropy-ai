import Link from "next/link";
import {
  ArrowRight,
  Flag,
  FlaskConical,
  Layers3,
  Microscope,
  Repeat2,
  ShieldCheck,
} from "lucide-react";
import { CouponVisual } from "@/components/coupon-visual";
import { MediaSlot } from "@/components/media-slot";
import { modelGoals, modelSubjects, roadmap, validationGate, workflowSteps } from "@/lib/about-content";
import { findService, serviceHref, statusLabel, type ServiceStatus } from "@/lib/services";
import { team } from "@/lib/team";
import "../inner-pages.css";
import "./about.css";

export const metadata = {
  title: "About",
  description:
    "Anisotropy is an engineering platform built only for composite structures. Design, analysis, and testing share one record today, grounded in composite theory and real mechanical test data; fabrication and repair are planned on the same record.",
};

/** The five parts of the workflow the platform is built for, each labelled as the service pages label them; a part with a
 * service page links to it by the service's name. */
const pillars: { title: string; status: ServiceStatus; text: string; service?: string }[] = [
  {
    title: "Design",
    status: "partly",
    text: "A laminate stated as its layup and material, a coupon as a few dimensions; the stiffness and the mesh follow from them. A CAD file to take elsewhere is planned.",
    service: "computer-aided-design",
  },
  {
    title: "Analysis",
    status: "built",
    text: "Classical laminate theory for the stack and finite elements for the coupon, checked against a reference solver, with first-ply failure by the criterion you choose.",
    service: "finite-element-modeling",
  },
  {
    title: "Testing",
    status: "partly",
    text: "Coupons sized to ASTM D3039, a setup check before any run, and our own tensile tests and microscopy to check the model against. The test-plan document is planned.",
    service: "test-plans",
  },
  {
    title: "Fabrication",
    status: "planned",
    text: "The ply book and the cure cycle from the same record. Not built; the lab lays up its own coupons by hand today.",
    service: "manufacturing-plans",
  },
  {
    title: "Repair",
    status: "planned",
    text: "Repair analysis comes after joints and damage, developed through element tests. Named here so the workflow is complete, not because it exists.",
  },
];

/** The lab's loop, one row per step. */
const loop = [
  { icon: Layers3, title: "Fabricate", text: "Geometry, material, layup, and process." },
  { icon: FlaskConical, title: "Test", text: "Capture the response and where failure occurs." },
  { icon: Microscope, title: "Investigate", text: "Connect fracture observations to the specimen." },
  { icon: Repeat2, title: "Compare and learn", text: "Check predictions, review evidence, refine the model." },
] as const;

export default function About() {
  return (
    <main id="main" className="kit-page about-page">
      <section className="page-opening">
        <p className="page-opening-label">ABOUT</p>
        <h1 className="page-opening-title">
          Engineering built{" "}
          <br />
          on <em>physical evidence.</em>
        </h1>
        <div className="page-opening-grid">
          <div className="page-opening-copy">
            <p>
              Anisotropy is an engineering platform built only for composite structures. Design, analysis, and testing
              share one record today, grounded in composite theory and real mechanical test data; fabrication and repair
              are planned on the same record.
            </p>
            <p>
              Every answer comes with its assumptions and references, so engineers can verify results and students can
              learn from them. Less time on repetitive setup and documentation, more time optimizing the structure.
            </p>
          </div>
          <div className="page-opening-note">
            <p className="page-opening-note-label">ONE WORKFLOW</p>
            <p>
              Design. Analyze. Test.
              <br />
              Fabrication and repair next.
              <br />
              One record through all of it.
            </p>
          </div>
        </div>
      </section>
      <section className="band is-light about-building">
        <div className="band-head">
          <p className="band-label">WHAT WE ARE BUILDING</p>
          <div className="band-statement">
            <h2>
              One platform,
              <br />
              only for composites.
            </h2>
            <p>
              A composite part is designed, analyzed, tested, built, and sometimes repaired by different people with
              different tools. We keep those steps on one record, so the layup the analyst used is the layup the lab laid
              up, and the number in the report is the number the analysis computed.
            </p>
          </div>
        </div>
        <div className="about-pillars">
          {pillars.map((pillar) => {
            const service = pillar.service ? findService(pillar.service) : undefined;
            return (
              <article className="kit-row" key={pillar.title}>
                <div className="kit-row-head about-pillar-head">
                  <h3 className="kit-title">{pillar.title}</h3>
                  <span className={`kit-status kit-status-${pillar.status}`}>{statusLabel[pillar.status]}</span>
                </div>
                <p className="kit-row-body kit-text">{pillar.text}</p>
                {service ? (
                  <Link className="kit-row-aside kit-link" href={serviceHref(service)}>
                    {service.title} <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                ) : null}
              </article>
            );
          })}
        </div>
        <MediaSlot
          className="about-figure"
          label="Microscopy of a tested coupon"
          src="/assets/images/microscopy.jpg"
          webpSrcSet="/assets/images/microscopy-800.webp 800w, /assets/images/microscopy-1600.webp 1600w"
          sizes="(max-width: 1023px) 100vw, 50vw"
          width={2880}
          height={2160}
          alt="Microscopy image of a composite specimen"
          ratio="4/3"
          caption="The lab's own specimens under the microscope."
        />
      </section>
      <section className="band about-workflow">
        <div className="band-head">
          <p className="band-label">THE WORKFLOW</p>
          <div className="band-statement">
            <h2>
              Better decisions.
              <br />
              Built layer by layer.
            </h2>
            <p>Composite design is a conversation between what we predict and what we can prove.</p>
            <p>
              The workflow brings those two worlds together, from the first specification to the next physical test.
            </p>
          </div>
        </div>
        <div className="band-grid">
          {workflowSteps.map((step, i) => (
            <article className="band-card about-step" key={step.title}>
              <div className="about-step-top">
                <step.icon size={24} strokeWidth={1.4} aria-hidden="true" />
                <span className="kit-mono">0{i + 1}</span>
              </div>
              <h3 className="kit-title">{step.title}</h3>
              <p>{step.text}</p>
              <span className="kit-mono about-step-tag">{step.tag}</span>
            </article>
          ))}
        </div>
        <div className="kit-note">
          <span className="kit-mono kit-note-lead">
            <ShieldCheck size={18} strokeWidth={1.6} aria-hidden="true" />
            OUR CORE PRINCIPLE
          </span>
          <p className="kit-note-text">
            <strong>Physics produces the numbers.</strong> Every conclusion connects to its material basis, method, and
            supporting evidence. A language model may draft an input or explain a result; it never produces a number.
          </p>
        </div>
      </section>
      <section className="band is-light about-direction" id="direction">
        <div className="band-head">
          <p className="band-label">OUR DIRECTION</p>
          <div className="band-statement">
            <h2>
              Start small.
              <br />
              Prove it. Build forward.
            </h2>
            <p>
              This is the first chapter, not the final blueprint.
              <br />
              Real test results will shape what comes next.
            </p>
          </div>
        </div>
        <div className="band-grid">
          {roadmap.map((stage, i) => (
            <article className={i === 0 ? "about-stage is-current" : "about-stage"} key={stage.number}>
              <div className="about-stage-number">
                {stage.number}
                <span className={i === 0 ? "about-stage-dot" : "about-stage-ring"} aria-hidden="true" />
              </div>
              <span className="kit-mono">{stage.subtitle}</span>
              <h3 className="kit-title">{stage.title}</h3>
              <p>{stage.text}</p>
              <span className="kit-mono about-stage-status">{stage.status}</span>
            </article>
          ))}
        </div>
        <div className="kit-note">
          <p className="kit-note-text has-icon">
            <Flag size={18} aria-hidden="true" />
            <span>{validationGate}</span>
          </p>
        </div>
      </section>
      <section className="band about-lab">
        <div className="band-head">
          <p className="band-label">ONE CONTINUOUS ENGINEERING LOOP</p>
          <div className="band-statement">
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
          </div>
        </div>
        <div className="band-grid">
          <div className="about-lab-cycle">
            {loop.map(({ icon: Icon, title, text }) => (
              <article key={title}>
                <Icon size={22} strokeWidth={1.4} aria-hidden="true" />
                <div>
                  <h3 className="kit-title">{title}</h3>
                  <p>{text}</p>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
      <section className="band is-light about-context">
        <div className="band-head">
          <p className="band-label">RESEARCH CONTEXT</p>
          <div className="band-statement">
            <h2>
              Where it fails
              <br />
              is part of the answer.
            </h2>
            <p>
              Inspired by our specimen-shape studies, tensile tests, and microscopy. Research observations guide the
              questions we ask next.
            </p>
          </div>
        </div>
        <div className="band-grid">
          <div className="kit-figure about-context-figure">
            <div className="kit-figure-top">
              <span>TENSION STRIP / REGION TO INVESTIGATE</span>
              <span className="kit-badge">CONCEPT</span>
            </div>
            <CouponVisual mode="failure" />
            <p>Investigate the region in which a specimen fails: in its gauge section, or at the end of a tab.</p>
          </div>
          <div className="about-context-notes">
            <article>
              <span className="kit-mono">OBSERVE</span>
              <h3 className="kit-title">Locate the fracture.</h3>
              <p>
                Relate the observed failure region to the gauge section, specimen geometry, and local features seen under
                microscopy.
              </p>
            </article>
            <article>
              <span className="kit-mono">INVESTIGATE</span>
              <h3 className="kit-title">Connect the mechanisms.</h3>
              <p>
                Compare the load path and predicted stress concentrations with test observations. A contour alone does not
                establish the cause of failure.
              </p>
            </article>
            <article>
              <span className="kit-mono">VALIDATE</span>
              <h3 className="kit-title">Test the revised design.</h3>
              <p>
                Fabricate again and compare measured behavior with predictions. Report uncertainty, limitations, and
                unexpected outcomes.
              </p>
            </article>
          </div>
        </div>
        <div className="kit-note">
          <p className="kit-note-text">
            Our printed-polymer specimen studies shape the test approach; they are not a validation of the laminate model.
            Study-specific measurements and performance percentages are not published here.
          </p>
        </div>
      </section>
      <section className="band about-model">
        <div className="band-head">
          <p className="band-label">WHAT THE MODEL DESCRIBES</p>
          <div className="band-statement">
            <h2>
              More than
              <br />a predicted number.
            </h2>
            <p>
              The model follows a composite from its material properties and ply sequence to its response under a defined
              load. Laminate theory establishes the global response, local stress recovery examines each ply, and finite
              element analysis investigates geometry and critical regions.
            </p>
          </div>
        </div>
        <div className="band-grid about-model-tags">
          {modelSubjects.map((subject) => (
            <span key={subject}>{subject}</span>
          ))}
        </div>
        <div className="band-grid about-model-tags about-model-goals">
          <p className="kit-mono">RESEARCH GOALS</p>
          {modelGoals.map((goal) => (
            <span key={goal}>{goal}</span>
          ))}
        </div>
        <div className="band-grid">
          <p className="kit-text about-model-text">
            Our research starts with coupons and documented assumptions. Published studies inform the material basis;
            fabrication, tensile testing, and microscopy help test the model against physical evidence. Reported values
            remain tied to inspectable calculations and reviewed source records.
          </p>
        </div>
      </section>
      <section className="band is-light about-team" id="team">
        <div className="band-head">
          <p className="band-label">ABOUT US</p>
          <div className="band-statement">
            <h2>The team.</h2>
            <p>
              Five people, two seats each: one technical, one for the company. A lead decides alone inside the seat and
              checks with the CEO on anything that could alter results, cost, security, test plans or spending.
            </p>
          </div>
        </div>
        <div className="band-grid">
          {/* A card is the name and the seats. It shows no portrait yet: the portraits in lib/team.ts are on the home page's cards
              (ADR-0077 amendment 29, each person's consent still to be confirmed), and About's cards take them with Kai's work on
              the team cards. */}
          <div className="team-grid">
            {team.map((person) => (
              <article className="team-card" key={person.name}>
                <div className="team-card-body">
                  <h3 className="kit-title">{person.name}</h3>
                  {person.role ? <span className="kit-mono team-role">{person.role}</span> : null}
                  <p>{person.technical.charAt(0).toUpperCase() + person.technical.slice(1)}.</p>
                  {person.company ? <p>{person.company.charAt(0).toUpperCase() + person.company.slice(1)}.</p> : null}
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
