import type { CSSProperties } from "react";

export type MediaSlotProps = {
  /** What the picture or clip shows: the clip's accessible name when it has no `alt`. */
  label: string;
  caption?: string;
  /** A file under public/ (for example /assets/images/microscopy.jpg). Without one the slot renders nothing: no placeholder ever
   * reaches a visitor (audit of 2026-11-12, about-industries-contact-1). */
  src?: string;
  /** Smaller WebP copies of the picture, as a `srcset` ("/a-800.webp 800w, /a-1600.webp 1600w"); `src` stays the fallback. */
  webpSrcSet?: string;
  /** How wide the picture is drawn, for `webpSrcSet`. */
  sizes?: string;
  /** The picture's own size in pixels, so the page keeps its space before it loads. */
  width?: number;
  height?: number;
  alt?: string;
  poster?: string;
  ratio?: "16/9" | "4/3" | "3/2" | "1/1";
  kind?: "image" | "clip";
  className?: string;
};

/** One slot for a photo or a short clip (audit of 2026-10-31, items 9, 11 and 13). A page sets `src` once a file is in
 * public/assets/images or public/assets/clips; until then the slot is not drawn. A clip never plays for a visitor who asked for
 * reduced motion and shows its controls, so it can be paused. Nothing is fetched from outside the site. */
export function MediaSlot({
  label, caption, src, webpSrcSet, sizes, width, height, alt = "", poster, ratio = "16/9", kind = "image", className = "",
}: MediaSlotProps) {
  if (!src) return null;
  const frame: CSSProperties = { aspectRatio: ratio };
  const image = <img src={src} width={width} height={height} alt={alt} loading="lazy" decoding="async" />;
  return (
    <figure className={`media-slot ${className}`.trim()}>
      <div className="media-slot-frame" style={frame}>
        {kind === "clip" ? (
          <video poster={poster} muted loop playsInline autoPlay controls aria-label={alt || label}>
            <source src={src} media="(prefers-reduced-motion: no-preference)" />
          </video>
        ) : webpSrcSet ? (
          <picture>
            <source type="image/webp" srcSet={webpSrcSet} sizes={sizes} />
            {image}
          </picture>
        ) : (
          image
        )}
      </div>
      {caption ? <figcaption>{caption}</figcaption> : null}
    </figure>
  );
}
