export const CODE_AGENT_IDS = new Set(['job_hunter', 'city_ui_engineer', 'internships_engineer', 'quality_engineer']);

export function agentGroup(id: string): 'Développement' | 'Agents métier' {
  return CODE_AGENT_IDS.has(id) ? 'Développement' : 'Agents métier';
}

export function groupedAgents<T extends {id: string}>(agents: T[]) {
  return {
    code: agents.filter(agent => CODE_AGENT_IDS.has(agent.id)),
    business: agents.filter(agent => !CODE_AGENT_IDS.has(agent.id)),
  };
}
