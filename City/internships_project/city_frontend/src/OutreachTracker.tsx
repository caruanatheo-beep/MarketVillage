import React, {useEffect, useRef, useState} from "react";

export type OutreachStatus="draft"|"ready"|"sent"|"replied"|"follow_up";
export type OutreachRecord={id:string;contact_id:string;recipient_email:string;subject:string;body:string;status:OutreachStatus;
  sent_at:string;follow_up_at:string;notes:string;created_at:string;updated_at:string};
export type OutreachContact={id:string;name:string;role:string;company:string;email?:string};

const statusLabels:Record<OutreachStatus,string>={draft:"Brouillon",ready:"Prêt à envoyer",sent:"Envoyé",replied:"Réponse reçue",follow_up:"À relancer"};
export const followUpDue=(item:OutreachRecord)=>!!item.sent_at&&item.status!=='replied'&&(item.status==='follow_up'||!!item.follow_up_at&&item.follow_up_at<=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()));
const dateLabel=(value:string)=>value&&Number.isFinite(Date.parse(value))?new Intl.DateTimeFormat("fr-FR",{timeZone:'Europe/Paris',day:"numeric",month:"short",year:"numeric"}).format(new Date(value)):"Date inconnue";

export function OutreachTracker({contacts,records,onReload,initialContactId,onSeedConsumed,onDirtyChange}:{contacts:OutreachContact[];records:OutreachRecord[];onReload:()=>Promise<void>;initialContactId:string;onSeedConsumed:()=>void;onDirtyChange?:(dirty:boolean)=>void}){
  const [recordId,setRecordId]=useState(""),[contactId,setContactId]=useState(""),[recipientEmail,setRecipientEmail]=useState("");
  const [subject,setSubject]=useState(""),[body,setBody]=useState(""),[status,setStatus]=useState<OutreachStatus>("draft");
  const [followUpAt,setFollowUpAt]=useState(""),[notes,setNotes]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const [filter,setFilter]=useState<"all"|"due"|OutreachStatus>("all"),[query,setQuery]=useState('');
  const [dirty,setDirty]=useState(false),[notice,setNotice]=useState(''),[sentAt,setSentAt]=useState('');
  const saving=useRef(false);
  const canSwitch=()=>!saving.current&&(!dirty||window.confirm('Des modifications ne sont pas enregistrées. Les abandonner ?'));
  useEffect(()=>{onDirtyChange?.(dirty);},[dirty,onDirtyChange]);
  const contact=contacts.find(item=>item.id===contactId);
  const counts=Object.fromEntries((Object.keys(statusLabels) as OutreachStatus[]).map(key=>[key,records.filter(item=>item.status===key).length])) as Record<OutreachStatus,number>;
  const text=(value:string)=>value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const visibleRecords=records.filter(item=>{const person=contacts.find(c=>c.id===item.contact_id);return (filter==='all'||filter==='due'&&followUpDue(item)||item.status===filter)&&text(`${person?.name||''} ${person?.company||''} ${item.subject} ${item.recipient_email}`).includes(text(query));}).sort((a,b)=>Number(followUpDue(b))-Number(followUpDue(a))||b.updated_at.localeCompare(a.updated_at));
  function planFollowUp(days:number){
    const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    const date=new Date(today+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+days);
    setFollowUpAt(date.toISOString().slice(0,10));setDirty(true);setNotice('');
  }
  async function copyMessage(){
    try{await navigator.clipboard.writeText(body);setNotice('Message copié.');}catch{setError('Copie indisponible : sélectionne le texte du message pour le copier.');}
  }

  function startDraft(id=""){
    if(!canSwitch())return;
    setDirty(!!id);setNotice('');setSentAt('');
    const selected=contacts.find(item=>item.id===id);
    const firstName=selected?.name.trim().split(/\s+/)[0]||"";
    setRecordId("");setContactId(id);setRecipientEmail(selected?.email||"");setStatus("draft");setFollowUpAt("");setNotes("");setError("");
    setSubject(selected?`Échange autour de ${selected.role||selected.company}`:"");
    setBody(selected?`Bonjour ${firstName},\n\nJe me permets de vous contacter car votre parcours comme ${selected.role||"professionnel"} chez ${selected.company||"votre entreprise"} a retenu mon attention.\n\n[Ajoute ici le motif précis de ton message et ta demande.]\n\nBien cordialement,\n[Ta signature]`:"");
  }
  function openRecord(item:OutreachRecord){
    if(!canSwitch())return;
    setDirty(false);setNotice('');setSentAt(item.sent_at);
    setRecordId(item.id);setContactId(item.contact_id);setRecipientEmail(item.recipient_email);setSubject(item.subject);setBody(item.body);
    setStatus(item.status);setFollowUpAt(item.follow_up_at);setNotes(item.notes);setError("");
  }
  useEffect(()=>{if(initialContactId){const existing=records.find(item=>item.contact_id===initialContactId);if(existing)openRecord(existing);else startDraft(initialContactId);onSeedConsumed();}},[initialContactId]);

  async function save(nextStatus=status){
    if(saving.current)return;
    if(!contactId){setError("Choisis d’abord un contact du répertoire.");return;}
    if(nextStatus!=='draft'&&(!/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(recipientEmail.trim())||!subject.trim()||!body.trim())){setError('Complète une adresse valide, l’objet et le message avant de changer son état.');return;}
    if(['replied','follow_up'].includes(nextStatus)&&!sentAt){setError('Confirme d’abord l’envoi de ce message.');return;}
    saving.current=true;setNotice('');
    setBusy(true);setError("");
    try{
      const response=await fetch("/city/api/outreach",{method:"POST",headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},
        body:JSON.stringify({...(recordId?{id:recordId}:{}),contact_id:contactId,recipient_email:recipientEmail,subject,body,status:nextStatus,follow_up_at:followUpAt,notes})});
      const payload=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(payload.detail||"Le suivi n’a pas pu être enregistré.");
      setRecordId(payload.record.id);setStatus(payload.record.status);setSentAt(payload.record.sent_at);setFollowUpAt(payload.record.follow_up_at);setDirty(false);setNotice('Suivi enregistré.');
      try{await onReload();}catch{setNotice('Suivi enregistré. La liste n’a pas pu être actualisée ; recharge-la avant de créer un autre message.');}
    }catch(exc){setError(exc instanceof Error?exc.message:"Le suivi n’a pas pu être enregistré.");}
    finally{saving.current=false;setBusy(false);}
  }

  return <div className="outreach-tracker">
    <section className="outreach-intro"><div><span className="network-kicker">MESSAGES ET RELANCES</span><h3>Un suivi clair de tes échanges</h3><p>Prépare ici, envoie depuis ton logiciel mail, puis confirme l’envoi dans City.</p></div></section>
    <div className="outreach-quick-filters" aria-label="Filtres des messages">{([
      ['all','Tous',records.length],['draft','Brouillons',counts.draft],['ready','Prêts',counts.ready],
      ['sent','Envoyés',counts.sent],['replied','Réponses',counts.replied],['due','À relancer',records.filter(followUpDue).length]
    ] as const).map(([key,label,count])=><button type="button" key={key} aria-pressed={filter===key} onClick={()=>setFilter(key)}>{label}<span>{count}</span></button>)}</div>
    <div className="outreach-layout">
      <section className="outreach-list-panel"><div className="outreach-list-heading"><h4>Mes envois</h4><button type="button" disabled={busy} onClick={()=>startDraft()}>Nouveau message</button></div>
        <label className="outreach-search">Rechercher un message<input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Contact, entreprise ou objet…"/></label>
        <div className="outreach-record-list">{visibleRecords.map(item=>{const person=contacts.find(candidate=>candidate.id===item.contact_id);return <button type="button" key={item.id} disabled={busy} aria-pressed={recordId===item.id} className={`outreach-record ${recordId===item.id?"selected":""}`} onClick={()=>openRecord(item)}><span className={`outreach-status-dot ${item.status}`}/><span><strong>{person?.name||"Contact archivé"}</strong><small>{person?.company||"Entreprise inconnue"} · {statusLabels[item.status]}</small><em>{item.subject||"Objet à compléter"}</em>{followUpDue(item)&&<small className="outreach-due">Relance à faire{item.follow_up_at?` · ${dateLabel(item.follow_up_at)}`:""}</small>}</span><time>{dateLabel(item.sent_at||item.updated_at)}</time></button>;})}{!visibleRecords.length&&<p className="outreach-empty">Aucun suivi dans cette catégorie.</p>}</div>
      </section>
      <section className="outreach-editor"><div className="outreach-editor-heading"><div><span className="network-kicker">{recordId?"SUIVI ENREGISTRÉ":"NOUVEAU MESSAGE"}</span><h4>{contact?.name||"Choisir un contact"}</h4></div>{recordId&&<span className={`outreach-status-pill ${status}`}>{statusLabels[status]}</span>}</div>
        <fieldset disabled={busy} onChange={()=>{setDirty(true);setNotice('');}}>
        <label>Contact du répertoire<select disabled={!!recordId} value={contactId} onChange={event=>startDraft(event.target.value)}><option value="">Sélectionner un contact…</option>{recordId&&!contact&&<option value={contactId}>Contact archivé</option>}{contacts.slice().sort((a,b)=>a.name.localeCompare(b.name,"fr")).map(item=><option value={item.id} key={item.id}>{item.name} · {item.company||"Entreprise à confirmer"}</option>)}</select></label>
        {contact&&<p className="outreach-contact-context">{contact.role||"Poste à confirmer"} · {contact.company||"Entreprise à confirmer"}</p>}
        <label>Adresse e-mail <span>(à confirmer)</span><input type="email" maxLength={320} value={recipientEmail} onChange={event=>setRecipientEmail(event.target.value)} placeholder="adresse@entreprise.com" autoComplete="off"/></label>
        <label>Objet<input maxLength={500} value={subject} onChange={event=>setSubject(event.target.value)} placeholder="Objet du message"/></label>
        <label>Message<textarea maxLength={10000} rows={6} value={body} onChange={event=>setBody(event.target.value)} placeholder="Personnalise le message et vérifie les informations avant l’envoi."/></label>
        <div className="outreach-editor-meta"><label>État<select value={status} onChange={event=>setStatus(event.target.value as OutreachStatus)}>{(Object.keys(statusLabels) as OutreachStatus[]).map(key=><option value={key} key={key} disabled={sentAt?["draft","ready"].includes(key):["replied","follow_up"].includes(key)}>{statusLabels[key]}</option>)}</select></label><label>Relance prévue<input type="date" disabled={status==='replied'} value={followUpAt} onChange={event=>setFollowUpAt(event.target.value)}/></label></div>
        <div className="outreach-followup-shortcuts"><span>Prévoir une relance</span><button type="button" disabled={status==='replied'||!contactId} onClick={()=>planFollowUp(7)}>Dans 7 jours</button><button type="button" disabled={status==='replied'||!contactId} onClick={()=>planFollowUp(14)}>Dans 14 jours</button>{followUpAt&&status!=='replied'&&<button type="button" onClick={()=>{setFollowUpAt('');setDirty(true);setNotice('');}}>Retirer la date</button>}</div>
        <label>Notes de suivi<textarea rows={2} maxLength={3000} value={notes} onChange={event=>setNotes(event.target.value)} placeholder="Échange, réponse ou prochaine action…"/></label>
        </fieldset>
        {dirty&&<p className="outreach-unsaved">Modifications non enregistrées</p>}{notice&&<p className="outreach-save-notice" role="status">{notice}</p>}
        {error&&<p className="network-warning" role="alert">{error}</p>}
        <div className="outreach-actions"><button type="button" className="network-primary" disabled={busy||!contactId} onClick={()=>void save()}>{busy?"Enregistrement…":recordId?"Enregistrer les modifications":status==='draft'?"Enregistrer le brouillon":"Enregistrer le suivi"}</button>{!sentAt&&<button type="button" disabled={busy||!contactId} onClick={()=>void save("ready")}>Marquer prêt</button>}{!sentAt&&<button type="button" disabled={busy||!contactId} onClick={()=>void save("sent")}>Confirmer l’envoi</button>}{sentAt&&status!=="replied"&&<button type="button" disabled={busy} onClick={()=>void save("replied")}>Réponse reçue</button>}{body.trim()&&<button type="button" disabled={busy} onClick={()=>void copyMessage()}>Copier le message</button>}{/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(recipientEmail.trim())&&subject.trim()&&body.trim()&&<a href={`mailto:${encodeURIComponent(recipientEmail)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`}>Ouvrir mon logiciel mail ↗</a>}</div>
        {recordId&&<small className="outreach-sent-note">{status==="sent"&&"Envoi marqué manuellement · "}{records.find(item=>item.id===recordId)?.sent_at?`Envoyé le ${dateLabel(records.find(item=>item.id===recordId)!.sent_at)}`:"Suivi enregistré dans ton compte."}</small>}
      </section>
    </div>
  </div>;
}
