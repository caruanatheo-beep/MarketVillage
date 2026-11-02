import {isPendingProposal,needsDecision,parisDay,type NotificationTask,type NotificationEvent} from './notifications';
export type CockpitTask=NotificationTask&{result:NotificationTask['result']&{new_count?:number;contacts?:unknown[]}};
export function cockpitData(tasks:CockpitTask[],events:NotificationEvent[],now=new Date()){
  const latest=new Map<string,NotificationEvent>();
  for(const event of events)if(event.id>(latest.get(event.task_id)?.id||0))latest.set(event.task_id,event);
  const finished=tasks.filter(t=>t.status==='completed'&&!isPendingProposal(t)).sort((a,b)=>Date.parse(b.finished_at||b.created_at)-Date.parse(a.finished_at||a.created_at));
  const active=tasks.filter(t=>['running','queued'].includes(t.status)).sort((a,b)=>Number(b.status==='running')-Number(a.status==='running')||Date.parse(a.created_at)-Date.parse(b.created_at));
  const decisions=tasks.filter(needsDecision).sort((a,b)=>Date.parse(a.created_at)-Date.parse(b.created_at));
  return {active,decisions,finished,latest,today:finished.filter(t=>parisDay(t.finished_at||t.created_at)===parisDay(now)).length};
}
export function resultSummary(task:CockpitTask):string{
  if(task.result.new_count!==undefined&&task.agent_id==='networker')return `${task.result.new_count} nouveaux contacts ajoutés`;
  if(task.result.new_count!==undefined&&task.agent_id==='internship_scout')return `${task.result.new_count} nouveaux stages détectés`;
  return (task.result.text||task.result.title||task.description).replace(/[#*`]/g,'').replace(/\s+/g,' ').trim().slice(0,180);
}
