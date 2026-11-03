import React, {useEffect, useRef, useState} from "react";
import {LinkedInAssisted} from "./LinkedInAssisted";

type Contact = {id:string;name:string;role:string;company:string;location:string;linkedin_url:string;school?:string;school_source_url?:string;school_evidence?:string;source_type?:string;source_date?:string;location_source_url?:string;location_evidence?:string;
  detected_at:string;source_url:string;source_title:string;source_excerpt:string;verification_status:string;employment_status:string;
  contact_segment:"sales"|"secondary"|"outside"|"unclear";sales_priority:boolean;specialty:string;focus_reason:string};
type Schedule = {enabled:boolean;last_day:string;status:string;error:string;report?:{count?:number;duplicates?:number;text?:string;warnings?:string[]}};
type Data = {contacts:Contact[];schedule:Schedule};
const safeLink=(url:string)=>/^https:\/\/(?:www\.)?linkedin\.com\/in\/[^/?#]+\/?$/.test(url)?url:undefined;
const safeSource=(url:string)=>{try{const u=new URL(url);return u.protocol==="https:"&&!u.username&&!u.password?url:undefined;}catch{return undefined;}};

function displayContactName(value:string):string{
  const [name,...suffix]=value.trim().replace(/\s+/g," ").split(",");
  const formatted=name.replace(/\p{L}+/gu,word=>word.length>2&&word===word.toLocaleUpperCase("fr")&&!/^(CFA|FRM|CAIA|CQF|MBA)$/.test(word)?word[0]+word.slice(1).toLocaleLowerCase("fr"):word);
  return [formatted,...suffix.map(s=>s.trim())].join(", ");
}

export function NetworkContactsWindow({onClose}:{onClose:()=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    const el=dialog.current,previous=document.activeElement as HTMLElement|null;
    el?.showModal();
    el?.querySelector<HTMLInputElement>('input[aria-label="Rechercher un contact"]')?.focus();
    return()=>{el?.close();previous?.focus();};
  },[]);
  return <dialog ref={dialog} className="network-window" aria-labelledby="network-window-title" onCancel={onClose}
    onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}}>
    <header className="network-window-heading">
      <span className="network-host roster-avatar pixel-agent-avatar networker" aria-hidden="true"><i className="agent-sprite"/></span>
      <div><span className="network-kicker">Lina · Network</span><h2 id="network-window-title">Contacts</h2><p>Ton réseau en finance de marché · Sales et métiers proches · Paris.</p></div>
      <button className="network-close" type="button" onClick={onClose} aria-label="Fermer les contacts">×</button>
    </header>
    <NetworkContacts/>
    <footer className="network-window-footer"><span><i/> Dossier privé de ton compte</span><span>Sources publiques · Informations à confirmer</span></footer>
  </dialog>;
}

export function NetworkContacts(){
  const [data,setData]=useState<Data|null>(null), [error,setError]=useState(""), [busy,setBusy]=useState(false);
  const [readStatus,setReadStatus]=useState(0),[loading,setLoading]=useState(true);
  const [query,setQuery]=useState(""),[company,setCompany]=useState("");
  const [segment,setSegment]=useState("all"),[specialty,setSpecialty]=useState("");
  const [visibleCount,setVisibleCount]=useState(50);
  useEffect(()=>setVisibleCount(50),[query,company,segment,specialty]);
  async function load(){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{
      const r=await fetch("/city/api/network",{cache:"no-store",signal:controller.signal});
      setReadStatus(r.status);
      if(!r.ok){
        if(r.status===404)throw Error("Ce serveur utilise une ancienne version : la route Contacts n’existe pas encore (HTTP 404). Redémarre MarketDesk City, puis recharge la page.");
        if(r.status===401||r.status===403)throw Error("Ta session a expiré ou l’accès est refusé. Reconnecte-toi pour retrouver ton dossier.");
        throw Error(`Le dossier Network est temporairement indisponible (HTTP ${r.status}). Réessaie dans un instant.`);
      }
      const payload=await r.json();
      if(!Array.isArray(payload.contacts)||typeof payload.schedule?.enabled!=="boolean")throw Error("Le serveur a renvoyé une réponse incompatible. Redémarre MarketDesk City et recharge la page.");
      setData(payload);setError("");setReadStatus(0);
    }catch(e){
      if(e instanceof Error&&e.name==="AbortError")throw Error("Le serveur met trop de temps à répondre. Réessaie dans un instant.");
      throw e;
    }finally{clearTimeout(timer);setLoading(false);}
  }
  useEffect(()=>{let active=true;const update=()=>load().catch(e=>{if(active)setError(e.message);});void update();const timer=setInterval(update,10000);return()=>{active=false;clearInterval(timer);};},[]);
  async function action(payload:object){
    setBusy(true);setError("");
    try{const r=await fetch("/city/api/network",{method:"POST",headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},body:JSON.stringify(payload)});
      if(!r.ok)throw Error("La collecte n’a pas pu être planifiée.");await load();
    }catch(e){setError(e instanceof Error?e.message:"Erreur de collecte.");}finally{setBusy(false);}
  }
  const contacts=data?.contacts||[],schedule=data?.schedule;
  const text=(s:string)=>s.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
  const salesCount=contacts.filter(c=>c.sales_priority).length;
  const filtered=contacts.filter(c=>(segment==="all"||(segment==="sales"?c.sales_priority:!c.sales_priority))&&(!specialty||c.specialty===specialty)&&(!company||c.company===company)&&text(`${c.name} ${c.role} ${c.company} ${c.location} ${c.school||""} ${c.specialty||""}`).includes(text(query)));
  const active=schedule&&["queued","running"].includes(schedule.status);
  const calendar=new Intl.DateTimeFormat("en-CA",{timeZone:"Europe/Paris",year:"numeric",month:"2-digit",day:"2-digit"});
  const today=calendar.format(new Date());
  const newToday=contacts.filter(c=>c.detected_at&&calendar.format(new Date(c.detected_at))===today).length;
  if(!data)return <div className="network-directory"><section className="network-load-state" role={error?"alert":"status"}>
    <span className="network-load-icon" aria-hidden="true">{error?"!":"…"}</span><h3>{error?"Dossier inaccessible":"Connexion à ton dossier…"}</h3>
    <p>{error||"Chargement des contacts et de la planification de Lina."}</p>
    {error&&<div className="network-actions"><button disabled={loading} onClick={()=>{setLoading(true);void load().catch(e=>setError(e instanceof Error?e.message:"Connexion au serveur impossible."));}}>{loading?"Connexion…":"Réessayer"}</button>
      {readStatus===401||readStatus===403?<a className="network-reconnect" href="/login">Se reconnecter</a>:<button onClick={()=>window.location.reload()}>Recharger MarketDesk</button>}
    </div>}
  </section></div>;
  return <div className="network-directory">
    <LinkedInAssisted onImported={load}/>
    <div className="network-summary"><div className="network-stats"><span><b>{salesCount}</b> Sales prioritaires</span><span className="network-today">+{newToday} aujourd’hui</span></div><span className={`network-collection-state ${active?"running":schedule?.enabled?"enabled":"paused"}`}><i/>{active?"Collecte en cours":schedule?.enabled?"Collecte quotidienne active":"Collecte suspendue"}</span></div>
    <details className="network-schedule"><summary><span>Collecte et dernier bilan<small>Objectif : 10 nouveaux contacts par jour, Sales en priorité puis métiers proches en finance de marché.</small></span><span className="network-details-chevron" aria-hidden="true">⌄</span></summary>
      <div className="network-schedule-body"><p>Collecte automatique une fois par jour, heure de Paris, tant que le serveur fonctionne. Tu peux aussi lancer une recherche à tout moment, même si la collecte automatique est suspendue. GPT‑5.4 mini + recherche Web, coût suivi dans les réglages IA.</p>
        <div className="network-actions"><button disabled={busy||!schedule} onClick={()=>void action({enabled:!schedule?.enabled})}>{schedule?.enabled?"Suspendre":"Activer"}</button>
        <button className="network-primary" disabled={busy||!schedule||!!active} onClick={()=>void action({collect:true})}>Rechercher maintenant</button></div>
        <div className="network-actions"><button disabled={busy||!schedule||!!active||!contacts.some(c=>!c.school)} onClick={()=>void action({enrich_schools:true})}>Rechercher les écoles</button><small>5 contacts par lot · sources publiques · coût suivi dans les réglages IA.</small></div>
        {schedule?.last_day&&<small>Dernière tentative : {schedule.last_day} · {schedule.status==="failed"?"Échec":schedule.status==="completed"?"Terminée":active?"En cours":"Planifiée"}</small>}
        {schedule?.report?.text&&<p>{schedule.report.text}</p>}{!!schedule?.report?.warnings?.length&&<p className="network-warning">Certaines recherches ont échoué : {schedule.report.warnings.join(" · ")}</p>}
      </div>
    </details>
    {schedule?.error&&<p className="network-warning" role="status">{schedule.error}</p>}
    {error&&<p role="alert" className="network-warning">{error}</p>}
    <div className="network-toolbar">
      <div className="network-segments" role="group" aria-label="Ciblage des contacts">{[["sales","Sales prioritaires",salesCount],["all","Tous les contacts",contacts.length],["other","Autres métiers",contacts.length-salesCount]].map(([id,label,count])=><button type="button" key={id} aria-pressed={segment===id} onClick={()=>{setSegment(String(id));setSpecialty("");}}>{label}<span>{count}</span></button>)}</div>
      <div className="network-filters"><label className="network-search"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/></svg><input aria-label="Rechercher un contact" placeholder="Nom, poste, entreprise…" value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label="Spécialité" value={specialty} onChange={e=>setSpecialty(e.target.value)}><option value="">Toutes les spécialités</option>{[...new Set(contacts.map(c=>c.specialty).filter(Boolean))].sort().map(s=><option key={s}>{s}</option>)}</select><select aria-label="Entreprise" value={company} onChange={e=>setCompany(e.target.value)}><option value="">Toutes les entreprises</option>{[...new Set(contacts.map(c=>c.company).filter(Boolean))].sort().map(c=><option key={c}>{c}</option>)}</select></div>
      <div className="network-result-count"><span>{filtered.length} contact{filtered.length===1?"":"s"} affiché{filtered.length===1?"":"s"} sur {contacts.length}</span>{(query||company||specialty||segment!=="sales")&&<button onClick={()=>{setQuery("");setCompany("");setSpecialty("");setSegment("sales");}}>Réinitialiser</button>}</div>
    </div>
    {!data&&!error&&<p>Chargement du dossier…</p>}
    {data&&!filtered.length&&<div className="network-empty">{contacts.length?(segment==="sales"&&!salesCount?"Ton dossier ne contient pas encore de Sales ciblé. Les prochaines collectes privilégieront ce métier.":"Aucun contact ne correspond à tes filtres."):"Lina recherche en priorité des Sales à Paris : Fixed Income, Rates, Credit, FX, Equities et produits structurés."}{!!contacts.length&&segment==="sales"&&!salesCount&&<p><button onClick={()=>setSegment("all")}>Voir tous les contacts</button></p>}</div>}
    <div className="network-contact-grid">{filtered.sort((a,b)=>Number(b.sales_priority)-Number(a.sales_priority)||Number(a.specialty==="Sales & Trading")-Number(b.specialty==="Sales & Trading")||b.detected_at.localeCompare(a.detected_at)||a.id.localeCompare(b.id)).slice(0,visibleCount).map(c=><article className="network-contact" key={c.id}>
      <div className="network-contact-head"><span className="network-initials">{c.name.split(/\s+/).map(w=>w[0]).slice(0,2).join("")}</span><div><h4 title={c.name}>{displayContactName(c.name)}</h4><div className="network-contact-meta"><strong>{c.company||"Entreprise à confirmer"}</strong><span>{c.location||"Lieu à confirmer"}</span></div></div></div>
      <p className="network-contact-role" title={c.role}>{c.role||"Poste à confirmer"}</p>
      <p><small>{c.source_type||"Source publique"}{c.source_date?` · Publication : ${c.source_date}`:""}</small></p>
      {safeSource(c.location_source_url||"")&&<details><summary>Source de la localisation</summary><p>{c.location_evidence}</p><a href={safeSource(c.location_source_url||"")} target="_blank" rel="noopener noreferrer">Vérifier la localisation ↗</a></details>}
      <p><strong>École / université :</strong> {c.school||"Non renseignée"}</p>
      {c.school&&<details><summary>Source de la formation</summary><p>{c.school_evidence}</p>{safeSource(c.school_source_url||"")&&<a href={safeSource(c.school_source_url||"")} target="_blank" rel="noopener noreferrer">Consulter la source ↗</a>}<small>Formation mentionnée publiquement ; diplôme non confirmé.</small></details>}
      <footer><span className={`network-specialty ${c.sales_priority?"sales":"secondary"}`} title={c.focus_reason}>{c.sales_priority&&!c.specialty?.startsWith("Sales")?"Sales · ":""}{c.specialty||"Périmètre à préciser"}</span><span className="network-badge">{c.verification_status||"À vérifier"}</span>{safeLink(c.linkedin_url)||safeSource(c.source_url)?<a href={safeLink(c.linkedin_url)||safeSource(c.source_url)} target="_blank" rel="noopener noreferrer">{safeLink(c.linkedin_url)?"Profil LinkedIn ↗":"Source publique ↗"}</a>:<span>Copie LinkedIn · lien absent</span>}</footer>
      <details><summary>Source et détails</summary><p><strong>Poste :</strong> {c.role||"À confirmer"}</p><p>{c.employment_status}</p><p className="network-targeting-note">{c.focus_reason}</p><p>{c.source_excerpt||c.source_title}</p>{safeSource(c.source_url)&&<a href={safeSource(c.source_url)} target="_blank" rel="noopener noreferrer">Consulter la source du contact</a>}<small>Détecté le {new Date(c.detected_at).toLocaleDateString("fr-FR")} · {c.source_type==='Sélection LinkedIn'||c.source_type==='Copie LinkedIn'?'Informations sélectionnées manuellement, poste à confirmer.':'Extrait indexé, poste actuel à confirmer.'} Fiche également disponible dans Internships → Mail.</small></details>
    </article>)}</div>
    {filtered.length>visibleCount&&<button onClick={()=>setVisibleCount(v=>v+50)}>Afficher 50 contacts de plus</button>}
  </div>;
}
