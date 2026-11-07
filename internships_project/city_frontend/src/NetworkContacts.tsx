import React, {useEffect, useRef, useState} from "react";
import {LinkedInAssisted} from "./LinkedInAssisted";
import {ContactCollectionReport, CollectionReport} from "./ContactCollectionReport";

type Contact = {id:string;name:string;role:string;company:string;location:string;linkedin_url:string;school?:string;school_source_url?:string;school_evidence?:string;source_type?:string;source_date?:string;location_source_url?:string;location_evidence?:string;origin?:string;
  detected_at:string;source_url:string;source_title:string;source_excerpt:string;verification_status:string;employment_status:string;
  contact_segment:"sales"|"secondary"|"outside"|"unclear";sales_priority:boolean;specialty:string;focus_reason:string};
type Schedule = {enabled:boolean;last_day:string;status:string;error:string;report?:CollectionReport};
type Scout = {id?:string;status:string;created_at?:string;finished_at?:string;error?:string;summary?:string;report?:CollectionReport};
type Data = {contacts:Contact[];schedule:Schedule;clara?:Scout};
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
    el?.show();
    el?.querySelector<HTMLInputElement>('input[aria-label="Rechercher un contact"]')?.focus();
    return()=>{el?.close();previous?.focus();};
  },[]);
  return <dialog ref={dialog} className="network-window" aria-labelledby="network-window-title" onCancel={onClose} onKeyDown={e=>{if(e.key==="Escape")onClose();}}
    onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)onClose();}}}>
    <header className="network-window-heading">
      <span className="network-host roster-avatar pixel-agent-avatar networker" aria-hidden="true"><i className="agent-sprite"/></span>
      <div><span className="network-kicker">LINA · CLARA · NETWORK</span><h2 id="network-window-title">Tes contacts</h2><p>Recherche, vérifie et retrouve tes interlocuteurs de marché.</p></div>
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
  const [scope,setScope]=useState<'all'|'lina'|'clara'>('all'),[specialty,setSpecialty]=useState("");
  const [targetQuery,setTargetQuery]=useState("");
  const [view,setView]=useState<'directory'|'collect'|'import'>('directory');
  const [salesOnly,setSalesOnly]=useState(false),[sortBy,setSortBy]=useState<'recent'|'name'>('recent');
  const [selectedId,setSelectedId]=useState(''),[visibleCount,setVisibleCount]=useState(80);
  useEffect(()=>setVisibleCount(80),[query,company,scope,specialty,salesOnly,sortBy]);
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
  useEffect(()=>{let active=true;const update=()=>load().catch(e=>{if(active)setError(e.message);});void update();const timer=setInterval(()=>{if(!document.hidden)void update();},30000);return()=>{active=false;clearInterval(timer);};},[]);
  async function action(payload:object){
    setBusy(true);setError("");
    try{const r=await fetch("/city/api/network",{method:"POST",headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},body:JSON.stringify(payload)});
      if(!r.ok)throw Error("La collecte n’a pas pu être planifiée.");await load();
    }catch(e){setError(e instanceof Error?e.message:"Erreur de collecte.");}finally{setBusy(false);}
  }
  async function runClara(){
    setBusy(true);setError('');
    try{const r=await fetch('/city/api/agents/securities_scout/run',{method:'POST',headers:{'Content-Type':'application/json','X-MarketDesk-City':'1'},body:'{}'});
      if(!r.ok){const response=await r.json().catch(()=>({}));throw Error(response.detail||'La mission de Clara n’a pas pu être lancée.');}
      await load();
    }catch(e){setError(e instanceof Error?e.message:'Mission indisponible.');}finally{setBusy(false);}
  }
  const contacts=data?.contacts||[],schedule=data?.schedule,clara=data?.clara;
  const text=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const linaCount=contacts.filter(c=>c.origin!=='securities_public_search').length;
  const claraCount=contacts.length-linaCount;
  const filtered=contacts.filter(c=>(scope==='all'||(scope==='clara')===(c.origin==='securities_public_search'))&&
    (!salesOnly||c.sales_priority)&&(!specialty||c.specialty===specialty)&&(!company||c.company===company)&&
    text(`${c.name} ${c.role} ${c.company} ${c.location} ${c.school||''} ${c.specialty||''}`).includes(text(query)))
    .sort((a,b)=>sortBy==='name'?displayContactName(a.name).localeCompare(displayContactName(b.name),'fr'):
      b.detected_at.localeCompare(a.detected_at)||a.name.localeCompare(b.name,'fr'));
  const selected=filtered.find(c=>c.id===selectedId)||filtered[0];
  const active=!!schedule&&['queued','running'].includes(schedule.status);
  const claraActive=!!clara&&['queued','running'].includes(clara.status);
  const calendar=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'});
  const today=calendar.format(new Date());
  const newToday=contacts.filter(c=>c.detected_at&&calendar.format(new Date(c.detected_at))===today).length;
  if(!data)return <div className="network-directory"><section className="network-load-state" role={error?'alert':'status'}>
    <span className="network-load-icon" aria-hidden="true">{error?'!':'…'}</span><h3>{error?'Dossier inaccessible':'Connexion à ton dossier…'}</h3>
    <p>{error||'Chargement des contacts de Lina et Clara.'}</p>
    {error&&<div className="network-actions"><button disabled={loading} onClick={()=>{setLoading(true);void load().catch(e=>setError(e instanceof Error?e.message:'Connexion impossible.'));}}>{loading?'Connexion…':'Réessayer'}</button>
      {readStatus===401||readStatus===403?<a className="network-reconnect" href="/login">Se reconnecter</a>:<button onClick={()=>window.location.reload()}>Recharger City</button>}</div>}
  </section></div>;
  return <div className="network-directory network-workspace">
    <nav className="network-workspace-tabs" aria-label="Espaces Contacts">{([['directory','Répertoire',contacts.length],['collect','Lina & Clara',Number(active)+Number(claraActive)],['import','Importer',null]] as const).map(([id,label,count])=><button key={id} type="button" aria-current={view===id?'page':undefined} onClick={()=>setView(id)}>{label}{count!==null&&<span>{count}</span>}</button>)}</nav>
    <div className={`network-workspace-body ${view==='directory'?'directory-open':''}`}>
      {view==='directory'&&<div className="network-directory-view">
        <div className="network-directory-overview"><div><strong>{contacts.length}</strong><span>contacts enregistrés</span><b>+{newToday} aujourd’hui</b></div><small>Lina · {linaCount} &nbsp;·&nbsp; Clara · {claraCount}</small></div>
        <div className="network-directory-controls"><label className="network-search"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/></svg><input aria-label="Rechercher un contact" placeholder="Nom, poste, banque, école…" value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="network-directory-scope" role="group" aria-label="Origine des contacts">{([['all','Tous',contacts.length],['lina','Lina',linaCount],['clara','Clara',claraCount]] as const).map(([id,label,count])=><button type="button" key={id} aria-pressed={scope===id} onClick={()=>setScope(id)}>{label}<span>{count}</span></button>)}</div></div>
        <div className="network-directory-options"><label><input type="checkbox" checked={salesOnly} onChange={e=>setSalesOnly(e.target.checked)}/> Sales uniquement</label><select aria-label="Trier les contacts" value={sortBy} onChange={e=>setSortBy(e.target.value as 'recent'|'name')}><option value="recent">Plus récents</option><option value="name">Nom A–Z</option></select><details className="network-advanced"><summary>Filtres avancés{(company||specialty)?' · actifs':''}</summary><div><select aria-label="Spécialité" value={specialty} onChange={e=>setSpecialty(e.target.value)}><option value="">Toutes les spécialités</option>{[...new Set(contacts.map(c=>c.specialty).filter(Boolean))].sort().map(s=><option key={s}>{s}</option>)}</select><select aria-label="Entreprise" value={company} onChange={e=>setCompany(e.target.value)}><option value="">Toutes les entreprises</option>{[...new Set(contacts.map(c=>c.company).filter(Boolean))].sort().map(c=><option key={c}>{c}</option>)}</select></div></details>{(query||company||specialty||scope!=='all'||salesOnly||sortBy!=='recent')&&<button type="button" onClick={()=>{setQuery('');setCompany('');setSpecialty('');setScope('all');setSalesOnly(false);setSortBy('recent');}}>Effacer les filtres</button>}</div>
        <div className="network-results-layout"><div className="network-contact-list" role="listbox" aria-label="Contacts filtrés"><div className="network-contact-list-title">{filtered.length} résultat{filtered.length===1?'':'s'}</div>{!filtered.length?<div className="network-empty"><p>{contacts.length?"Aucun contact ne correspond aux filtres. Les fiches enregistrées sont conservées.":"Ton répertoire est vide. Consulte les bilans de Lina et Clara pour comprendre la dernière collecte."}</p><button type="button" onClick={()=>setView("collect")}>Voir les bilans et cibler une recherche</button></div>:filtered.slice(0,visibleCount).map(c=><button type="button" role="option" aria-selected={selected?.id===c.id} className="network-list-row" key={c.id} onClick={()=>setSelectedId(c.id)}><span className="network-initials">{c.name.split(/\s+/).map(w=>w[0]).slice(0,2).join('')}</span><span className="network-list-copy"><strong>{displayContactName(c.name)}</strong><small>{c.role||'Poste à confirmer'}</small><em>{c.company||'Entreprise à confirmer'}{c.location?` · ${c.location}`:''}</em></span>{c.sales_priority&&<i title="Sales prioritaire">S</i>}</button>)}{filtered.length>visibleCount&&<button type="button" className="network-load-more" onClick={()=>setVisibleCount(n=>n+80)}>Afficher 80 contacts de plus</button>}</div>
          <div className="network-contact-detail">{selected?<article key={selected.id}><div className="network-detail-head"><span className="network-initials">{selected.name.split(/\s+/).map(w=>w[0]).slice(0,2).join('')}</span><div><span className="network-kicker">{selected.origin==='securities_public_search'?'CONTACT DE CLARA':'CONTACT DE LINA'}</span><h3>{displayContactName(selected.name)}</h3><p>{selected.role||'Poste à confirmer'}</p></div></div><div className="network-detail-tags"><span className={`network-specialty ${selected.sales_priority?'sales':'secondary'}`}>{selected.specialty||'Finance de marché'}</span><span className="network-badge">{selected.verification_status||'À vérifier'}</span></div><div className="network-detail-facts"><div><small>Entreprise</small><strong>{selected.company||'À confirmer'}</strong></div><div><small>Localisation</small><strong>{selected.location||'À confirmer'}</strong></div><div><small>École / université</small><strong>{selected.school||'Non renseignée'}</strong></div><div><small>Détecté</small><strong>{selected.detected_at?new Date(selected.detected_at).toLocaleDateString('fr-FR'):'Date inconnue'}</strong></div></div><div className="network-detail-links">{safeLink(selected.linkedin_url)&&<a href={safeLink(selected.linkedin_url)} target="_blank" rel="noopener noreferrer">Profil LinkedIn ↗</a>}{safeSource(selected.source_url)&&<a href={safeSource(selected.source_url)} target="_blank" rel="noopener noreferrer">Source publique ↗</a>}</div>{selected.focus_reason&&<section><h4>Pourquoi ce contact</h4><p>{selected.focus_reason}</p></section>}<details open><summary>Sources et vérification</summary><p>{selected.employment_status||'Poste actuel à confirmer.'}</p><p>{selected.source_title||selected.source_type||'Source non précisée'}</p>{!safeSource(selected.source_url)&&<p>Aucun lien public vérifiable enregistré pour cette fiche. Vérifie l’extrait avant toute prise de contact.</p>}<p>{selected.source_excerpt||selected.source_title||'Source non précisée.'}</p>{selected.source_date&&<small>Publication : {selected.source_date}</small>}{selected.school&&<p><strong>Formation :</strong> {selected.school_evidence||'Mention publique à confirmer.'} {safeSource(selected.school_source_url||'')&&<a href={safeSource(selected.school_source_url||'')} target="_blank" rel="noopener noreferrer">Source ↗</a>}</p>}{safeSource(selected.location_source_url||'')&&<p><strong>Lieu :</strong> {selected.location_evidence} <a href={safeSource(selected.location_source_url||'')} target="_blank" rel="noopener noreferrer">Source ↗</a></p>}</details><small className="network-detail-footnote">Informations professionnelles publiques à vérifier avant prise de contact.</small></article>:<div className="network-empty">Sélectionne un contact dans la liste.</div>}</div></div>
      </div>}
      {view==='collect'&&<div className="network-collect-view"><div className="network-section-intro"><h3>Lancer une recherche</h3><p>Lina cherche des contacts en finance de marché. Clara explore les services titres et les équipes moins visibles.</p></div>{error&&<p role="alert" className="network-warning">{error}</p>}<div className="network-agent-grid"><section className="network-agent-card"><div className="network-agent-heading"><span className="roster-avatar pixel-agent-avatar networker" aria-hidden="true"><i className="agent-sprite"/></span><div><span className="network-kicker">FINANCE DE MARCHÉ</span><h4>Lina</h4></div></div><p>Sales en priorité, puis métiers de marché proches. Recherche manuelle à tout moment.</p><span className={`network-collection-state ${active?'running':schedule?.enabled?'enabled':'paused'}`}><i/>{active?'Recherche en cours':schedule?.enabled?'Collecte quotidienne active':'Collecte quotidienne suspendue'}</span><div className="network-agent-actions"><button className="network-primary" disabled={busy||active} onClick={()=>void action({collect:true})}>Rechercher maintenant</button><button disabled={busy} onClick={()=>void action({enabled:!schedule?.enabled})}>{schedule?.enabled?'Suspendre le quotidien':'Activer le quotidien'}</button><button disabled={busy||active||!contacts.some(c=>!c.school)} onClick={()=>void action({enrich_schools:true})}>Compléter les écoles</button></div><ContactCollectionReport report={schedule?.report}/>{schedule?.error&&<p className="network-warning">{schedule.error}</p>}</section><section className="network-agent-card"><div className="network-agent-heading"><span className="roster-avatar pixel-agent-avatar securities_scout" aria-hidden="true"><i className="agent-sprite"/></span><div><span className="network-kicker">SERVICES TITRES</span><h4>Clara</h4></div></div><p>Collateral, repo, securities lending, FX et trésorerie chez les dépositaires et banques spécialisées.</p><span className={`network-collection-state ${claraActive?'running':clara?.status==='completed'?'enabled':'paused'}`}><i/>{claraActive?'Recherche en cours':clara?.status==='completed'?'Dernière recherche terminée':clara?.status==='failed'?'Dernière recherche en échec':'Prête pour une recherche'}</span><div className="network-agent-actions"><button className="network-primary" disabled={busy||claraActive} onClick={()=>void runClara()}>Lancer Clara</button></div><ContactCollectionReport report={clara?.report||{text:clara?.summary}}/>{clara?.error&&<p className="network-warning">{clara.error}</p>}</section></div><section className="network-targeted-search"><h4>Préparer une recherche ciblée</h4><p>Précise un métier, une banque ou un lieu. La recherche s’ouvre sur LinkedIn ; tu choisis ensuite les profils à importer.</p><form onSubmit={e=>{e.preventDefault();setTargetQuery([query,company,specialty].filter(Boolean).join(" ").slice(0,250)||"FX Sales Paris");setView("import");}}><label>Critères de recherche<input maxLength={250} value={query} onChange={e=>setQuery(e.target.value)} placeholder="FX Sales CACEIS Paris"/></label><button type="submit">Préparer dans l’import assisté</button></form></section></div>}
      {view==='import'&&<div className="network-import-view"><div className="network-section-intro"><h3>Importer depuis LinkedIn</h3><p>Copie des résultats, vérifie l’aperçu, puis ajoute seulement les profils utiles.</p></div><LinkedInAssisted key={targetQuery} initialQuery={targetQuery} expanded onImported={load}/></div>}
    </div>
  </div>;
}
