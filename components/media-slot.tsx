import type { CSSProperties } from "react";

export type MediaSlotProps = {
  /** What the picture or clip should show; printed inside an empty slot so the team knows what to supply. */
  label: string;
  caption?: string;
  /** A file under public/ (for example /assets/images/coupon-01.jpg). Empty: the labelled placeholder renders. */
  src?: string;
  alt?: string;
  poster?: string;
  ratio?: "16/9" | "4/3" | "3/2" | "1/1";
  kind?: "image" | "clip";
  className?: string;
};

/** One slot for a photo or a short clip (audit of 2026-10-31, items 9, 11 and 13). The team drops the file in
 * public/assets/images or public/assets/clips and sets `src` in one place; until then the slot says what belongs there.
 * Nothing is fetched from outside the site. */
export function MediaSlot({ label, caption, src, alt = "", poster, ratio = "16/9", kind = "image", className = "" }: MediaSlotProps) {
  const frame: CSSProperties = { aspectRatio: ratio };
  const word = kind === "clip" ? "CLIP" : "IMAGE";
  return (
    <figure className={`media-slot ${src ? "" : "media-slot-empty"} ${className}`.trim()}>
      <div className="media-slot-frame" style={frame}>
        {src ? (
          kind === "clip" ? (
            <video src={src} poster={poster} muted loop playsInline autoPlay aria-label={alt || label} />
          ) : (
            <img src={src} alt={alt} loading="lazy" />
          )
        ) : (
          <div className="media-slot-placeholder" role="img" aria-label={`${word.toLowerCase()} slot: ${label}`}>
            <span className="tiny-label">{word} SLOT</span>
            <strong>{label}</strong>
          </div>
        )}
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}
