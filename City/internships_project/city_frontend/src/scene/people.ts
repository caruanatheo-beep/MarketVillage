// Procedural characters, 20 native pixels tall (60 px on screen at the default ×3 zoom).
import { P, mix, type Ctx } from "./pixels";

export type Pose = "stand" | "walk" | "sit" | "work" | "think" | "wait" | "error" | "talk" | "putt";
export type Look = { skin: string; hair: string; top: string; bottom: string; style: 0 | 1 | 2 | 3; tie?: string };

const SKIN = [P.glow, mix(P.glow, P.rust, 0.3), mix(P.rust, P.glow, 0.35), mix(P.rust, P.plum, 0.25)];
const BROWN = mix(P.rust, P.ink, 0.45), GREY = mix(P.glow, P.indigo, 0.45), DENIM = mix(P.indigo, P.glow, 0.2), SLATE = mix(P.plum, P.ink, 0.3);

// Style: 0 short, 1 long, 2 bun, 3 cap.
export const LOOKS: Record<string, Look> = {
  desk_manager: { skin: SKIN[1], hair: GREY, top: mix(P.night, P.ink, 0.35), bottom: mix(P.night, P.ink, 0.5), style: 0, tie: P.amber },
  market_analyst: { skin: SKIN[0], hair: P.rust, top: mix(P.indigo, P.glow, 0.45), bottom: SLATE, style: 1 },
  finance_tutor: { skin: SKIN[2], hair: P.ink, top: mix(P.sage, P.glow, 0.3), bottom: DENIM, style: 0 },
  innovation_lab: { skin: SKIN[0], hair: P.amber, top: P.rust, bottom: SLATE, style: 2 },
  job_hunter: { skin: SKIN[1], hair: BROWN, top: mix(P.plum, P.glow, 0.4), bottom: DENIM, style: 3 },
  city_ui_engineer: { skin: SKIN[0], hair: P.plum, top: P.amber, bottom: SLATE, style: 1 },
  internships_engineer: { skin: SKIN[3], hair: P.ink, top: mix(P.sage, P.glow, 0.15), bottom: mix(P.plum, P.glow, 0.2), style: 0 },
  quality_engineer: { skin: SKIN[1], hair: P.amber, top: mix(P.indigo, P.glow, 0.25), bottom: SLATE, style: 0 },
  developer: { skin: SKIN[2], hair: BROWN, top: P.glow, bottom: mix(P.night, P.ink, 0.3), style: 0, tie: P.rust },
  internship_scout: { skin: SKIN[0], hair: BROWN, top: mix(P.amber, P.rust, 0.4), bottom: DENIM, style: 3 },
  networker: { skin: SKIN[1], hair: P.ink, top: mix(P.rust, P.glow, 0.35), bottom: SLATE, style: 1 },
  securities_scout: { skin: SKIN[0], hair: P.amber, top: mix(P.sage, P.glow, 0.4), bottom: DENIM, style: 2 },
  prime_services_scout: { skin: SKIN[3], hair: P.ink, top: mix(P.indigo, P.glow, 0.55), bottom: SLATE, style: 2 },
  outreach_agent: { skin: SKIN[2], hair: P.rust, top: mix(P.plum, P.amber, 0.45), bottom: DENIM, style: 1 },
};
const FALLBACK: Look = { skin: SKIN[0], hair: BROWN, top: P.sage, bottom: SLATE, style: 0 };

// `x` is the centre of the body, `foot` the floor line. `frame` advances four times per second.
export function drawPerson(c: Ctx, x: number, foot: number, id: string, pose: Pose, frame: number, dir: 1 | -1): void {
  const look = LOOKS[id] || FALLBACK, shade = mix(look.top, P.ink, 0.3);
  const p = (dx: number, dy: number, w: number, h: number, color: string) => {
    c.fillStyle = color; c.fillRect(Math.round(dir > 0 ? x + dx : x - dx - w), Math.round(foot + dy), w, h);
  };
  const seated = pose === "sit" || pose === "work" || pose === "think";
  const step = pose === "walk" ? frame % 4 : 0;
  const bob = step % 2 === 1 || (pose === "talk" && frame % 4 === 1) ? -1 : 0, droop = pose === "error" ? 1 : 0;

  c.fillStyle = "rgba(16,10,14,.4)"; c.fillRect(Math.round(x - 4), Math.round(foot), 9, 1);
  if (seated) {
    p(-1, -7, 5, 2, look.bottom); p(3, -5, 2, 4, look.bottom); p(3, -1, 3, 1, P.ink);
  } else {
    const front = step === 1 ? 1 : 0, back = step === 3 ? 1 : 0;
    p(-3 - back, -6, 2, 5 - back, look.bottom); p(1 + front, -6, 2, 5 - front, look.bottom);
    p(-3 - back, -1 - back, 3, 1, P.ink); p(1 + front, -1 - front, 3, 1, P.ink);
  }
  const b = bob + droop;
  p(-3, -13 + b, 6, 7, look.top);
  if (look.tie) { p(1, -13 + b, 1, 4, look.tie); p(0, -13 + b, 3, 1, P.glow); }
  // Arms.
  p(-4, -13 + b, 1, 5, shade);
  if (pose === "work") { p(2, -11 + b, 3, 1, shade); p(5, -11 + b + (frame % 2), 1, 1, look.skin); }
  else if (pose === "think") { p(3, -13 + b, 1, 2, shade); p(3, -15 + b, 1, 2, look.skin); }
  else if (pose === "putt") { p(3, -12 + b, 1, 4, shade); p(4, -8 + b, 1, 1, look.skin); p(5 + (frame % 4 === 1 ? 1 : 0), -8, 1, 7, P.glow); p(5, -1, 2, 1, P.glow); }
  else if (pose === "talk" && frame % 4 < 2) { p(3, -13 + b, 2, 1, shade); p(5, -14 + b, 1, 1, look.skin); }
  else { p(3, -13 + b + (step === 1 ? 1 : 0), 1, 5, shade); p(3, -8 + b, 1, 1, look.skin); p(-4, -8 + b, 1, 1, look.skin); }
  // Head.
  const h = b + (pose === "error" ? 1 : 0);
  p(-3, -20 + h, 6, 7, look.skin);
  p(-3, -20 + h, 6, 2, look.hair); p(-3, -18 + h, 1, 3, look.hair);
  if (look.style === 1) { p(-4, -19 + h, 2, 8, look.hair); p(-3, -20 + h, 6, 3, look.hair); }
  if (look.style === 2) p(-5, -20 + h, 2, 3, look.hair);
  if (look.style === 3) { p(-3, -21 + h, 6, 2, look.top); p(1, -19 + h, 4, 1, shade); }
  if (pose === "error") { p(0, -16 + h, 1, 1, P.ink); p(2, -16 + h, 1, 1, P.ink); }
  else if (frame % 16 !== 7) { p(0, -17 + h, 1, 2, P.ink); p(2, -17 + h, 1, 2, P.ink); }
  p(-3, -14 + h, 5, 1, mix(look.skin, P.rust, 0.25));
}

export type Bubble = "dots" | "alert" | "error" | "none";

// Status icon above the head. Drawn after the night layer so it always stays readable.
export function drawBubble(c: Ctx, x: number, foot: number, kind: Bubble, time: number): void {
  if (kind === "none") return;
  if (kind === "alert") {
    const y = Math.round(foot - 33 - Math.abs(Math.sin(time * 5)) * 4);
    c.fillStyle = P.ink; c.fillRect(x - 3, y - 1, 7, 11); c.fillRect(x - 4, y, 9, 9);
    c.fillStyle = P.amber; c.fillRect(x - 3, y, 7, 9);
    c.fillStyle = P.ink; c.fillRect(x - 1, y + 1, 3, 4); c.fillRect(x - 1, y + 6, 3, 2);
    return;
  }
  const y = Math.round(foot - 31), back = kind === "error" ? P.rust : P.glow;
  c.fillStyle = P.ink; c.fillRect(x - 5, y - 1, 11, 9); c.fillRect(x - 6, y, 13, 7); c.fillRect(x - 1, y + 8, 2, 2);
  c.fillStyle = back; c.fillRect(x - 5, y, 11, 7); c.fillRect(x - 1, y + 7, 2, 1);
  c.fillStyle = kind === "error" ? P.glow : P.ink;
  if (kind === "error") { for (let i = 0; i < 5; i++) { c.fillRect(x - 2 + i, y + 1 + i, 1, 1); c.fillRect(x + 2 - i, y + 1 + i, 1, 1); } }
  else for (let i = 0; i < 3; i++) if (Math.floor(time * 3) % 4 > i) c.fillRect(x - 3 + i * 3, y + 3, 1, 1);
}
