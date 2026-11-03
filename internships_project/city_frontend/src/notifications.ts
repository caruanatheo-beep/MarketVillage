export type NotificationTask={id:string;agent_id:string;description:string;status:string;created_at:string;finished_at?:string;started_at?:string;error?:string;workflow_id?:string;retry_count?:number;max_retries?:number;
  result:{title?:string;text?:string;summary?:string;market_points?:number;approval_required?:boolean;role_version?:number;branch?:string;review_decision?:string;revision?:string;blockage?:string;file?:string}};
export type NotificationEvent={id:number;agent_id:string;task_id:string;status:string;message:string;created_at:string};
export function isPendingProposal(task:NotificationTask):boolean{
  return task.status==='completed'&&task.result.role_version===2&&!!task.result.approval_required&&!task.result.branch&&!task.result.review_decision&&['job_hunter','innovation_lab'].includes(task.agent_id);
}
export const needsDecision=(task:NotificationTask)=>task.status==='waiting_approval'||isPendingProposal(task);
export function parisDay(value:string|Date):string{
  const date=new Date(value);return Number.isNaN(date.getTime())?'':new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
}
export function notificationRows(tasks:NotificationTask[],events:NotificationEvent[],readThrough:number){
  const latest=new Map<string,NotificationEvent>();
  for(const event of events)if(event.id>(latest.get(event.task_id)?.id||0))latest.set(event.task_id,event);
  return tasks.map(task=>({task,event:latest.get(task.id),unread:(latest.get(task.id)?.id||0)>readThrough}))
    .sort((a,b)=>Number(needsDecision(b.task))-Number(needsDecision(a.task))||
      Date.parse(b.event?.created_at||b.task.finished_at||b.task.created_at)-Date.parse(a.event?.created_at||a.task.finished_at||a.task.created_at));
}
