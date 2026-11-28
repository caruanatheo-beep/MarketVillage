// Talking to the Desk Manager, role-playing-game style: portrait, text box, choices.
import React, { useEffect, useRef, useState } from "react";
import { actions, streamChat } from "../client/api";
import type { ChatMessage } from "../client/types";
import { Portrait } from "./ui";

const CHOICES: [string, string, string][] = [
  ["Bilan du jour", "Présente le bilan du jour : développement, contacts et stages.", "daily_summary"],
  ["Bilan du code", "Fais le bilan du développement aujourd’hui : changements intégrés, vérifications, échecs et travaux en attente.", "development_report"],
  ["Bilan des contacts", "Quels sont les derniers résultats de Lina, Clara et Élodie ?", "contacts_report"],
  ["Reprendre les missions en attente", "Reprends maintenant les missions en attente, jusqu’à huit, en conservant leurs dépendances. Indique ce qui a réellement été remis en file.", "resume_pending"],
  ["Relancer les échecs", "Vérifie les missions récentes en échec et relance celles qui peuvent reprendre, jusqu’à huit. Explique les reprises et les blocages restants.", "resume_failed"],
];

export function Dialogue(props: { draft: string; onClose(): void; onRefresh(): Promise<void> }): React.ReactElement {
  const [messages, setMessages] = useState<ChatMessage[]>([]), [input, setInput] = useState(props.draft);
  const [busy, setBusy] = useState(false), [status, setStatus] = useState(""), [error, setError] = useState(""), [history, setHistory] = useState(false);
  const abort = useRef<AbortController | null>(null), scroll = useRef<HTMLDivElement>(null);
  useEffect(() => { setInput(props.draft); }, [props.draft]);
  useEffect(() => { void actions.chatHistory().then(data => { if (!abort.current) setMessages(data.messages || []); }).catch(exc => setError(exc instanceof Error ? exc.message : "Historique indisponible.")); }, []);
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [messages, status, history]);

  const patchLast = (change: (message: ChatMessage) => ChatMessage) => setMessages(rows => {
    const copy = [...rows], last = copy[copy.length - 1];
    if (last?.role === "assistant") copy[copy.length - 1] = change(last);
    return copy;
  });
  async function send(text: string, intent?: string): Promise<void> {
    const message = text.trim();
    if (!message || busy) return;
    setMessages(rows => [...rows, { role: "user", content: message }, { role: "assistant", content: "" }]);
    setInput(""); setBusy(true); setError(""); setStatus("Le Desk Manager réfléchit…");
    const controller = new AbortController(); abort.current = controller;
    try {
      await streamChat(message, intent, controller.signal, event => {
        if (event.type === "delta") { setStatus(""); patchLast(last => ({ ...last, content: last.content + (event.text || "") })); }
        if (event.type === "replace") patchLast(last => ({ ...last, content: event.text || "" }));
        if (event.type === "status") setStatus(event.text || "");
        if (event.type === "tool") setStatus(`${event.name || "Service"} · ${event.status === "running" ? "en cours…" : "terminé"}`);
        if (event.type === "error") setError(event.text || "La génération a échoué.");
      });
    } catch (exc) {
      setError(exc instanceof DOMException && exc.name === "AbortError" ? "Réponse interrompue. Les actions déjà exécutées restent enregistrées." : exc instanceof Error ? exc.message : "La conversation a échoué.");
    } finally { setBusy(false); setStatus(""); abort.current = null; void props.onRefresh(); }
  }
  async function briefing(): Promise<void> {
    setBusy(true); setError("");
    try { await actions.briefing(); setMessages((await actions.chatHistory()).messages || []); }
    catch (exc) { setError(exc instanceof Error ? exc.message : "Briefing indisponible."); }
    finally { setBusy(false); }
  }

  const shown = history ? messages : messages.slice(-2);
  return <section className="dialogue" role="dialog" aria-label="Conversation avec le Desk Manager">
    <div className="dialogue-portrait"><Portrait id="desk_manager" scale={5} /><strong>Desk Manager</strong></div>
    <div className="dialogue-main">
      <div className="dialogue-text" ref={scroll} aria-live="polite">
        {!messages.length && <p className="line assistant">Bonsoir. Que veux-tu faire avancer cette nuit ?</p>}
        {shown.map((message, i) => <p key={i} className={`line ${message.role}`}>{message.role === "user" && <b>Toi : </b>}{message.content || (busy && i === shown.length - 1 ? "…" : "")}</p>)}
        {status && <p className="line status">{status}</p>}
        {error && <p className="line error" role="alert">{error}</p>}
      </div>
      <div className="dialogue-choices">{CHOICES.map(([label, text, intent]) => <button key={label} type="button" disabled={busy} onClick={() => void send(text, intent)}>▸ {label}</button>)}
        <button type="button" disabled={busy} onClick={() => void briefing()}>▸ Briefing du matin</button>
        <button type="button" onClick={() => setHistory(!history)}>{history ? "▾ Replier" : "▴ Historique"}</button></div>
      <form onSubmit={event => { event.preventDefault(); void send(input); }}>
        <input value={input} maxLength={3000} onChange={event => setInput(event.target.value)} placeholder="Écris au Desk Manager…" aria-label="Message au Desk Manager" autoFocus />
        {busy ? <button type="button" className="btn" onClick={() => abort.current?.abort()}>Interrompre</button> : <button type="submit" className="btn primary" disabled={!input.trim()}>Envoyer</button>}
        <button type="button" className="btn" onClick={props.onClose} aria-label="Fermer (Échap)">Fermer</button>
      </form>
    </div>
  </section>;
}
