import Link from "next/link";
import {
  ArrowRight,
  FlaskConical,
  Layers3,
  Microscope,
  Repeat2,
} from "lucide-react";
import { CouponVisual } from "@/components/coupon-visual";

export const metadata = { title: "About — Anisotropy AI" };
export default function About() {
  return (
    <main id="main" className="inner-page">
      <section className="section page-intro">
        <span className="eyebrow">ABOUT / THE THINKING BEHIND THE WORK</span>
        <div className="intro-grid">
          <div>
            <h1>
              Engineering built
              <br />
              on <em>physical evidence.</em>
            </h1>
            <p>
              We prioritize research. Our composite model connects material
              properties, laminate physics, and a working lab to explain how a
              design responds—and why a particular region may fail.
            </p>
          </div>
          <div className="intro-aside">
            <span className="status-dot" />
            <span>COUPON-SCALE MVP</span>
            <p>
              Learn from the material.
              <br />
              Verify with the experiment.
              <br />
              Build from what holds up.
            </p>
          </div>
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
            Our lab connects fabrication, tensile testing, and microscopy. Each
            specimen can become a linked record of its geometry, process,
            measured response, and observed failure location.
          </p>
          <p>
            We plan to compare predictions with physical tests, then use
            reviewed evidence to refine and evaluate the engineering model.
            Failure location and failure mode are central research questions;
            agreement must be demonstrated with independent experiments.
          </p>
          <Link className="text-button" href="/#lab">
            Explore the research bench <ArrowRight size={15} />
          </Link>
        </div>
        <div className="lab-cycle">
          {[
            [Layers3, "Fabricate", "Geometry, material, layup, and process."],
            [
              FlaskConical,
              "Test",
              "Capture the response and where failure occurs.",
            ],
            [
              Microscope,
              "Investigate",
              "Connect fracture observations to the specimen.",
            ],
            [
              Repeat2,
              "Compare & learn",
              "Check predictions, review evidence, refine the model.",
            ],
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
            Inspired by our specimen-shape studies, tensile tests, and
            microscopy. Research observations guide the questions we ask next.
          </p>
        </div>
        <div className="research-context-grid">
          <div className="concept-panel">
            <div className="concept-top">
              <span>SPECIMEN SHAPE / LOAD PATH</span>
              <span className="sample-badge">CONCEPT</span>
            </div>
            <CouponVisual mode="failure" />
            <p>
              Investigate how geometry changes local stress and the region in
              which a specimen fails.
            </p>
          </div>
          <div className="context-notes">
            <article>
              <span>OBSERVE</span>
              <h3>Locate the fracture.</h3>
              <p>
                Relate the observed failure region to the gauge section,
                specimen geometry, and local features seen under microscopy.
              </p>
            </article>
            <article>
              <span>INVESTIGATE</span>
              <h3>Connect the mechanisms.</h3>
              <p>
                Compare the load path and predicted stress concentrations with
                test observations. A contour alone does not establish the cause
                of failure.
              </p>
            </article>
            <article>
              <span>VALIDATE</span>
              <h3>Test the revised design.</h3>
              <p>
                Fabricate again and compare measured behavior with predictions.
                Report uncertainty, limitations, and unexpected outcomes.
              </p>
            </article>
          </div>
        </div>
        <p className="context-disclosure">
          The supplied printed-polymer studies inform our experimental approach.
          They are not validation of the planned composite-laminate model.
          Study-specific measurements and performance percentages are not
          published here.
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
            The model follows a composite from its material properties and ply
            sequence to its response under a defined load. Laminate theory
            establishes the global response, local stress recovery examines each
            ply, and finite element analysis investigates geometry and critical
            regions.
          </p>
          <div className="learning-tags">
            <span>Strength & stiffness</span>
            <span>Failure location & mode</span>
            <span>Prediction uncertainty</span>
            <span>Physics–test discrepancy</span>
          </div>
          <p>
            Our research starts with coupons and documented assumptions.
            Published studies inform the material basis; fabrication, tensile
            testing, and microscopy help test the model against physical
            evidence. Reported values will remain tied to inspectable
            calculations and reviewed source records.
          </p>
        </div>
      </section>
    </main>
  );
}
