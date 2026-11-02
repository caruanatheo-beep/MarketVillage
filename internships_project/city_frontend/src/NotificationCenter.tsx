import React,{useEffect,useRef,useState} from 'react';
import {ActivityTimeline} from './ActivityTimeline';
import {isPendingProposal,needsDecision,notificationRows,type NotificationTask,type NotificationEvent} from './notifications';

type Props={tasks:NotificationTask[];events:NotificationEvent[];agents:{id:string;name:string}[];readThrough:number;
  onClose:()=>void;onOpen:(id:string)=>void;onRead:()=>Promise<unknown>;onRelaunch:()=>Promise<unknown>;
  onApprove:(id:string)=>Promise<unknown>;onCancel:(id:string)=>Promise<unknown>;onReview:(id:string,approved:boolean)=>Promise<unknown>;onRetry:(id:string)=>Promise<unknown>;onRefresh:()=>Promise<void>};
const LABELS:Record<string,string>={completed:'Terminée',failed:'Erreur',queued:'En attente',running:'En cours',waiting_approval:'À valider',cancelled:'Annulée'};
export function NotificationCenter(props:Props){
  const dialog=useRef<HTMLDialogElement>(null);
  const [filter,setFilter]=useState('all'),[query,setQuery]=useState(''),[agent,setAgent]=useState('');
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
  useEffect(()=>{const el=dialog.current,previous=document.activeElement as HTMLElement|null;el?.showModal();el?.querySelector<HTMLInputElement>('input')?.focus();return()=>{el?.close();previous?.focus();};},[]);
  const rows=notificationRows(props.tasks,props.events,props.readThrough);
  const decisions=props.tasks.filter(needsDecision).length,failures=props.tasks.filter(t=>t.status==='failed').length,completed=props.tasks.filter(t=>t.status==='completed'&&!isPendingProposal(t)).length;
  const visible=rows.filter(({task,unread})=>(!agent||task.agent_id===agent)&&
    (filter==='all'||filter==='decision'&&needsDecision(task)||filter==='completed'&&task.status==='completed'&&!isPendingProposal(task)||filter==='failed'&&task.status==='failed'||filter==='active'&&['queued','running'].includes(task.status)||filter==='unread'&&unread)&&
    `${task.description} ${task.result.title||''} ${task.error||''} ${task.id}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  async function action(key:string,operation:()=>Promise<unknown>,success:string){
    if(busy)return;setBusy(key);setError('');setNotice('');
    try{await operation();await props.onRefresh();setNotice(success);}catch(exc){setError(exc instanceof Error?exc.message:'Action impossible.');}finally{setBusy('');}
  }
  const julesActive=props.tasks.some(t=>t.agent_id==='job_hunter'&&['running','queued','waiting_approval'].includes(t.status));
  return <dialog ref={dialog} className="network-window notification-center" aria-labelledby="notifications-title" onCancel={props.onClose}>
    <header className="notification-heading"><div><span className="notification-eyebrow">TON VILLAGE, EN UN COUP D’ŒIL</span><h2 id="notifications-title">Centre de notifications</h2><p>Les décisions à prendre, les résultats à consulter et les missions à suivre.</p></div><button type="button" className="network-close" onClick={props.onClose} aria-label="Fermer les notifications">×</button></header>
    <div className="notification-summary">
      <button className="decision" onClick={()=>setFilter('decision')}><span>À toi de décider</span><strong>{decisions}</strong><small>Validations et propositions</small></button>
      <button className="success" onClick={()=>setFilter('completed')}><span>Missions terminées</span><strong>{completed}</strong><small>Résultats disponibles</small></button>
      <button className="failure" onClick={()=>setFilter('failed')}><span>À examiner</span><strong>{failures}</strong><small>Erreurs et relances</small></button>
    </div>
    <div className="notification-commands"><button disabled={!!busy||julesActive} onClick={()=>void action('jules',props.onRelaunch,'Nouvel audit Jules ajouté aux missions.')}>{busy==='jules'?'Lancement…':julesActive?'Jules a une mission active':'↻ Relancer l’audit de Jules'}</button><button disabled={!!busy} onClick={()=>void action('read',props.onRead,'Notifications marquées comme lues. Les décisions restent à traiter.')}>Tout marquer comme lu</button></div>
    <div className="notification-tabs" role="group" aria-label="Filtrer les notifications">{[['all','Tout'],['decision','Décisions'],['unread','Non lues'],['completed','Terminées'],['active','En cours'],['failed','Erreurs']].map(([id,label])=><button key={id} aria-pressed={filter===id} className={filter===id?'selected':''} onClick={()=>setFilter(id)}>{label}</button>)}</div>
    <div className="notification-filters"><input aria-label="Rechercher une notification" placeholder="Mission, résultat ou identifiant…" value={query} onChange={e=>setQuery(e.target.value)}/><select aria-label="Agent des notifications" value={agent} onChange={e=>setAgent(e.target.value)}><option value="">Tous les agents</option>{props.agents.map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
    {error&&<p className="notification-feedback error" role="alert">{error}</p>}{notice&&<p className="notification-feedback" role="status">{notice}</p>}
    <div className="notification-feed"><p className="notification-count">{visible.length} mission(s) affichée(s) · décisions en priorité</p>
      {!visible.length&&<div className="notification-empty"><strong>Tout est calme ici.</strong><p>Aucune mission ne correspond à ces filtres.</p></div>}
      {visible.map(({task,event,unread})=>{const decision=needsDecision(task),proposal=isPendingProposal(task),blocked=proposal&&task.agent_id==='job_hunter'&&!task.result.revision;
        return <article key={task.id} className={`notification-card ${decision?'decision':task.status} ${unread?'unread':''}`}>
          <div className="notification-card-top"><span className={`roster-avatar pixel-agent-avatar ${task.agent_id}`} aria-hidden="true"><i className="agent-sprite"/></span><div><strong>{props.agents.find(a=>a.id===task.agent_id)?.name||task.agent_id}</strong><small>{new Date(event?.created_at||task.finished_at||task.created_at).toLocaleString('fr-FR',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Paris'})}</small></div><span className="notification-status">{decision?'Décision requise':LABELS[task.status]||task.status}</span>{unread&&<i className="notification-unread" title="Non lue"/>}</div>
          <h3>{task.description}</h3><p>{task.error||task.result.text?.slice(0,240)||task.result.title||event?.message||'Mission enregistrée.'}</p>
          {blocked&&<p className="notification-blockage">La branche nécessite un audit avec une révision Git. Relance l’audit de Jules pour obtenir une proposition à jour.</p>}
          {task.result.file&&<p className="notification-file">Fichier préparé : <code>{task.result.file}</code></p>}
          <div className="notification-actions"><button onClick={()=>props.onOpen(task.id)}>{task.status==='completed'?'Voir le résultat':'Voir la mission'} →</button>
            {proposal&&<><button className="accept" disabled={!!busy||blocked} onClick={()=>void action(task.id,()=>props.onReview(task.id,true),'Proposition validée et mission suivante créée.')}>Valider la proposition</button><button disabled={!!busy} onClick={()=>void action(task.id,()=>props.onReview(task.id,false),'Proposition refusée.')}>Refuser</button></>}
            {task.status==='waiting_approval'&&<><button className="accept" disabled={!!busy} onClick={()=>void action(task.id,()=>props.onApprove(task.id),'Mission autorisée.')}>Autoriser la mission</button><button disabled={!!busy} onClick={()=>void action(task.id,()=>props.onCancel(task.id),'Mission annulée.')}>Annuler</button></>}
            {task.status==='failed'&&(!task.workflow_id||(task.retry_count||0)<(task.max_retries||0))&&<button disabled={!!busy} onClick={()=>void action(task.id,()=>props.onRetry(task.id),'Mission remise en file.')}>Réessayer</button>}
          </div>
        </article>;
      })}
      <details className="notification-journal"><summary>Journal détaillé · {props.events.length} événements récents</summary><ActivityTimeline events={props.events} agents={props.agents} onOpen={(_agent,id)=>props.onOpen(id)}/></details>
    </div>
    <footer className="notification-footer">Les validations sont explicites. Lire une notification n’autorise aucune action.</footer>
  </dialog>;
}
