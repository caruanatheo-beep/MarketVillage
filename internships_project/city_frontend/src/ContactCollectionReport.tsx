import React from "react";

export type CollectionReport = {count?:number;duplicates?:number;duplicate_examples?:{name:string;role:string;company:string;source_url:string;reason:string}[];rejected?:number;text?:string;warnings?:string[];source?:string};

export function ContactCollectionReport({report}:{report?:CollectionReport}){
  if(!report||!Object.keys(report).length)return null;
  const h=React.createElement;
  return h("section",{className:"network-collection-report","aria-label":"Dernier bilan"},
    h("h4",null,"Dernier bilan"),
    report.count!==undefined&&h("p",null,h("strong",null,`${report.count} nouveaux contacts`),` · ${report.duplicates??0} doublons écartés`,report.rejected!==undefined?` · ${report.rejected} fiches insuffisamment sourcées écartées`:""),
    report.count===0&&h("p",null,"Aucune nouvelle fiche enregistrée. ",report.duplicates?"Des profils déjà présents ont été écartés. ":"",report.rejected?"Des fiches sans preuves suffisantes ont été écartées. ":"",report.warnings?.length?"Une partie de la recherche n’a pas abouti ; consulte les avertissements ci-dessous.":"Les sources consultées n’ont pas fourni de nouveau profil exploitable."," Tu peux préparer une recherche ciblée ci-dessous."),
    report.text&&h("p",null,report.text),
    report.source&&h("small",null,`Sources de la collecte : ${report.source}`),
    !!report.duplicate_examples?.length&&h("details",null,
      h("summary",null,"Voir les doublons écartés"),
      h("p",null,"Exemples de profils déjà enregistrés ou rencontrés plusieurs fois pendant cette collecte (5 maximum). Les fiches existantes sont conservées."),
      h("ul",null,report.duplicate_examples.map((contact,i)=>h("li",{key:i},
        h("strong",null,contact.name),` · ${contact.role} · ${contact.company} — ${contact.reason}. `,
        (()=>{try{const url=new URL(contact.source_url);return url.protocol==="https:"&&!url.username&&!url.password?h("a",{href:contact.source_url,target:"_blank",rel:"noopener noreferrer"},"Source du doublon ↗"):null;}catch{return null;}})())))),
    report.warnings?.map((warning,i)=>h("p",{key:i,className:"network-warning"},warning)));
}
