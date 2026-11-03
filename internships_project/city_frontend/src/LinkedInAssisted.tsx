import React, {useState} from "react";

const EMPTY={name:"",role:"",company:"",location:"",linkedin_url:"",school:"",evidence:""};
const SEARCHES=['(Sales OR Vendeur OR Vente) AND (Rates OR Credit OR FX OR Taux) AND Paris',
  '(Trader OR Trading OR Structurer OR Structureur) AND Paris',
  '("Portfolio Manager" OR Gérant OR Quant OR "Market Risk") AND Paris'];

export function LinkedInAssisted({onImported}:{onImported:()=>Promise<void>}){
  const [query,setQuery]=useState(SEARCHES[0]);
  const [contact,setContact]=useState(EMPTY),[busy,setBusy]=useState(false);
  const [status,setStatus]=useState(""),[error,setError]=useState("");
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
