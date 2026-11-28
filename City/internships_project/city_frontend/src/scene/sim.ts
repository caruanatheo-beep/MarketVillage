// Client-side life of the building: where each agent stands, how it moves between
// floors, and the lift. Purely cosmetic; it reads server state and never writes any.
import { needsReview, type Agent, type Task } from "../client/types";
import { ANTEROOM, CAR_X, HEAD_LEVEL, LEVELS, ROOF_SPOTS, SEATS, footY } from "./building";
import type { Bubble, Pose } from "./people";

export type Mood = "idle" | "work" | "queued" | "review" | "error";
type Step = { k: "move"; x: number; y: number } | { k: "lift"; to: number; phase: 0 | 1 | 2 | 3 } | { k: "level"; level: number } | { k: "pose"; pose: Pose; dir: 1 | -1 };
export type Actor = { id: string; level: number; x: number; y: number; dir: 1 | -1; pose: Pose; mood: Mood;
  steps: Step[]; inCar: boolean; nextBreak: number; away: number; slot: number };
type Request = { actor: Actor; from: number; to: number; boarded: boolean; left: boolean };

const WALK = 30, LIFT = 70, RECENT_FAILURE_MS = 45 * 60 * 1000;

export class Sim {
  actors = new Map<string, Actor>();
  car = { y: footY(1), door: 0, target: 1 };
  private queue: Request[] = [];
  private current: Request | null = null;
  private delivering = false;
  private time = 0;

  constructor() {
    Object.entries(SEATS).forEach(([id, seat], index) => this.actors.set(id, { id, level: seat.level, x: seat.x, y: footY(seat.level),
      dir: 1, pose: "sit", mood: "idle", steps: [], inCar: false, nextBreak: 12 + index * 9, away: 0, slot: index }));
  }

  // Derives each agent's mood from the server snapshot and re-plans those that changed.
  sync(agents: Agent[], tasks: Task[]): void {
    const reviewing = new Set(tasks.filter(needsReview).map(task => task.agent_id));
    let slot = 0;
    for (const agent of agents) {
      const actor = this.actors.get(agent.id);
      if (!actor) continue;
      const failedAt = agent.latest?.finished_at ? Date.parse(agent.latest.finished_at) : 0;
      const mood: Mood = reviewing.has(agent.id) ? "review" : agent.status === "running" ? "work" : agent.status === "queued" ? "queued"
        : agent.status === "failed" && Date.now() - failedAt < RECENT_FAILURE_MS ? "error" : "idle";
      if (mood === "review" && agent.id !== "desk_manager") actor.slot = slot++;
      if (mood === actor.mood) continue;
      actor.mood = mood; actor.away = 0;
      this.goHome(actor);
    }
  }

  private goHome(actor: Actor): void {
    const seat = SEATS[actor.id];
    if (actor.mood === "review" && actor.id !== "desk_manager") this.plan(actor, HEAD_LEVEL, ANTEROOM(actor.slot), "wait", 1);
    else this.plan(actor, seat.level, seat.x, actor.mood === "work" ? "work" : actor.mood === "queued" ? "think" : actor.mood === "error" ? "error" : actor.mood === "review" ? "wait" : "sit", 1);
  }

  private plan(actor: Actor, level: number, x: number, pose: Pose, dir: 1 | -1): void {
    if (actor.inCar) { // Finish the ride first; the new plan is appended after it.
      const ride = actor.steps.findIndex(step => step.k === "lift");
      actor.steps = actor.steps.slice(0, ride + 2);
    } else {
      actor.steps = [];
      // Drop any pending lift call so the car never waits for someone who changed plans.
      this.queue = this.queue.filter(item => item.actor !== actor);
      if (this.current?.actor === actor) { this.current = null; this.delivering = false; }
    }
    const from = actor.inCar ? (actor.steps.find(step => step.k === "level") as { level: number } | undefined)?.level ?? actor.level : actor.level;
    if (from !== level) {
      if (Math.abs(from - level) === 1 && (actor.slot + level) % 2 === 0) {
        const up = level < from, low = footY(Math.max(from, level)), high = low - 96;
        const path: [number, number][] = [[590, low], [612, low - 48], [590, high]];
        if (!up) path.reverse();
        actor.steps.push({ k: "move", x: 582, y: footY(from) }, ...path.map(([px, py]) => ({ k: "move" as const, x: px, y: py })), { k: "level", level });
      } else {
        actor.steps.push({ k: "move", x: 72, y: footY(from) }, { k: "lift", to: level, phase: 0 }, { k: "level", level });
      }
    }
    actor.steps.push({ k: "move", x, y: footY(level) }, { k: "pose", pose, dir });
  }

  update(dt: number): void {
    this.time += dt;
    for (const actor of this.actors.values()) { this.ambient(actor); this.advance(actor, dt); }
    this.runCar(dt);
  }

  // Idle agents take a break on the roof or drop by a colleague, then come back.
  private ambient(actor: Actor): void {
    if (actor.mood !== "idle" || actor.steps.length) return;
    if (actor.away && this.time > actor.away) { actor.away = 0; this.goHome(actor); actor.nextBreak = this.time + 40 + Math.random() * 70; return; }
    if (actor.away || this.time < actor.nextBreak) return;
    const roll = Math.random();
    if (actor.id === "desk_manager") { if (roll < 0.5) { this.plan(actor, HEAD_LEVEL, 300, "stand", 1); actor.away = this.time + 14; } else actor.nextBreak = this.time + 30; return; }
    const busy = new Set([...this.actors.values()].filter(other => other.level === 0 || other.away).map(other => Math.round(other.x)));
    const spot = ROOF_SPOTS.filter(candidate => !busy.has(candidate.x))[Math.floor(Math.random() * ROOF_SPOTS.length)];
    const friend = [...this.actors.values()].filter(other => other !== actor && other.mood === "idle" && !other.away && !other.steps.length)[Math.floor(Math.random() * 6)];
    if (roll < 0.45 && spot) { this.plan(actor, 0, spot.x, spot.pose, 1); actor.away = this.time + 45; }
    else if (roll < 0.8 && friend) { this.plan(actor, friend.level, friend.x + 24, "talk", -1); actor.away = this.time + 30; }
    else actor.nextBreak = this.time + 25;
  }

  private advance(actor: Actor, dt: number): void {
    const step = actor.steps[0];
    if (!step) return;
    if (step.k === "pose") { actor.pose = step.pose; actor.dir = step.dir; actor.steps.shift(); return; }
    if (step.k === "level") { actor.level = step.level; actor.steps.shift(); return; }
    if (step.k === "move") {
      const dx = step.x - actor.x, dy = step.y - actor.y, distance = Math.hypot(dx, dy);
      if (distance < 0.6) { actor.x = step.x; actor.y = step.y; actor.steps.shift(); if (!actor.steps.length) actor.pose = "stand"; return; }
      const travel = Math.min(distance, WALK * dt);
      actor.x += dx / distance * travel; actor.y += dy / distance * travel;
      actor.pose = "walk"; if (Math.abs(dx) > 0.2) actor.dir = dx > 0 ? 1 : -1;
      return;
    }
    // Lift: call, board, ride, step out.
    const request = this.queue.find(item => item.actor === actor) || (this.current?.actor === actor ? this.current : null);
    if (step.phase === 0) { this.queue.push({ actor, from: actor.level, to: step.to, boarded: false, left: false }); step.phase = 1; actor.pose = "stand"; actor.dir = -1; return; }
    if (step.phase === 1) {
      if (!request || this.current !== request || this.delivering || this.car.door < 1 || Math.abs(this.car.y - footY(request.from)) > 0.5) return;
      const dx = CAR_X - actor.x;
      if (Math.abs(dx) > 0.6) { actor.x += Math.sign(dx) * Math.min(Math.abs(dx), WALK * dt); actor.pose = "walk"; actor.dir = -1; return; }
      actor.inCar = true; actor.pose = "stand"; actor.dir = 1; request.boarded = true; step.phase = 2; return;
    }
    if (step.phase === 2) {
      actor.y = this.car.y;
      if (request && this.delivering && this.car.door >= 1 && Math.abs(this.car.y - footY(step.to)) < 0.5) step.phase = 3;
      return;
    }
    const dx = 72 - actor.x;
    if (Math.abs(dx) > 0.6) { actor.x += Math.sign(dx) * Math.min(Math.abs(dx), WALK * dt); actor.pose = "walk"; actor.dir = 1; return; }
    actor.inCar = false; actor.y = footY(step.to); if (request) request.left = true; actor.steps.shift();
  }

  private runCar(dt: number): void {
    const car = this.car;
    if (!this.current) {
      if (car.door > 0) { car.door = Math.max(0, car.door - dt * 2); return; }
      const next = this.queue.shift();
      if (!next) return;
      this.current = next; this.delivering = false; car.target = next.from;
    }
    const request = this.current, goal = footY(car.target), done = this.delivering ? request.left : request.boarded;
    if (Math.abs(car.y - goal) > 0.5) {
      if (car.door > 0) { car.door = Math.max(0, car.door - dt * 2.5); return; }
      car.y += Math.sign(goal - car.y) * Math.min(Math.abs(goal - car.y), LIFT * dt); return;
    }
    car.y = goal;
    if (!done) { car.door = Math.min(1, car.door + dt * 2.5); return; }
    if (car.door > 0) { car.door = Math.max(0, car.door - dt * 2.5); return; }
    if (this.delivering) this.current = null; else { this.delivering = true; car.target = request.to; }
  }

  bubble(actor: Actor): Bubble {
    if (actor.mood === "review") return "alert";
    if (actor.mood === "error") return "error";
    if (actor.mood === "queued" || actor.pose === "talk") return "dots";
    return "none";
  }

  // Activity per floor, between 0 (asleep) and 1 (fully lit).
  floorActivity(): number[] {
    const levels: number[] = LEVELS.map((_, index) => index === 0 ? 0.6 : index === LEVELS.length - 1 ? 0.35 : 0);
    for (const actor of this.actors.values()) {
      const weight = actor.mood === "work" ? 1 : actor.mood === "review" ? 0.9 : actor.mood === "queued" ? 0.6 : actor.mood === "error" ? 0.5 : 0;
      const home = SEATS[actor.id].level;
      levels[home] = Math.max(levels[home], weight);
      if (actor.mood === "review") levels[HEAD_LEVEL] = Math.max(levels[HEAD_LEVEL], 0.9);
    }
    return levels;
  }

  reviewLevels(): Set<number> {
    const levels = new Set<number>();
    for (const actor of this.actors.values()) if (actor.mood === "review") levels.add(actor.level);
    return levels;
  }
}
