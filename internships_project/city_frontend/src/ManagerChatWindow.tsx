import React, {useEffect, useRef} from "react";

export function ManagerChatWindow({children,onClose}:{children:React.ReactNode;onClose:()=>void}) {
  const dialog=useRef<HTMLDialogElement>(null);
  useEffect(()=>{
    const el=dialog.current, previous=document.activeElement as HTMLElement|null;
    el?.showModal();
    el?.querySelector<HTMLTextAreaElement>("textarea")?.focus();
    const history=el?.querySelector<HTMLElement>(".chat-history");
    if(history)history.scrollTop=history.scrollHeight;
    return()=>{el?.close();previous?.focus();};
  },[]);
  return <dialog ref={dialog} className="network-window manager-chat-window" aria-labelledby="manager-chat-title" onCancel={onClose}
    onClick={event=>{if(event.target===event.currentTarget){const r=event.currentTarget.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)onClose();}}}>
    <header className="network-window-heading">
      <span className="network-host roster-avatar pixel-agent-avatar desk_manager" aria-hidden="true"><i className="agent-sprite"/></span>
      <div><span className="network-kicker">Command Center</span><h2 id="manager-chat-title">Desk Manager</h2><p>Confie tes demandes aux agents et retrouve ta conversation.</p></div>
      <button type="button" className="network-close" onClick={onClose} aria-label="Fermer le chat">×</button>
    </header>
    <div className="command-console manager-chat-content">{children}</div>
  </dialog>;
}
