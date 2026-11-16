type IconName = 'city' | 'code' | 'contacts' | 'missions' | 'team' | 'internships' | 'notifications' | 'settings';

const paths: Record<IconName, string> = {
  city: 'M4 21V7h10v14M14 11h6v10M2 21h20M8 11h2M8 15h2M8 19h2M17 15h1M17 18h1',
  code: 'm8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16',
  contacts: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8m6 10v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  missions: 'm3 6 1 1 2-2m-3 7 1 1 2-2m-3 7 1 1 2-2M10 6h11M10 12h11M10 18h11',
  team: 'M3 21v-5h6v5m6 0v-5h6v5M6 16v-4h12v4m-6-4V9m-3-6h6v6H9z',
  internships: 'M9 7V4h6v3M3 7h18v14H3zM3 12l9 3 9-3M12 12v4',
  notifications: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  settings: 'M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6',
};

export function SidebarIcon({name}: {name: IconName}) {
  return <svg className="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]}/></svg>;
}
