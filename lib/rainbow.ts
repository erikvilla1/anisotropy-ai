/** The rainbow most analysis programs draw, blue at a field's smallest value through cyan, green and yellow to red at its largest, as red,
 * green and blue from 0 to 1: the home page's demo colours its wing with it (ADR-0098, the lead's word of 2026-11-14: "make the FEA
 * analysis colors like that"), and the workspace's default scale, Classic, is the same five stops (ADR-0063 amendment 1, ADR-0098
 * amendment 12). Kept apart from `lib/demo-wing.ts` so the workspace does not load the demo's record. */
export const RAINBOW: [number, number, number][] = [[0, 0, 1], [0, 1, 1], [0, 1, 0], [1, 1, 0], [1, 0, 0]];
