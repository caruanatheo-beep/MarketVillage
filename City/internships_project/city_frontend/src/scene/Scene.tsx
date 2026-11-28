// The building canvas. Receives server state, renders at an integer zoom, reports
// picks and camera info. It never calls the API.
import React, { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { Agent, Task } from "../client/types";
import { Backdrop } from "./backdrop";
import { BW, FACADE, FLOOR_H, GROUND, LEVELS, SKY, WORLD_H, bakeBuilding, drawCar, drawScreens, CAR_X } from "./building";
import { drawBubble, drawPerson } from "./people";
import { P, halo, makeCanvas, mix, px } from "./pixels";
import { Sim, type Actor } from "./sim";

export type SceneInfo = { camY: number; viewH: number; zoom: number; baseZoom: number; review: number[];
  anchor: { x: number; y: number; h: number } | null };
export type SceneHandle = { goToLevel(level: number): void; scrollLevels(delta: number): void; focusAgent(id: string): void; zoomBy(delta: number): void };
type Props = { agents: Agent[]; tasks: Task[]; selectedId: string; onPick(id: string): void; onInfo(info: SceneInfo): void };

const NIGHT_OFF = [98, 104, 158], NIGHT_ON = [222, 208, 202], MOONLIT = [132, 136, 180], TERRACE = [176, 166, 178];
const STREET = mix(P.ink, P.plum, 0.45);
const lerp = (a: number[], b: number[], t: number) => `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(",")})`;

export const Scene = forwardRef<SceneHandle, Props>(function Scene(props, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null), plateRef = useRef<HTMLDivElement>(null);
  const latest = useRef(props); latest.current = props;
  const sim = useRef<Sim | null>(null);
  const view = useRef({ camY: -30, target: -30, zoom: 0, base: 1, viewW: BW, viewH: 360, originX: 0, follow: "", followUntil: 0, mouseX: -1, mouseY: -1 });

  useImperativeHandle(ref, () => ({
    goToLevel(level) { const v = view.current; v.follow = ""; v.target = level * FLOOR_H - Math.round((v.viewH - FLOOR_H) / 2); },
    scrollLevels(delta) { const v = view.current; v.follow = ""; v.target += delta * FLOOR_H; },
    focusAgent(id) { const v = view.current; v.follow = id; v.followUntil = performance.now() + 8000; },
    zoomBy(delta) { const v = view.current; v.zoom = Math.max(1, Math.min(v.base + 1, (v.zoom || v.base) + delta)); },
  }), []);

  useEffect(() => { sim.current?.sync(props.agents, props.tasks); }, [props.agents, props.tasks]);

  useEffect(() => {
    const canvas = canvasRef.current!, out = canvas.getContext("2d")!;
    const building = bakeBuilding(), backdrop = new Backdrop(), world = new Sim();
    sim.current = world; world.sync(latest.current.agents, latest.current.tasks);
    let [frame, f] = makeCanvas(BW, 360), [inner, n] = makeCanvas(BW, 360), [shade, s] = makeCanvas(BW, 360);
    const activity = LEVELS.map(() => 0.3);
    const v = view.current;

    const resize = () => {
      const rect = canvas.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr)); canvas.height = Math.max(1, Math.round(rect.height * dpr));
      v.base = Math.max(1, Math.floor(canvas.width / BW));
    };
    resize();
    const observer = new ResizeObserver(resize); observer.observe(canvas);

    let last = performance.now(), raf = 0, infoAt = 0;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.05, (now - last) / 1000), time = now / 1000; last = now;
      const zoom = Math.max(1, Math.min(v.base + 1, v.zoom || v.base));
      v.viewW = Math.ceil(canvas.width / zoom); v.viewH = Math.ceil(canvas.height / zoom); v.originX = Math.floor((v.viewW - BW) / 2);
      if (frame.width !== v.viewW || frame.height !== v.viewH) {
        [frame, f] = makeCanvas(v.viewW, v.viewH); [inner, n] = makeCanvas(v.viewW, v.viewH); [shade, s] = makeCanvas(v.viewW, v.viewH);
      }
      world.update(dt);
      world.floorActivity().forEach((goal, i) => { activity[i] += (goal - activity[i]) * Math.min(1, dt * 0.9); });

      // Camera: vertical only, clamped between the sky above the roof and the street.
      const followed = v.follow && now < v.followUntil ? world.actors.get(v.follow) : null;
      if (followed) v.target = followed.y - Math.round(v.viewH * 0.62);
      const low = -SKY, high = WORLD_H + GROUND + Math.ceil(104 * (window.devicePixelRatio || 1) / zoom) - v.viewH;
      v.target = high < low ? high : Math.max(low, Math.min(high, v.target));
      v.camY += (v.target - v.camY) * Math.min(1, dt * 9);
      if (Math.abs(v.target - v.camY) < 0.4) v.camY = v.target;
      const camY = Math.round(v.camY), ox = v.originX;

      backdrop.draw(f, v.viewW, v.viewH, ox, camY + SKY, time);
      // The street runs across the whole view under the neighbouring buildings.
      px(f, 0, WORLD_H - camY, v.viewW, 2, mix(STREET, P.glow, 0.25)); px(f, 0, WORLD_H + 2 - camY, v.viewW, Math.max(0, v.viewH - (WORLD_H + 2 - camY)), STREET);

      // Interior layer: baked building, live screens, lift and people.
      n.clearRect(0, 0, v.viewW, v.viewH); n.save(); n.translate(ox, -camY);
      n.drawImage(building.canvas, 0, 0);
      drawScreens(n, time, activity[2]);
      const actors = [...world.actors.values()], riders = actors.filter(actor => actor.inCar);
      const person = (actor: Actor, x = actor.x) => drawPerson(n, Math.round(x), Math.round(actor.y), actor.id, actor.pose, Math.floor(time * (actor.pose === "walk" ? 8 : 4) + actor.slot), actor.dir);
      drawCar(n, Math.round(world.car.y), world.car.door, riders.length ? () => riders.forEach(actor => person(actor, CAR_X)) : null);
      actors.filter(actor => !actor.inCar).sort((a, b) => a.x - b.x).forEach(actor => person(actor));
      n.restore();

      // Night: one multiply tone per floor, limited to the opaque interior pixels.
      s.globalCompositeOperation = "source-over"; s.clearRect(0, 0, v.viewW, v.viewH); s.save(); s.translate(ox, -camY);
      LEVELS.forEach((_, i) => { s.fillStyle = i === 0 ? lerp(TERRACE, TERRACE, 0) : lerp(NIGHT_OFF, NIGHT_ON, activity[i]); s.fillRect(0, i * FLOOR_H, BW, FLOOR_H); });
      s.fillStyle = lerp(MOONLIT, MOONLIT, 0); s.fillRect(0, -SKY, BW, SKY); s.fillRect(0, 0, FACADE, WORLD_H); s.fillRect(BW - FACADE, 0, FACADE, WORLD_H);
      s.fillStyle = lerp(NIGHT_OFF, NIGHT_OFF, 0); s.fillRect(0, WORLD_H, BW, GROUND);
      s.restore(); s.globalCompositeOperation = "destination-in"; s.drawImage(inner, 0, 0);
      n.globalCompositeOperation = "multiply"; n.drawImage(shade, 0, 0); n.globalCompositeOperation = "source-over";
      f.drawImage(inner, 0, 0);
      // People are redrawn half-bright over the night tone so they always read.
      f.save(); f.translate(ox, -camY); f.globalAlpha = 0.55;
      actors.forEach(actor => drawPerson(f, Math.round(actor.inCar ? CAR_X : actor.x), Math.round(actor.y), actor.id, actor.pose, Math.floor(time * (actor.pose === "walk" ? 8 : 4) + actor.slot), actor.dir));
      f.restore();

      // Warm additive light on every lamp, screen and window.
      f.save(); f.translate(ox, -camY); f.globalCompositeOperation = "lighter";
      for (const light of building.lights) {
        if (light.y + light.r < camY || light.y - light.r > camY + v.viewH) continue;
        const power = light.base + (1 - light.base) * activity[light.level];
        f.globalAlpha = Math.min(1, power * (light.flicker ? 0.85 + 0.15 * Math.sin(time * 6 + light.x) : 1));
        f.drawImage(halo(light.r, light.color), light.x - light.r, light.y - light.r);
      }
      f.globalAlpha = 0.7; f.drawImage(halo(30, P.glow), CAR_X - 30, Math.round(world.car.y) - 52);
      for (const actor of actors) if (actor.mood === "review") {
        f.globalAlpha = 0.55 + 0.35 * Math.sin(time * 4); f.drawImage(halo(22, P.amber), Math.round(actor.x) - 22, Math.round(actor.y) - 34);
      }
      f.globalAlpha = 1; f.globalCompositeOperation = "source-over";
      // Status icons and the selection marker stay at full brightness.
      const nx = Math.floor(v.mouseX / zoom) - ox, ny = Math.floor(v.mouseY / zoom) + camY;
      let hovered: Actor | null = null;
      for (const actor of actors) {
        drawBubble(f, Math.round(actor.x), Math.round(actor.y), world.bubble(actor), time);
        if (v.mouseX >= 0 && Math.abs(nx - actor.x) <= 7 && ny >= actor.y - 23 && ny <= actor.y + 2) hovered = actor;
        if (actor.id === latest.current.selectedId) {
          const y = Math.round(actor.y) - 26 - (Math.floor(time * 3) % 2), x = Math.round(actor.x);
          px(f, x - 2, y, 5, 1, P.amber); px(f, x - 1, y + 1, 3, 1, P.amber); px(f, x, y + 2, 1, 1, P.amber);
        }
      }
      f.restore();

      out.imageSmoothingEnabled = false;
      out.drawImage(frame, 0, 0, v.viewW * zoom, v.viewH * zoom);

      // Name plate and cursor follow the hovered agent without any React render.
      const plate = plateRef.current, dpr = window.devicePixelRatio || 1;
      canvas.style.cursor = hovered ? "pointer" : "default";
      if (plate) {
        if (hovered) {
          const agent = latest.current.agents.find(item => item.id === hovered!.id);
          plate.textContent = agent ? `${agent.name} · ${agent.role}` : hovered.id;
          plate.style.transform = `translate(${(Math.round(hovered.x) + ox) * zoom / dpr}px, ${(Math.round(hovered.y) - camY - 30) * zoom / dpr}px) translate(-50%, -100%)`;
          plate.hidden = false;
        } else plate.hidden = true;
      }
      canvas.dataset.hover = hovered?.id || "";
      if (now - infoAt > 120) {
        infoAt = now;
        const picked = world.actors.get(latest.current.selectedId);
        latest.current.onInfo({ camY, viewH: v.viewH, zoom, baseZoom: v.base, review: [...world.reviewLevels()],
          anchor: picked ? { x: (Math.round(picked.x) + ox) * zoom / dpr, y: (Math.round(picked.y) - camY) * zoom / dpr, h: 22 * zoom / dpr } : null });
      }
    };
    raf = requestAnimationFrame(tick);

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      if (event.ctrlKey) { v.zoom = Math.max(1, Math.min(v.base + 1, (v.zoom || v.base) + (event.deltaY < 0 ? 1 : -1))); return; }
      v.follow = ""; v.target += event.deltaY * 0.4;
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => { cancelAnimationFrame(raf); observer.disconnect(); canvas.removeEventListener("wheel", onWheel); sim.current = null; };
  }, []);

  const track = (event: React.MouseEvent) => {
    const rect = canvasRef.current!.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    view.current.mouseX = (event.clientX - rect.left) * dpr; view.current.mouseY = (event.clientY - rect.top) * dpr;
  };
  return <div className="scene">
    <canvas ref={canvasRef} aria-label="Immeuble MarketDesk en coupe" onMouseMove={track}
      onMouseLeave={() => { view.current.mouseX = -1; }}
      onClick={event => { track(event); window.setTimeout(() => props.onPick(canvasRef.current?.dataset.hover || ""), 40); }} />
    <div className="nameplate" ref={plateRef} hidden />
  </div>;
});
