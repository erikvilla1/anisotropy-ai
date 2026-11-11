/** The programmes and organisations that support the team, as the home page's strip shows them (components/home/logo-strip.tsx,
 * ADR-0077 amendment 14). A logo is listed only for a real, confirmed relationship. It is its owner's mark, so it is shown as
 * made: not recoloured, cropped or distorted. Adding a supporter is adding its file under public/assets/partners/ and a line
 * here; `width` and `height` are the file's own pixels, which keep its proportions on the page. */
export type Supporter = {
  /** The owner's name; it is the logo's text for a visitor who does not see the image. */
  name: string;
  /** The logo's path under public/. */
  src: string;
  width: number;
  height: number;
};

export const supporters: readonly Supporter[] = [
  { name: "UC San Diego, The Basement", src: "/assets/partners/uc-san-diego-the-basement.png", width: 684, height: 202 },
];
