export const CODE_AGENT_IDS = new Set(['job_hunter', 'city_ui_engineer', 'internships_engineer', 'quality_engineer']);
export const CONTACT_AGENT_IDS = new Set(['networker', 'securities_scout', 'prime_services_scout']);
export const AGENT_GROUP_LABELS = ['Coordination', 'Développement', 'Recherche de contacts', 'Agents métier'] as const;

export function agentGroup(id: string): typeof AGENT_GROUP_LABELS[number] {
  if (id === 'desk_manager') return 'Coordination';
  if (CONTACT_AGENT_IDS.has(id)) return 'Recherche de contacts';
  return CODE_AGENT_IDS.has(id) ? 'Développement' : 'Agents métier';
}

export function agentSections<T extends {id: string}>(agents: T[]) {
  return AGENT_GROUP_LABELS.map(label => ({label, agents: agents.filter(agent => agentGroup(agent.id) === label)}))
    .filter(section => section.agents.length > 0);
}
