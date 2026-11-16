import React, {useEffect, useRef, useState} from "react";
import {LinkedInAssisted} from "./LinkedInAssisted";
import {ContactCollectionReport, CollectionReport} from "./ContactCollectionReport";
import {OutreachTracker, OutreachRecord, followUpDue} from "./OutreachTracker";

type Contact = {id:string;name:string;role:string;company:string;location:string;linkedin_url:string;email?:string;school?:string;school_source_url?:string;school_evidence?:string;source_type?:string;source_date?:string;location_source_url?:string;location_evidence?:string;origin?:string;
  detected_at:string;source_url:string;source_title:string;source_excerpt:string;verification_status:string;employment_status:string;
  contact_segment:"sales"|"secondary"|"outside"|"unclear";sales_priority:boolean;specialty:string;focus_reason:string};
type Schedule = {enabled:boolean;last_day:string;status:string;error:string;report?:CollectionReport};
type Scout = {id?:string;status:string;created_at?:string;finished_at?:string;error?:string;summary?:string;report?:CollectionReport};
type Data = {contacts:Contact[];schedule:Schedule;clara?:Scout;prime_services?:Scout;outreach?:OutreachRecord[]};
const safeLink=(url:string)=>/^https:\/\/(?:www\.)?linkedin\.com\/in\/[^/?#]+\/?$/.test(url)?url:undefined;
const safeSource=(url:string)=>{try{const u=new URL(url);return u.protocol==="https:"&&!u.username&&!u.password?url:undefined;}catch{return undefined;}};

function displayContactName(value:string):string{
  const [name,...suffix]=value.trim().replace(/\s+/g," ").split(",");
  const formatted=name.replace(/\p{L}+/gu,word=>word.length>2&&word===word.toLocaleUpperCase("fr")&&!/^(CFA|FRM|CAIA|CQF|MBA)$/.test(word)?word[0]+word.slice(1).toLocaleLowerCase("fr"):word);
  return [formatted,...suffix.map(s=>s.trim())].join(", ");
}

export function NetworkContactsWindow({onClose,onIrisAction,irisStatus}:{onClose:()=>void;onIrisAction:(name:string,action:'message'|'history')=>void;irisStatus:string}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [dirty,setDirty]=useState(false);
  const close=()=>{if(!dirty||window.confirm('Un message contient des modifications non enregistrées. Fermer quand même ?'))onClose();};
  useEffect(()=>{
    const el=dialog.current,previous=document.activeElement as HTMLElement|null;
    el?.show();
    el?.querySelector<HTMLInputElement>('input[aria-label="Rechercher un contact"]')?.focus();
    return()=>{el?.close();previous?.focus();};
  },[]);
  return <dialog ref={dialog} className="network-window" aria-labelledby="network-window-title" onCancel={e=>{e.preventDefault();close();}} onKeyDown={e=>{if(e.key==="Escape"){e.preventDefault();e.stopPropagation();close();}}}
    onClick={e=>{if(e.target===e.currentTarget){const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();}}}>
    <header className="network-window-heading">
      <span className="network-host roster-avatar pixel-agent-avatar networker" aria-hidden="true"><i className="agent-sprite"/></span>
      <div><span className="network-kicker">LINA · CLARA · ÉLODIE · CONTACTS</span><h2 id="network-window-title">Tes contacts</h2><p>Recherche, vérifie et retrouve tes interlocuteurs de marché.</p></div>
      <button className="network-close" type="button" onClick={close} aria-label="Fermer les contacts">×</button>
    </header>
    <NetworkContacts onIrisAction={onIrisAction} irisStatus={irisStatus} onDirtyChange={setDirty}/>
    <footer className="network-window-footer"><span><i/> Dossier privé de ton compte</span><span>Sources publiques · Informations à confirmer</span></footer>
  </dialog>;
}

export function NetworkContacts({onIrisAction,irisStatus,onDirtyChange}:{onIrisAction:(name:string,action:'message'|'history')=>void;irisStatus:string;onDirtyChange?:(dirty:boolean)=>void}){
  const [data,setData]=useState<Data|null>(null), [error,setError]=useState(""), [busy,setBusy]=useState(false);
  const [readStatus,setReadStatus]=useState(0),[loading,setLoading]=useState(true);
  const [query,setQuery]=useState(""),[company,setCompany]=useState("");
  const [scope,setScope]=useState<'all'|'lina'|'clara'|'prime'>('all'),[specialty,setSpecialty]=useState("");
  const [sourceType,setSourceType]=useState(""),[verification,setVerification]=useState(""),[detectedRange,setDetectedRange]=useState<'all'|'today'|'week'>('all');
  const [targetQuery,setTargetQuery]=useState("");
  const [view,setView]=useState<'directory'|'collect'|'import'|'outreach'>('directory');
  const [outreachSeedId,setOutreachSeedId]=useState('');
  const [salesOnly,setSalesOnly]=useState(false),[sortBy,setSortBy]=useState<'recent'|'name'>('recent');
  const [selectedId,setSelectedId]=useState(''),[visibleCount,setVisibleCount]=useState(10);
  useEffect(()=>setVisibleCount(10),[query,company,scope,specialty,sourceType,verification,detectedRange,salesOnly,sortBy]);
  const readSequence=useRef(0);
  async function load(){
    const sequence=++readSequence.current;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
    try{
      const r=await fetch("/city/api/network",{cache:"no-store",signal:controller.signal});
      if(sequence!==readSequence.current)return;
      setReadStatus(r.status);
      if(!r.ok){
        if(r.status===404)throw Error("Ce serveur utilise une ancienne version : la route Contacts n’existe pas encore (HTTP 404). Redémarre MarketDesk City, puis recharge la page.");
        if(r.status===401||r.status===403)throw Error("Ta session a expiré ou l’accès est refusé. Reconnecte-toi pour retrouver ton dossier.");
        throw Error(`Le dossier Network est temporairement indisponible (HTTP ${r.status}). Réessaie dans un instant.`);
      }
      const payload=await r.json();
      if(!Array.isArray(payload.contacts)||typeof payload.schedule?.enabled!=="boolean")throw Error("Le serveur a renvoyé une réponse incompatible. Redémarre MarketDesk City et recharge la page.");
      if(!Array.isArray(payload.outreach))payload.outreach=[];
      if(sequence!==readSequence.current)return;
      setData(payload);setError("");setReadStatus(0);
    }catch(e){
      if(sequence!==readSequence.current)return;
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
  async function runPrimeServices(){
    setBusy(true);setError('');
    try{const r=await fetch('/city/api/agents/prime_services_scout/run',{method:'POST',headers:{'Content-Type':'application/json','X-MarketDesk-City':'1'},body:'{}'});
      if(!r.ok){const response=await r.json().catch(()=>({}));throw Error(response.detail||'La mission d’Élodie n’a pas pu être lancée.');}
      await load();
    }catch(e){setError(e instanceof Error?e.message:'Mission indisponible.');}finally{setBusy(false);}
  }
  const contacts=data?.contacts||[],schedule=data?.schedule,clara=data?.clara,prime=data?.prime_services;
  const text=(s:string)=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const linaCount=contacts.filter(c=>!['securities_public_search','prime_services_public_search'].includes(c.origin||'')).length;
  const claraCount=contacts.filter(c=>c.origin==='securities_public_search').length;
  const primeCount=contacts.filter(c=>c.origin==='prime_services_public_search').length;
  const calendar=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'});
  const today=calendar.format(new Date());
  const detectedToday=(value:string)=>Number.isFinite(Date.parse(value))&&calendar.format(new Date(value))===today;
  const filtered=contacts.filter(c=>(scope==='all'||scope==='lina'&&c.origin!=='securities_public_search'&&c.origin!=='prime_services_public_search'||
    scope==='clara'&&c.origin==='securities_public_search'||scope==='prime'&&c.origin==='prime_services_public_search')&&
    (!salesOnly||c.sales_priority)&&(!specialty||c.specialty===specialty)&&(!company||c.company===company)&&
    (!sourceType||c.source_type===sourceType)&&(!verification||c.verification_status===verification)&&
    (detectedRange==='all'||!!c.detected_at&&(detectedRange==='today'?detectedToday(c.detected_at):Date.now()-new Date(c.detected_at).getTime()>=0&&Date.now()-new Date(c.detected_at).getTime()<=7*86400000))&&
    text(`${c.name} ${c.role} ${c.company} ${c.location} ${c.school||''} ${c.specialty||''}`).includes(text(query)))
    .sort((a,b)=>sortBy==='name'?displayContactName(a.name).localeCompare(displayContactName(b.name),'fr'):
      (Number.isFinite(Date.parse(b.detected_at))?b.detected_at:'').localeCompare(Number.isFinite(Date.parse(a.detected_at))?a.detected_at:'')||a.name.localeCompare(b.name,'fr'));
  const selected=filtered.find(c=>c.id===selectedId)||filtered[0];
  const active=!!schedule&&['queued','running'].includes(schedule.status);
  const claraActive=!!clara&&['queued','running'].includes(clara.status);
  const primeActive=!!prime&&['queued','running'].includes(prime.status);
  const newToday=contacts.filter(c=>c.detected_at&&detectedToday(c.detected_at)).length;
  if(!data)return <div className="network-directory"><section className="network-load-state" role={error?'alert':'status'}>
    <span className="network-load-icon" aria-hidden="true">{error?'!':'…'}</span><h3>{error?'Dossier inaccessible':'Connexion à ton dossier…'}</h3>
    <p>{error||'Chargement du répertoire partagé de Lina, Clara et Élodie.'}</p>
    {error&&<div className="network-actions"><button disabled={loading} onClick={()=>{setLoading(true);void load().catch(e=>setError(e instanceof Error?e.message:'Connexion impossible.'));}}>{loading?'Connexion…':'Réessayer'}</button>
      {readStatus===401||readStatus===403?<a className="network-reconnect" href="/login">Se reconnecter</a>:<button onClick={()=>window.location.reload()}>Recharger City</button>}</div>}
  </section></div>;
  return <div className="network-directory network-workspace">
    <section className="contact-metrics dev-metrics" aria-label="Vue d’ensemble des contacts"><div><strong>{contacts.length}</strong><span>contacts enregistrés</span></div><div><strong>{(data.outreach||[]).filter(item=>item.status==='ready').length}</strong><span>messages prêts</span></div><div><strong>{(data.outreach||[]).filter(item=>!!item.sent_at).length}</strong><span>envois déclarés</span></div><div><strong>{(data.outreach||[]).filter(followUpDue).length}</strong><span>relances à faire</span></div></section>
    <nav className="network-workspace-tabs" aria-label="Espaces Contacts">{([['directory','Répertoire',null],['outreach','Messages et suivi',(data.outreach||[]).length],['collect','Ajouter des contacts',null]] as const).map(([id,label,count])=><button key={id} type="button" aria-current={(view==='import'?'collect':view)===id?'page':undefined} onClick={()=>setView(id)}>{label}{count!==null&&<span>{count}</span>}</button>)}</nav>
    <div className={`network-workspace-body ${view==='directory'?'directory-open':''}`}>
      {view==='directory'&&<div className="network-directory-view"><aside className="network-contact-sidebar">
  <p className="network-directory-context">{newToday} nouveau{newToday===1?'':'x'} contact{newToday===1?'':'s'} aujourd’hui · {contacts.filter(c=>c.sales_priority).length} profils Sales prioritaires</p>
  <div className="network-directory-controls"><label className="network-search"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 5 5"/></svg><input aria-label="Rechercher un contact" placeholder="Nom, poste, banque, école…" value={query} onChange={e=>setQuery(e.target.value)}/></label><div className="network-directory-scope" role="group" aria-label="Origine des contacts">{([['all','Tous',contacts.length],['lina','Lina',linaCount],['clara','Clara',claraCount],['prime','Élodie',primeCount]] as const).map(([id,label,count])=><button type="button" key={id} aria-pressed={scope===id} onClick={()=>setScope(id)}>{label}<span>{count}</span></button>)}</div><label className="network-sales-toggle"><input type="checkbox" checked={salesOnly} onChange={e=>setSalesOnly(e.target.checked)}/> Sales uniquement</label>
  <details className="network-advanced"><summary>Filtres avancés{(company||specialty||sourceType||verification||detectedRange!=='all')?' · actifs':''}</summary><div><select aria-label="Spécialité" value={specialty} onChange={e=>setSpecialty(e.target.value)}><option value="">Toutes les spécialités</option>{[...new Set(contacts.map(c=>c.specialty).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select><select aria-label="Entreprise" value={company} onChange={e=>setCompany(e.target.value)}><option value="">Toutes les entreprises</option>{[...new Set(contacts.map(c=>c.company).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select><select aria-label="Source du contact" value={sourceType} onChange={e=>setSourceType(e.target.value)}><option value="">Toutes les sources</option>{[...new Set(contacts.map(c=>c.source_type).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select><select aria-label="Statut de vérification" value={verification} onChange={e=>setVerification(e.target.value)}><option value="">Tous les statuts</option>{[...new Set(contacts.map(c=>c.verification_status).filter(Boolean))].sort().map(x=><option key={x}>{x}</option>)}</select><select aria-label="Date de détection" value={detectedRange} onChange={e=>setDetectedRange(e.target.value as 'all'|'today'|'week')}><option value="all">Toutes les dates</option><option value="today">Aujourd’hui</option><option value="week">7 derniers jours</option></select><select aria-label="Trier les contacts" value={sortBy} onChange={e=>setSortBy(e.target.value as 'recent'|'name')}><option value="recent">Plus récents</option><option value="name">Nom A–Z</option></select></div></details>
  {(query||company||specialty||sourceType||verification||detectedRange!=='all'||scope!=='all'||salesOnly||sortBy!=='recent')&&<button type="button" className="network-clear-filters" onClick={()=>{setQuery('');setCompany('');setSpecialty('');setSourceType('');setVerification('');setDetectedRange('all');setScope('all');setSalesOnly(false);setSortBy('recent');}}>Effacer les filtres</button>}</div>
</aside><div className="network-results-layout"><div className="network-contact-list" role="listbox" aria-label="Contacts filtrés"><div className="network-contact-list-title">{filtered.length} résultat{filtered.length===1?'':'s'}</div>{!filtered.length?<div className="network-empty"><p>{contacts.length?"Aucun contact ne correspond aux filtres. Les fiches enregistrées sont conservées.":"Ton répertoire est vide. Consulte les bilans de Lina et Clara pour comprendre la dernière collecte."}</p><button type="button" onClick={()=>setView("collect")}>Voir les bilans et cibler une recherche</button></div>:filtered.slice(0,visibleCount).map(c=><button type="button" role="option" aria-selected={selected?.id===c.id} className="network-list-row" key={c.id} onClick={()=>setSelectedId(c.id)}><span className="network-initials">{c.name.split(/\s+/).map(w=>w[0]).slice(0,2).join('')}</span><span className="network-list-copy"><strong>{displayContactName(c.name)}</strong><small>{c.role||'Poste à confirmer'}</small><em>{c.company||'Entreprise à confirmer'}{c.location?` · ${c.location}`:''}</em></span>{c.sales_priority&&<i title="Sales prioritaire">S</i>}</button>)}{filtered.length>visibleCount&&<button type="button" className="network-load-more" onClick={()=>setVisibleCount(filtered.length)}>Afficher tous les contacts filtrés</button>}</div>
          <div className="network-contact-detail">{selected?<article key={selected.id}><div className="network-detail-head"><span className="network-initials">{selected.name.split(/\s+/).map(w=>w[0]).slice(0,2).join('')}</span><div><span className="network-kicker">{selected.origin==='prime_services_public_search'?'CONTACT ELODIE':selected.origin==='securities_public_search'?'CONTACT DE CLARA':'CONTACT DE LINA'}</span><h3>{displayContactName(selected.name)}</h3><p>{selected.role||'Poste à confirmer'}</p></div></div><div className="network-detail-tags"><span className={`network-specialty ${selected.sales_priority?'sales':'secondary'}`}>{selected.specialty||'Finance de marché'}</span><span className="network-badge">{selected.verification_status||'À vérifier'}</span></div><div className="network-detail-facts"><div><small>Entreprise</small><strong>{selected.company||'À confirmer'}</strong></div><div><small>Localisation</small><strong>{selected.location||'À confirmer'}</strong></div><div><small>École / université</small><strong>{selected.school||'Non renseignée'}</strong></div><div><small>Détecté</small><strong>{Number.isFinite(Date.parse(selected.detected_at))?new Date(selected.detected_at).toLocaleDateString('fr-FR',{timeZone:'Europe/Paris'}):'Date inconnue'}</strong></div></div><div className="network-detail-links">{safeLink(selected.linkedin_url)&&<a href={safeLink(selected.linkedin_url)} target="_blank" rel="noopener noreferrer">Profil LinkedIn ↗</a>}{safeSource(selected.source_url)&&<a href={safeSource(selected.source_url)} target="_blank" rel="noopener noreferrer">Source publique ↗</a>}</div><div className="network-contact-actions"><button type="button" className="network-primary" onClick={()=>{setOutreachSeedId(selected.id);setView('outreach');}}>Messages et suivi</button><button type="button" disabled={!safeSource(selected.source_url)} onClick={()=>{const url=safeSource(selected.source_url);if(url)window.open(url,'_blank','noopener,noreferrer');}}>Vérifier la source</button><button type="button" onClick={()=>onIrisAction(displayContactName(selected.name),'message')}>Préparer un message avec Iris</button><button type="button" onClick={()=>onIrisAction(displayContactName(selected.name),'history')}>Demander l’historique à Iris</button></div>{selected.focus_reason&&<section><h4>Pourquoi ce contact</h4><p>{selected.focus_reason}</p></section>}<details><summary>Sources et vérification</summary><p>{selected.employment_status||'Poste actuel à confirmer.'}</p><p>{selected.source_title||selected.source_type||'Source non précisée'}</p>{!safeSource(selected.source_url)&&<p>Aucun lien public vérifiable enregistré pour cette fiche. Vérifie l’extrait avant toute prise de contact.</p>}<p>{selected.source_excerpt||selected.source_title||'Source non précisée.'}</p>{selected.source_date&&<small>Publication : {selected.source_date}</small>}{selected.school&&<p><strong>Formation :</strong> {selected.school_evidence||'Mention publique à confirmer.'} {safeSource(selected.school_source_url||'')&&<a href={safeSource(selected.school_source_url||'')} target="_blank" rel="noopener noreferrer">Source ↗</a>}</p>}{safeSource(selected.location_source_url||'')&&<p><strong>Lieu :</strong> {selected.location_evidence} <a href={safeSource(selected.location_source_url||'')} target="_blank" rel="noopener noreferrer">Source ↗</a></p>}</details><small className="network-detail-footnote">Informations professionnelles publiques à vérifier avant prise de contact.</small></article>:<div className="network-empty">Sélectionne un contact dans la liste.</div>}</div></div>
      </div>}
      {view==='collect'&&<div className="network-collect-view"><div className="network-section-intro"><button type="button" className="network-primary" onClick={()=>setView('import')}>Importer des profils</button><h3>Lancer une recherche</h3><p>Lina couvre les métiers de marché, Clara les services titres, et Élodie Prime Services, Clearing et financement de titres.</p></div>{error&&<p role="alert" className="network-warning">{error}</p>}<div className="network-agent-grid"><section className="network-agent-card"><div className="network-agent-heading"><span className="roster-avatar pixel-agent-avatar networker" aria-hidden="true"><i className="agent-sprite"/></span><div><span className="network-kicker">FINANCE DE MARCHÉ</span><h4>Lina</h4></div></div><p>Sales en priorité, puis métiers de marché proches. Recherche manuelle à tout moment.</p><span className={`network-collection-state ${active?'running':schedule?.status==='completed'?'enabled':'paused'}`}><i/>{schedule?.status==='queued'?'Recherche en attente':schedule?.status==='running'?'Recherche en cours':schedule?.status==='failed'?'Dernière recherche en échec':schedule?.status==='completed'?'Dernière recherche terminée':'Prête pour une recherche'}</span><small>{schedule?.enabled?"Recherche quotidienne activée":"Recherche quotidienne suspendue"}</small><div className="network-agent-actions"><button className="network-primary" disabled={busy||active} onClick={()=>void action({collect:true})}>Rechercher maintenant</button><button disabled={busy} onClick={()=>void action({enabled:!schedule?.enabled})}>{schedule?.enabled?'Suspendre le quotidien':'Activer le quotidien'}</button><button disabled={busy||active||!contacts.some(c=>!c.school)} onClick={()=>void action({enrich_schools:true})}>Compléter les écoles</button></div><details className="network-report-disclosure"><summary>Dernier bilan de Lina</summary><ContactCollectionReport report={schedule?.report}/></details>{schedule?.error&&<p className="network-warning">{schedule.error}</p>}</section><section className="network-agent-card"><div className="network-agent-heading"><span className="roster-avatar pixel-agent-avatar securities_scout" aria-hidden="true"><i className="agent-sprite"/></span><div><span className="network-kicker">SERVICES TITRES</span><h4>Clara</h4></div></div><p>Collateral, repo, securities lending, FX et trésorerie chez les dépositaires et banques spécialisées.</p><span className={`network-collection-state ${claraActive?'running':clara?.status==='completed'?'enabled':'paused'}`}><i/>{clara?.status==='queued'?'Recherche en attente':claraActive?'Recherche en cours':clara?.status==='completed'?'Dernière recherche terminée':clara?.status==='failed'?'Dernière recherche en échec':'Prête pour une recherche'}</span><div className="network-agent-actions"><button className="network-primary" disabled={busy||claraActive} onClick={()=>void runClara()}>Lancer Clara</button></div><details className="network-report-disclosure"><summary>Dernier bilan de Clara</summary><ContactCollectionReport report={clara?.report||{text:clara?.summary}}/></details>{clara?.error&&<p className="network-warning">{clara.error}</p>}</section><section className="network-agent-card"><div className="network-agent-heading"><span className="roster-avatar pixel-agent-avatar prime_services_scout" aria-hidden="true"><i className="agent-sprite"/></span><div><span className="network-kicker">PRIME SERVICES · CLEARING</span><h4>Élodie</h4></div></div><p>Sales, Sales Traders et Relationship Managers à Paris dans les banques françaises.</p><span className={`network-collection-state ${primeActive?'running':prime?.status==='completed'?'enabled':'paused'}`}><i/>{prime?.status==='queued'?'Recherche en attente':primeActive?'Recherche en cours':'Recherche automatique à 9 h et 17 h'}</span><div className="network-agent-actions"><button className="network-primary" disabled={busy||primeActive} onClick={()=>void runPrimeServices()}>Lancer une recherche</button></div><details className="network-report-disclosure"><summary>Dernier bilan d'Elodie</summary><ContactCollectionReport report={prime?.report||{text:prime?.summary}}/></details>{prime?.error&&<p className="network-warning">{prime.error}</p>}</section></div><section className="network-targeted-search"><h4>Préparer une recherche ciblée</h4><p>Précise un métier, une banque ou un lieu. La recherche s’ouvre sur LinkedIn ; tu choisis ensuite les profils à importer.</p><form onSubmit={e=>{e.preventDefault();setTargetQuery([query,company,specialty].filter(Boolean).join(" ").slice(0,250)||"FX Sales Paris");setView("import");}}><label>Critères de recherche<input maxLength={250} value={query} onChange={e=>setQuery(e.target.value)} placeholder="FX Sales CACEIS Paris"/></label><button type="submit">Préparer dans l’import assisté</button></form></section></div>}
      <div hidden={view!=='outreach'} className="network-outreach-view"><OutreachTracker contacts={contacts} records={data.outreach||[]} onReload={load} initialContactId={outreachSeedId} onSeedConsumed={()=>setOutreachSeedId('')} onDirtyChange={onDirtyChange}/></div>
      {view==='import'&&<div className="network-import-view"><div className="network-section-intro"><button type="button" className="network-back" onClick={()=>setView('collect')}>← Recherches et imports</button><h3>Ajouter tes contacts</h3><p>Choisis une méthode, vérifie les informations, puis enregistre les profils utiles.</p></div><LinkedInAssisted key={targetQuery} initialQuery={targetQuery} expanded onImported={load}/></div>}
    </div>
  </div>;
}
