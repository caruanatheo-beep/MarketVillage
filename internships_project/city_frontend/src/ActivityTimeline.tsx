import React, {useState} from 'react';

type Entry = {id:number;agent_id:string;task_id:string;status:string;message:string;created_at:string};
type Person = {id:string;name:string};
export function ActivityTimeline({events,agents,onOpen}:{events:Entry[];agents:Person[];onOpen:(agent:string,task:string)=>void}) {
  const [query,setQuery]=useState('');
  const [agent,setAgent]=useState('');
  const [status,setStatus]=useState('');
  const [day,setDay]=useState('');
  const localDay=(value:string)=>{const d=new Date(value);return Number.isNaN(d.getTime())?'':`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;};
  const rows=events.filter(e=>(!agent||e.agent_id===agent)&&(!status||e.status===status)&&(!day||localDay(e.created_at)===day)&&`${e.message} ${e.task_id}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a,b)=>Date.parse(b.created_at)-Date.parse(a.created_at)||b.id-a.id);
  const labels:Record<string,string>={running:'En cours',queued:'En attente',waiting_approval:'À valider',completed:'Terminée',failed:'Erreur',cancelled:'Annulée'};
  return <section className="activity-timeline"><div className="timeline-filters">
    <input aria-label="Rechercher une activité ou un identifiant de mission" placeholder="Activité ou identifiant de mission…" value={query} onChange={e=>setQuery(e.target.value)}/>
    <select aria-label="Agent" value={agent} onChange={e=>setAgent(e.target.value)}><option value="">Tous les agents</option>{agents.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select>
    <select aria-label="Statut" value={status} onChange={e=>setStatus(e.target.value)}><option value="">Tous les statuts</option>{Object.entries(labels).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select>
    <input type="date" aria-label="Jour de l’activité" value={day} onChange={e=>setDay(e.target.value)}/>
  </div><small>{rows.length} événement{rows.length!==1?'s':''}</small>
  {!rows.length&&<p className="muted">Aucune activité pour ces critères.</p>}
  {rows.map((e,i)=><React.Fragment key={e.id}>{(i===0||localDay(rows[i-1].created_at)!==localDay(e.created_at))&&<h4 className="timeline-day">{new Date(e.created_at).toLocaleDateString('fr-FR',{weekday:'long',day:'numeric',month:'long'})}</h4>}
    <button type="button" className="timeline-event" onClick={()=>onOpen(e.agent_id,e.task_id)}><i className={`event-dot ${e.status}`}/><span><strong>{agents.find(a=>a.id===e.agent_id)?.name||e.agent_id}</strong><p>{e.message}</p><small>{labels[e.status]||e.status} · {e.task_id}</small></span><time>{new Date(e.created_at).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit'})}</time></button>
  </React.Fragment>)}</section>;
}
