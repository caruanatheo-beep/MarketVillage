import React from "react";

export type CollectionReport = {count?:number;duplicates?:number;rejected?:number;text?:string;warnings?:string[];source?:string};

export function ContactCollectionReport({report}:{report?:CollectionReport}){
  if(!report||!Object.keys(report).length)return null;
  const h=React.createElement;
  return h("section",{className:"network-collection-report","aria-label":"Dernier bilan"},
    h("h4",null,"Dernier bilan"),
    report.count!==undefined&&h("p",null,h("strong",null,`${report.count} nouveaux contacts`),` · ${report.duplicates??0} doublons écartés`,report.rejected!==undefined?` · ${report.rejected} fiches insuffisamment sourcées écartées`:""),
    report.count===0&&h("p",null,"Aucune nouvelle fiche enregistrée. ",report.duplicates?"Des profils déjà présents ont été écartés. ":"",report.rejected?"Des fiches sans preuves suffisantes ont été écartées. ":"",report.warnings?.length?"Une partie de la recherche n’a pas abouti ; consulte les avertissements ci-dessous.":"Les sources consultées n’ont pas fourni de nouveau profil exploitable."," Tu peux préparer une recherche ciblée ci-dessous."),
    report.text&&h("p",null,report.text),
    report.source&&h("small",null,`Sources de la collecte : ${report.source}`),
    report.warnings?.map((warning,i)=>h("p",{key:i,className:"network-warning"},warning)));
}
