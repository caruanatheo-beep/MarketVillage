import React, {useState} from "react";

const EMPTY={name:"",role:"",company:"",location:"",linkedin_url:"",school:"",evidence:""};
const SEARCHES=['(Sales OR Vendeur OR Vente) AND (Rates OR Credit OR FX OR Taux) AND Paris',
  '(Trader OR Trading OR Structurer OR Structureur) AND Paris',
  '("Portfolio Manager" OR Gérant OR Quant OR "Market Risk") AND Paris'];
type BulkResult={contacts:{name:string;role:string;company:string;location:string;contact_segment:string}[];excluded:{name:string;reason:string}[];imported:number;duplicates:number;text:string};

export function LinkedInAssisted({onImported}:{onImported:()=>Promise<void>}){
  const [query,setQuery]=useState(SEARCHES[0]);
  const [contact,setContact]=useState(EMPTY),[busy,setBusy]=useState(false);
  const [status,setStatus]=useState(""),[error,setError]=useState("");
  const [pageText,setPageText]=useState(""),[preview,setPreview]=useState<BulkResult|null>(null);
  const [bulkStatus,setBulkStatus]=useState(""),[bulkError,setBulkError]=useState("");
  async function submitPage(commit:boolean){
    setBusy(true);setBulkStatus("");setBulkError("");
    try{
      const response=await fetch("/city/api/network/assisted/bulk",{method:"POST",headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},body:JSON.stringify({text:pageText,commit})});
      const data=await response.json();
      if(!response.ok)throw Error(data.detail||"Importation impossible.");
      if(commit){setPreview(null);setBulkStatus(data.text);await onImported();}
      else setPreview(data);
    }catch(exc){setBulkError(exc instanceof Error?exc.message:"Importation impossible.");}
    finally{setBusy(false);}
  }
  async function submit(event:React.FormEvent){
    event.preventDefault();setBusy(true);setStatus("");setError("");
    try{
      const response=await fetch("/city/api/network/assisted",{method:"POST",headers:{"Content-Type":"application/json","X-MarketDesk-City":"1"},body:JSON.stringify(contact)});
      const data=await response.json();
      if(!response.ok)throw Error(data.detail||"Importation impossible.");
      setStatus(data.text);if(data.imported)setContact(EMPTY);
      await onImported();
    }catch(exc){setError(exc instanceof Error?exc.message:"Importation impossible.");}
    finally{setBusy(false);}
  }
  return <details className="network-schedule network-assisted">
    <summary><span>LinkedIn · mode assisté<small>Prépare une recherche, consulte les profils, puis ajoute les contacts sélectionnés.</small></span></summary>
    <div className="network-schedule-body">
      <p>Tu navigues et te connectes directement sur LinkedIn. Lina prépare les liens et enregistre les informations professionnelles que tu choisis de saisir ici.</p>
      <label>Requête LinkedIn<input value={query} maxLength={250} onChange={event=>setQuery(event.target.value)}/></label>
      <div className="network-actions">{SEARCHES.map((text,index)=><button key={text} type="button" onClick={()=>setQuery(text)}>{["Sales","Trading / structuration","Recherche / gestion"][index]}</button>)}</div>
      <div className="network-actions"><a className="network-primary" href={`https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(query)}`} target="_blank" rel="noopener noreferrer">Ouvrir la recherche LinkedIn ↗</a></div>
      <section className="network-assisted-bulk">
        <h4>Importer une page de résultats copiée</h4>
        <p>Copie les résultats de recherche LinkedIn, colle-les ici, puis vérifie l’aperçu. Les profils hors métiers de marché sont écartés.</p>
        <label>Résultats copiés<textarea rows={7} maxLength={30000} value={pageText} disabled={busy} onChange={event=>{setPageText(event.target.value);setPreview(null);setBulkStatus("");}} placeholder="Nom Prénom • 2e&#10;Poste actuel : FX Sales chez Banque…"/></label>
        <div className="network-actions"><button type="button" disabled={busy||!pageText.trim()} onClick={()=>void submitPage(false)}>Analyser la copie</button></div>
        {preview&&<div className="network-assisted-preview"><p role="status">{preview.text}</p>
          <ul>{preview.contacts.map((item,index)=><li key={`${item.name}-${index}`}><strong>{item.name}</strong> · {item.role} · {item.company}{item.location?` · ${item.location}`:""}</li>)}</ul>
          {preview.excluded.length>0&&<details><summary>{preview.excluded.length} profils écartés</summary><ul>{preview.excluded.map((item,index)=><li key={`${item.name}-${index}`}>{item.name} · {item.reason}</li>)}</ul></details>}
          {preview.contacts.length>0&&<button type="button" disabled={busy} onClick={()=>void submitPage(true)}>Enregistrer ces {preview.contacts.length} contacts</button>}
        </div>}
        {bulkStatus&&<p role="status">{bulkStatus}</p>}{bulkError&&<p role="alert" className="network-warning">{bulkError}</p>}
        <p><small>Import local sans appel IA. Sans lien de profil dans la copie, la fiche conserve le nom, le poste, la banque et la mention « à vérifier ».</small></p>
      </section>
      <form onSubmit={submit}>
        <h4>Ajouter un profil sélectionné</h4>
        <div className="network-assisted-fields">{([
          ["name","Nom complet"],["role","Poste en finance de marché"],["company","Entreprise"],
          ["location","Localisation (facultatif)"],["linkedin_url","Lien du profil LinkedIn"],["school","École / université (facultatif)"],
        ] as const).map(([field,label])=><label key={field}>{label}<input value={contact[field]} type={field==="linkedin_url"?"url":"text"} maxLength={300} required={field!=="school"&&field!=="location"} onChange={event=>setContact({...contact,[field]:event.target.value})}/></label>)}</div>
        <label>Extrait professionnel sélectionné<textarea rows={4} maxLength={4000} required value={contact.evidence} onChange={event=>setContact({...contact,evidence:event.target.value})} placeholder="Recopie les lignes qui confirment le nom, le poste et la banque ; ajoute le lieu ou l’école s’ils sont indiqués."/></label>
        <p><small>Import local sans appel IA. Les doublons sont écartés et les fiches existantes sont conservées. Aucun compte ou cookie LinkedIn n’est transmis à City.</small></p>
        <button type="submit" disabled={busy}>{busy?"Importation…":"Ajouter ce contact"}</button>
        {status&&<p role="status">{status}</p>}{error&&<p role="alert" className="network-warning">{error}</p>}
      </form>
    </div>
  </details>;
}
