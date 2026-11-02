"""Appearance for Gradio's built-in authenticated login view.

The login form and /login endpoint remain Gradio's. Gradio shows auth_message
on the unauthenticated page, while the main Blocks CSS is not sent there.
"""

from __future__ import annotations

import base64
import html
from pathlib import Path


_EMBLEM = base64.b64encode(
    (Path(__file__).parent / "assets" / "skema_emblem_2026.png").read_bytes()
).decode("ascii")

_CSS = """
<style>
div.main.app:has(.career-auth-content) {
  box-sizing: border-box;
  width: 100%;
  max-width: none;
  min-height: 100dvh;
  padding: 0;
  background: #f7f7fb;
}
.wrap:has(.career-auth-content) {
  min-height: 100dvh;
  margin: 0;
  padding: 24px;
  box-sizing: border-box;
  background: radial-gradient(circle at 50% 8%, #eee8ff 0, #f7f7fb 42%, #f8f9fc 100%);
  font-family: Arial, Helvetica, sans-serif;
  color: #17213a;
}
.wrap:has(.career-auth-content) .column.panel {
  box-sizing: border-box;
  width: min(100%, 420px);
  max-width: 420px;
  min-width: 0 !important;
  position: relative;
  padding: 28px 32px 24px;
  border: 1px solid #e8e3f1;
  border-radius: 16px;
  background: #fff;
  box-shadow: 0 18px 46px rgba(49, 36, 90, .09), 0 2px 8px rgba(49, 36, 90, .04);
  display: flex;
  flex-direction: column;
  height: auto;
  min-height: 0;
  flex: none;
  gap: 0;
}
.wrap:has(.career-auth-content) .column.panel > h2 { display: none; }
.wrap:has(.career-auth-content) p.auth { margin: 0 0 20px; color: #17213a; }
.career-auth-content { display: block; }
.career-auth-brand { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.career-auth-emblem { display: block; width: 84px; height: 88px; flex: none; overflow: hidden; clip-path: circle(37px at 42px 44px); }
.career-auth-emblem img { display: block; width: 1078px; height: 135px; max-width: none; transform: translate(-497px, -7px); }
.career-auth-wordmark { display: flex; flex-direction: column; line-height: 1; }
.career-auth-wordmark strong { font-size: 20px; letter-spacing: .055em; color: #17213a; }
.career-auth-wordmark small { margin-top: 4px; font-size: 8px; font-weight: 700; letter-spacing: .15em; color: #48516b; }
.career-auth-title { display: block; margin: 0 0 7px; font-size: 29px; line-height: 1.15; letter-spacing: -.035em; font-weight: 700; }
.career-auth-subtitle { display: block; max-width: 340px; font-size: 14px; line-height: 1.5; color: #626d82; }
.wrap:has(.career-auth-content) .form {
  display: flex; flex-direction: column; flex-wrap: nowrap; gap: 18px; width: 100%;
  min-height: 0; padding: 0; border: 0; border-radius: 0;
  background: transparent; box-shadow: none; overflow: visible;
}
.wrap:has(.career-auth-content) .form > * {
  flex: none; height: auto; min-height: 0; margin: 0; padding: 0;
  border: 0; background: transparent; box-shadow: none;
}
.wrap:has(.career-auth-content) .form label { color: #28334d; font-weight: 600; line-height: 1.35; }
.wrap:has(.career-auth-content) .form [data-testid="block-info"] { display: none; }
.wrap:has(.career-auth-content) label:has(input[data-testid="textbox"]),
.wrap:has(.career-auth-content) label:has(input[data-testid="password"]) { font-size: 0; }
.wrap:has(.career-auth-content) label:has(input[data-testid="textbox"])::before {
  content: "Identifiant"; display: block; margin-bottom: 8px; font-size: 14px;
}
.wrap:has(.career-auth-content) label:has(input[data-testid="password"])::before {
  content: "Mot de passe"; display: block; margin-bottom: 8px; font-size: 14px;
}
.wrap:has(.career-auth-content) .input-container {
  position: relative; width: 100%; height: 48px; min-height: 0;
  margin: 0; padding: 0; border: 0; background: transparent; box-shadow: none;
}
.wrap:has(.career-auth-content) label.container.show_textbox_border input[data-testid="textbox"],
.wrap:has(.career-auth-content) label.container.show_textbox_border input[data-testid="password"] {
  box-sizing: border-box;
  width: 100%;
  height: 48px;
  min-height: 0;
  padding: 0 14px;
  border: 1px solid #d8dce7;
  border-radius: 10px;
  background: #fff;
  color: #17213a;
  font: 400 16px Arial, Helvetica, sans-serif;
  box-shadow: none;
}
.wrap:has(.career-auth-content) input[data-testid="password"] { padding-right: 88px; }
.wrap:has(.career-auth-content) input::placeholder { color: #8290a5; opacity: 1; }
.wrap:has(.career-auth-content) input:focus-visible {
  outline: 3px solid rgba(112, 81, 207, .16);
  outline-offset: 1px;
  border-color: #7051cf;
}
.career-auth-content > .career-auth-toggle { display: none; }
.career-auth-toggle {
  position: absolute;
  z-index: 2;
  right: 7px;
  top: 50%;
  transform: translateY(-50%);
  padding: 7px 8px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: #6546bc;
  font: 600 12px Arial, Helvetica, sans-serif;
  cursor: pointer;
}
.career-auth-toggle:hover, .career-auth-toggle:focus-visible { background: #f1ecff; outline: none; }
.wrap:has(.career-auth-content) .input-container .career-auth-toggle {
  display: inline-block; position: absolute; right: 7px; left: auto; top: 50%;
  width: auto; height: auto; transform: translateY(-50%); margin: 0;
  padding: 7px 8px; font: 600 12px Arial, Helvetica, sans-serif;
}
.wrap:has(.career-auth-content) button.primary {
  width: 100%; height: 48px; min-height: 48px; margin-top: 20px;
  border: 1px solid #7051cf; border-radius: 10px;
  background: #7051cf; color: #fff;
  font-size: 0; font-family: Arial, Helvetica, sans-serif;
  font-weight: 700; cursor: pointer;
  transition: background .15s ease, box-shadow .15s ease, transform .15s ease;
}
.wrap:has(.career-auth-content) button.primary::after { content: "Se connecter"; font-size: 15px; }
.wrap:has(.career-auth-content) button.primary:hover { background: #5c3db8; box-shadow: 0 5px 12px rgba(88, 58, 169, .18); }
.wrap:has(.career-auth-content) button.primary:focus-visible { outline: 3px solid rgba(112, 81, 207, .3); outline-offset: 3px; }
.wrap:has(.career-auth-content) button.primary:disabled { cursor: wait; opacity: .72; transform: none; box-shadow: none; }
.wrap[data-career-auth-loading="true"] button.primary::after { content: "Connexion…"; }
.wrap:has(.career-auth-content) p.creds {
  box-sizing: border-box; margin: 0 0 16px; padding: 8px 10px;
  border: 1px solid #f2caca; border-radius: 8px;
  background: #fff5f5; color: #a12635; font-size: 0;
}
.wrap:has(.career-auth-content) p.creds::after { content: "Identifiant ou mot de passe incorrect."; font-size: 13px; }
.wrap:has(.career-auth-content) .career-auth-signup { display: block; margin-top: 14px; color: #6546bc;
  font-size: 14px; font-weight: 600; text-align: center; text-decoration: none; }
.career-auth-signup:hover { text-decoration: underline; }
.career-auth-signup:focus-visible { outline: 3px solid rgba(112, 81, 207, .3); outline-offset: 3px; }
.career-auth-footer {
  display: block; margin-top: 19px; padding-top: 14px;
  border-top: 1px solid #eceaf2; text-align: center;
}
.career-auth-footer span { display: block; color: #758094; font-size: 11px; line-height: 1.5; }
@media (max-width: 520px) {
  .wrap:has(.career-auth-content) { padding: 18px; }
  .wrap:has(.career-auth-content) .column.panel { padding: 24px 22px 20px; }
  .career-auth-title { font-size: 27px; }
}
</style>
"""

# The native Gradio login component owns the inputs and submit action. This
# enhancement only moves a button into its password field and reflects loading.
_ENHANCE = """(function(image){
  var root=image.closest('.wrap');
  if(!root || root.dataset.careerAuthEnhanced) return;
  root.dataset.careerAuthEnhanced='true';
  function decorate(){
    var account=root.querySelector('input[data-testid="textbox"]');
    var input=root.querySelector('input[data-testid="password"]');
    var toggle=root.querySelector('.career-auth-toggle');
    if(account){account.setAttribute('aria-label','Identifiant');account.setAttribute('placeholder','ex. prénom.nom');}
    if(input){input.setAttribute('aria-label','Mot de passe');input.setAttribute('placeholder','••••••••');}
    if(input && toggle && toggle.parentElement!==input.parentElement){
      input.parentElement.appendChild(toggle);
    }
    var submit=root.querySelector('button.primary');
    if(submit){
      submit.setAttribute('aria-label','Se connecter');
      if(submit.textContent!=='Se connecter') submit.textContent='Se connecter';
    }
    var footer=root.querySelector('.career-auth-footer');
    var signup=root.querySelector('.career-auth-signup');
    var panel=root.querySelector('.column.panel');
    if(signup && panel && signup.parentElement!==panel) panel.appendChild(signup);
    if(footer && panel && footer.parentElement!==panel) panel.appendChild(footer);
    var error=root.querySelector('p.creds');
    if(error){
      error.setAttribute('role','alert');
      error.setAttribute('aria-label','Identifiant ou mot de passe incorrect.');
      root.dataset.careerAuthLoading='false';
      if(submit) submit.disabled=false;
    }
  }
  var observer=new MutationObserver(decorate);
  observer.observe(root,{childList:true,subtree:true});
  root.addEventListener('click',function(event){
    var toggle=event.target.closest('.career-auth-toggle');
    if(toggle){
      var input=root.querySelector('input[data-testid="password"]');
      if(!input) return;
      var visible=input.type==='password';
      input.type=visible?'text':'password';
      toggle.textContent=visible?'Masquer':'Afficher';
      toggle.setAttribute('aria-label',visible?'Masquer le mot de passe':'Afficher le mot de passe');
      toggle.setAttribute('aria-pressed',String(visible));
      return;
    }
    if(event.target.closest('button.primary')) busy();
  });
  root.addEventListener('keydown',function(event){
    if(event.key==='Enter' && event.target.matches('input[data-testid="textbox"],input[data-testid="password"]')) busy();
  });
  function busy(){
    root.dataset.careerAuthLoading='true';
    setTimeout(function(){var submit=root.querySelector('button.primary'); if(submit) submit.disabled=true;},0);
    setTimeout(function(){root.dataset.careerAuthLoading='false';var submit=root.querySelector('button.primary');if(submit)submit.disabled=false;},10000);
  }
  decorate();
})(this)"""


def auth_message() -> str:
    return (
        _CSS
        + '<span class="career-auth-content">'
        + '<span class="career-auth-brand">'
        + '<span class="career-auth-emblem">'
        + f'<img src="data:image/png;base64,{_EMBLEM}" alt="" onload="{html.escape(_ENHANCE, quote=True)}">'
        + '</span>'
        + '<span class="career-auth-wordmark"><strong>SKEMA</strong><small>BUSINESS SCHOOL</small></span>'
        + '</span>'
        + '<strong class="career-auth-title">Bienvenue</strong>'
        + '<span class="career-auth-subtitle">Connecte-toi pour retrouver tes offres et tes candidatures.</span>'
        + '<button class="career-auth-toggle" type="button" aria-label="Afficher le mot de passe" aria-pressed="false">Afficher</button>'
        + '<a class="career-auth-signup" href="/inscription">Créer un compte</a>'
        + '<span class="career-auth-footer"><span>MSc Financial Markets &amp; Investments</span>'
        + '<span>Théo Caruana</span></span></span>'
    )
