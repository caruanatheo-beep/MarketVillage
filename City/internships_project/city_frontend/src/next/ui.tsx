// Shared interface pieces: pixel icons, the game window, the agent portrait.
import React, { useEffect, useRef, useState } from "react";
import { drawPerson } from "../scene/people";

const ICONS: Record<string, string[]> = {
  code: ["............", "............", "...11...11..", "..11.....11.", ".11.......11", "11.........1", ".11.......11", "..11.....11.", "...11...11..", "............", "............", "............"],
  contacts: ["..11111111..", ".1........1.", ".1...11...1.", ".1..1111..1.", ".1...11...1.", ".1........1.", ".1..1111..1.", ".1.111111.1.", ".1.111111.1.", ".1........1.", "..11111111..", "............"],
  missions: ["..11111111..", "..1......1..", "..1.1111.1..", "..1......1..", "..1.1111.1..", "..1......1..", "..1.11...1..", "..1......1..", "..1.1111.1..", "..1......1..", "..11111111..", "............"],
  team: ["............", "...11...11..", "..1111.1111.", "..1111.1111.", "...11...11..", "............", ".1111..1111.", "111111111111", "111111111111", "111111111111", "............", "............"],
  internships: ["111111111111", "1..........1", "1.111..111.1", "1.111..111.1", "1.111..111.1", "1..........1", "1.111..111.1", "1.111..111.1", "1..........1", "111111111111", "..1......1..", "..1......1.."],
  notifications: [".....11.....", "....1111....", "...111111...", "...111111...", "..11111111..", "..11111111..", "..11111111..", ".1111111111.", ".1111111111.", "............", ".....11.....", "............"],
  settings: ["............", "..11........", "111111111111", "..11........", "............", "......11....", "111111111111", "......11....", "............", "...11.......", "111111111111", "...11......."],
  agent: ["....1111....", "....1111....", "....1111....", "....1111....", "............", "..11111111..", ".1111111111.", ".1111111111.", ".1111111111.", ".1111111111.", ".1111111111.", "............"],
  alert: ["....1111....", "....1111....", "....1111....", "....1111....", "....1111....", "....1111....", "....1111....", "............", "....1111....", "....1111....", "............", "............"],
  note: ["....1111111.", "....1111111.", "....1.....1.", "....1.....1.", "....1.....1.", "....1.....1.", "..111...111.", ".1111..1111.", ".1111..1111.", "..11....11..", "............", "............"],
};

export function Icon({ name, size = 24 }: { name: string; size?: number }): React.ReactElement {
  const rows = ICONS[name] || ICONS.alert;
  const path = rows.map((row, y) => [...row].map((cell, x) => cell === "1" ? `M${x} ${y}h1v1h-1z` : "").join("")).join("");
  return <svg className="pixel-icon" width={size} height={size} viewBox="0 0 12 12" shapeRendering="crispEdges" aria-hidden="true"><path d={path} fill="currentColor" /></svg>;
}

export function Portrait({ id, scale = 4 }: { id: string; scale?: number }): React.ReactElement {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current?.getContext("2d");
    if (!c) return;
    c.clearRect(0, 0, 16, 24); drawPerson(c, 8, 22, id, "stand", 0, 1);
  }, [id]);
  return <canvas ref={ref} className="portrait" width={16} height={24} style={{ width: 16 * scale, height: 24 * scale }} aria-hidden="true" />;
}

export function Panel(props: { title: string; icon: string; subtitle?: string; onClose(): void; children: React.ReactNode; narrow?: boolean }): React.ReactElement {
  return <section className={`game-window ${props.narrow ? "narrow" : ""}`} role="dialog" aria-label={props.title}>
    <header><Icon name={props.icon} size={24} /><div><h2>{props.title}</h2>{props.subtitle && <small>{props.subtitle}</small>}</div>
      <button type="button" className="window-close" onClick={props.onClose} aria-label="Fermer (Échap)">×</button></header>
    <div className="window-body">{props.children}</div>
  </section>;
}

// Counts towards the new value instead of jumping, like a resource counter in a game.
export function useCountUp(value: number): number {
  const [shown, setShown] = useState(value);
  useEffect(() => {
    if (shown === value) return;
    const id = window.setTimeout(() => setShown(shown + Math.sign(value - shown)), 60);
    return () => window.clearTimeout(id);
  }, [shown, value]);
  return shown;
}

export function when(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Paris" }).format(date);
}
