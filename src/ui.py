from __future__ import annotations

import html
import inspect
import os
import re
from urllib.parse import quote
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import gradio as gr
import pandas as pd
import requests

from .agent import MarketAgent, RAG_ROOT
from .analytics import (
    briefing_markdown,
    cockpit_html,
    cross_asset_figure,
    curve_spreads,
    format_change,
    format_value,
    history_figure,
    point_map,
    desk_focus_figure,
    profiled_cockpit_html,
    yield_curve_figure,
)
from .calendar import load_calendar
from .config import settings
from .data import SERIES, MarketDataCollector, empty_points, load_snapshot, service_summary
from .memory import memory_markdown, new_session_state
from .intelligence import PROFILES, profiled_brief, surprise_text
from .macro_expectations import enrich_events, fetch_market_expectations
from .models import CalendarEvent, MarketPoint, NewsItem
from .news import load_news, recent_news, fetch_global_news, cached_global_news
from .reports import build_pdf, email_ready, report_sources
from .security import redact_secrets
from .tools import registry_markdown


CSS = """
.headline-brief {margin:0 0 24px;border:1px solid #303030;border-radius:8px;background:#111210;padding:4px 18px 10px;}
.headline-row {display:flex;justify-content:space-between;gap:20px;padding:12px 0;border-top:1px solid #292a28;text-decoration:none!important;color:#eee!important;align-items:center;}
.headline-row strong {font-size:14px;line-height:1.5;font-weight:500;}
.headline-row span {font-size:11px;color:#a4a6a1;white-space:nowrap;}
.headline-row:hover strong {color:#ed9b48;}
@media(max-width:800px){.headline-row{align-items:flex-start;flex-direction:column;gap:4px;}.headline-row span{white-space:normal;}}
:root {
  color-scheme:dark;
  --desk-bg:#070908;
  --desk-panel:#0f1210;
  --desk-panel-2:#141714;
  --desk-field:#1c201d;
  --desk-field-hover:#242925;
  --desk-line:#2a2e2b;
  --desk-text:#eeeae2;
  --desk-muted:#8c918d;
  --desk-orange:#e98c32;
  --desk-yellow:#e3ca58;
  --desk-green:#58d570;
  --desk-red:#ef5b50;
  --desk-blue:#7892ff;
}
html, body {
  color-scheme:dark !important;
  background:var(--desk-bg) !important;
}
.gradio-container {
  --body-background-fill:var(--desk-bg) !important;
  --background-fill-primary:var(--desk-panel) !important;
  --background-fill-secondary:var(--desk-panel-2) !important;
  --block-background-fill:var(--desk-panel) !important;
  --block-label-background-fill:var(--desk-panel) !important;
  --input-background-fill:var(--desk-field) !important;
  --input-background-fill-focus:var(--desk-field) !important;
  --input-background-fill-hover:var(--desk-field-hover) !important;
  --input-border-color:var(--desk-line) !important;
  --input-border-color-focus:var(--desk-orange) !important;
  --border-color-primary:var(--desk-line) !important;
  --body-text-color:var(--desk-text) !important;
  --body-text-color-subdued:var(--desk-muted) !important;
  color-scheme:dark !important;
  width:100% !important;
  max-width:none !important;
  margin:0 !important;
  padding:0 14px 22px !important;
  background:var(--desk-bg) !important;
  color:var(--desk-text) !important;
  font-family:Inter,Arial,sans-serif !important;
}
.terminal-header {
  min-height:58px;
  display:flex;
  align-items:center;
  gap:24px;
  background:#050706;
  padding:0 0 0 18px;
}
#global-header {
  align-items:center !important;
  gap:10px !important;
  margin:0 !important;
  padding:0 18px 0 0 !important;
  border-bottom:1px solid var(--desk-line);
  background:#050706;
}
#live-terminal-header {
  min-width:0 !important;
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
}
.terminal-brand {
  display:flex;
  align-items:baseline;
  gap:10px;
  min-width:205px;
  white-space:nowrap;
}
.terminal-brand strong {
  color:#fff;
  font-size:17px;
  letter-spacing:.18em;
}
.terminal-brand span {
  color:var(--desk-muted);
  font-size:10px;
  letter-spacing:.1em;
}
.market-clocks {
  display:flex;
  align-items:center;
  gap:0;
  border:1px solid var(--desk-line);
  border-radius:5px;
  overflow:hidden;
  margin-left:auto;
}
.market-clock {
  padding:8px 12px;
  color:var(--desk-muted);
  font:12px "IBM Plex Mono",Consolas,monospace;
  border-right:1px solid var(--desk-line);
  white-space:nowrap;
}
.market-clock:last-child { border-right:0; }
.market-clock b { color:var(--desk-text); font-weight:500; margin-left:5px; }
.market-dot {
  display:inline-block;
  width:7px;
  height:7px;
  border-radius:50%;
  background:var(--desk-green);
  box-shadow:0 0 7px rgba(88,213,112,.6);
  margin-right:4px;
}
.ticker-shell {
  position:relative;
  display:block;
  width:100%;
  max-width:100%;
  min-width:0;
  overflow:hidden;
  contain:paint;
  border-top:1px solid #202420;
  border-bottom:1px solid var(--desk-line);
  background:linear-gradient(90deg,#101310 0%,#171a17 50%,#101310 100%);
}
.ticker-shell::before,.ticker-shell::after {
  content:"";
  position:absolute;
  z-index:2;
  top:0;
  bottom:0;
  width:42px;
  pointer-events:none;
}
.ticker-shell::before { left:0; background:linear-gradient(90deg,#101310,transparent); }
.ticker-shell::after { right:0; background:linear-gradient(270deg,#101310,transparent); }
.ticker-track {
  display:flex;
  width:max-content;
  min-width:max-content;
  will-change:transform;
  animation:desk-ticker-scroll 42s linear infinite;
}
.ticker-shell:hover .ticker-track { animation-play-state:paused; }
.ticker-group { display:flex; flex:none; }
@keyframes desk-ticker-scroll {
  from { transform:translateX(0); }
  to { transform:translateX(-50%); }
}
.ticker-item {
  display:flex;
  gap:9px;
  align-items:center;
  padding:11px 26px;
  border-right:1px solid #222622;
  font:13px "IBM Plex Mono",Consolas,monospace;
}
.ticker-item b { color:var(--desk-yellow); font-family:Inter,Arial,sans-serif; }
.ticker-item .price { color:#d9d7d0; }
#market-ticker,
#market-ticker > div,
#market-ticker .html-container,
#market-ticker .prose {
  width:100% !important;
  max-width:100% !important;
  min-width:0 !important;
  overflow-x:hidden !important;
  overflow-y:hidden !important;
  scrollbar-width:none !important;
}
#market-ticker {
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
}
#market-ticker::-webkit-scrollbar,
#market-ticker *::-webkit-scrollbar {
  display:none !important;
  width:0 !important;
  height:0 !important;
}
.positive { color:var(--desk-green) !important; }
.negative { color:var(--desk-red) !important; }
.neutral { color:var(--desk-muted) !important; }
.command-row {
  align-items:center !important;
  justify-content:flex-end !important;
  min-height:34px !important;
  margin:7px 14px 3px !important;
}
.status-strip {
  min-height:35px;
  padding:8px 12px;
  border:1px solid var(--desk-line);
  border-radius:5px;
  background:var(--desk-panel);
  color:var(--desk-muted);
  font:11px "IBM Plex Mono",Consolas,monospace;
}
.status-strip b { color:var(--desk-text); font-weight:500; }
.status-ok { color:var(--desk-green); }
.status-warn { color:var(--desk-yellow); }
#refresh-button {
  flex:0 0 auto !important;
  width:112px !important;
  max-width:112px !important;
  min-width:112px !important;
  margin:0 !important;
}
#refresh-button button {
  min-height:32px !important;
  border-radius:4px !important;
  border:1px solid var(--desk-orange) !important;
  background:rgba(233,140,50,.10) !important;
  color:var(--desk-orange) !important;
  font-weight:700 !important;
  font-size:11px !important;
  letter-spacing:.02em !important;
}
#refresh-button button:hover {
  background:var(--desk-orange) !important;
  color:#080a08 !important;
}
#terminal-workspace { gap:14px !important; padding:5px 14px 0 !important; align-items:flex-start !important; }
#main-terminal { min-width:0; }
#desk-rail {
  min-width:290px;
  position:sticky;
  top:8px;
  align-self:flex-start;
}
.rail-panel, .terminal-panel {
  border:1px solid var(--desk-line) !important;
  border-radius:4px !important;
  background:var(--desk-panel) !important;
  overflow:hidden;
}
.rail-heading, .panel-heading {
  padding:10px 13px;
  border-bottom:1px solid var(--desk-line);
  color:#f6f3ec;
  font-size:13px;
  font-weight:700;
}
.desk-table { padding:4px 12px 8px; }
.desk-row {
  display:grid;
  grid-template-columns:1.35fr .8fr .72fr;
  gap:8px;
  align-items:center;
  min-height:36px;
  border-bottom:1px solid #252825;
  font:13px "IBM Plex Mono",Consolas,monospace;
}
.desk-row:last-child { border-bottom:0; }
.desk-row .label { color:#aeb8c5; font-family:Inter,Arial,sans-serif; }
.desk-row .value { color:#fff; text-align:right; }
.desk-row .move { text-align:right; }
.events-list { padding:5px 12px 10px; }
.rail-event {
  display:block;
  margin:0 -7px;
  padding:9px 7px;
  border-bottom:1px solid #252825;
  border-left:2px solid transparent;
  border-radius:2px;
  text-decoration:none !important;
  transition:background-color .15s ease,border-color .15s ease;
}
.rail-event:hover {
  background:#181b18;
  border-left-color:var(--desk-orange);
}
.rail-event:last-child { border-bottom:0; }
.rail-event time {
  display:block;
  color:var(--desk-orange);
  font:10px "IBM Plex Mono",Consolas,monospace;
  margin-bottom:4px;
}
.rail-event strong { display:block; color:#e8e5dd; font-size:12px; line-height:1.35; }
.rail-event small { color:var(--desk-muted); font-size:10px; }
.empty-rail { padding:20px 12px; color:var(--desk-muted); font-size:12px; }
.news-toolbar,
.tab-toolbar {
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:16px;
  margin-bottom:10px;
}
.news-toolbar h2,
.tab-toolbar h2 {
  margin:0;
  color:#f6f3ec;
  font-size:24px;
  letter-spacing:-.02em;
}
.news-toolbar p,
.tab-toolbar p {
  margin:4px 0 0;
  color:var(--desk-muted);
  font:10px "IBM Plex Mono",Consolas,monospace;
}
.overview-toolbar {
  flex:1 1 auto;
  width:100%;
  margin-bottom:10px;
  padding-bottom:10px;
  border-bottom:1px solid var(--desk-line);
}
.overview-toolbar span {
  display:inline-flex;
  align-items:center;
  gap:6px;
  color:var(--desk-green);
  font:9px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.05em;
  white-space:nowrap;
}
.overview-toolbar span::before {
  content:"";
  width:6px;
  height:6px;
  border-radius:50%;
  background:var(--desk-green);
  box-shadow:0 0 7px rgba(88,213,112,.55);
}
.overview-subhead {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  margin:15px 0 8px;
  padding-bottom:7px;
  border-bottom:1px solid var(--desk-line);
}
.overview-subhead strong {
  color:var(--desk-orange);
  font:700 10px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.overview-subhead span {
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
}
#news-grid-panel {
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
}
.news-grid {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:11px;
}
.news-card {
  min-width:0;
  overflow:hidden;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
  color:var(--desk-text) !important;
  text-decoration:none !important;
  transition:transform .16s ease,border-color .16s ease,background-color .16s ease;
}
.news-card:hover {
  transform:translateY(-2px);
  border-color:#555b56;
  background:#131713;
}
.news-card-visual {
  position:relative;
  height:142px;
  display:flex;
  align-items:center;
  justify-content:center;
  overflow:hidden;
  border-bottom:1px solid var(--desk-line);
  background:
    linear-gradient(135deg,rgba(233,140,50,.12),transparent 55%),
    repeating-linear-gradient(90deg,transparent 0,transparent 54px,rgba(255,255,255,.025) 55px),
    #171a18;
}
.news-card-visual::after {
  content:"";
  position:absolute;
  left:0;
  right:0;
  bottom:0;
  height:2px;
  background:var(--source-accent,var(--desk-orange));
}
.news-source-mark {
  color:#f2eee6;
  font:700 31px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.12em;
  text-shadow:0 0 22px color-mix(in srgb,var(--source-accent,var(--desk-orange)) 38%,transparent);
}
.news-source-official {
  position:absolute;
  top:11px;
  right:12px;
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.12em;
}
.source-fed { --source-accent:#70a0ff; }
.source-ecb { --source-accent:#e3ca58; }
.source-boe { --source-accent:#ef6a62; }
.source-boj { --source-accent:#58d570; }
.source-market { --source-accent:#e98c32; }
.news-card-copy { padding:11px 13px 13px; }
.news-card-meta {
  display:flex;
  align-items:center;
  gap:7px;
  min-width:0;
  margin-bottom:7px;
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
}
.news-card-source {
  overflow:hidden;
  color:var(--desk-yellow);
  text-overflow:ellipsis;
  white-space:nowrap;
}
.news-card-topic {
  flex:none;
  padding:2px 5px;
  border:1px solid #46504a;
  border-radius:2px;
  color:#b9d8c0;
  text-transform:uppercase;
  letter-spacing:.06em;
}
.news-card-time { margin-left:auto; flex:none; }
.news-card h3 {
  margin:0;
  color:#e9e6df;
  font-size:13px;
  line-height:1.4;
  font-weight:700;
}
.news-empty {
  grid-column:1/-1;
  padding:34px 18px;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
  color:var(--desk-muted);
  text-align:center;
  font:11px "IBM Plex Mono",Consolas,monospace;
}
.market-pulse {
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:8px;
  margin-bottom:10px;
}
#market-board-panel,#calendar-view-panel {
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
}
.pulse-card {
  min-width:0;
  padding:11px 12px;
  border:1px solid var(--desk-line);
  border-top:2px solid var(--desk-orange);
  border-radius:4px;
  background:var(--desk-panel);
}
.pulse-card > span {
  display:block;
  margin-bottom:7px;
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.pulse-card strong {
  display:block;
  overflow:hidden;
  color:#f0ede6;
  font-size:12px;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.pulse-card footer {
  display:flex !important;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  margin-top:5px;
  color:var(--desk-muted);
  font:11px "IBM Plex Mono",Consolas,monospace;
}
.market-board-grid {
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:9px;
}
.market-section {
  overflow:hidden;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
}
.market-section-header {
  display:flex;
  align-items:center;
  justify-content:space-between;
  min-height:38px;
  padding:0 12px;
  border-bottom:1px solid var(--desk-line);
  background:#141714;
}
.market-section-header h3 {
  margin:0;
  color:var(--desk-orange);
  font:700 11px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.07em;
  text-transform:uppercase;
}
.market-section-header span {
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
}
.market-line {
  display:grid;
  grid-template-columns:minmax(135px,1.5fr) minmax(92px,.8fr) minmax(105px,.9fr);
  gap:10px;
  align-items:center;
  min-height:54px;
  padding:7px 12px;
  border-bottom:1px solid #252825;
  color:var(--desk-text) !important;
  text-decoration:none !important;
  transition:background-color .15s ease;
}
.market-line:last-child { border-bottom:0; }
.market-line:hover { background:#181b18; }
.market-line.is-unavailable { opacity:.52; }
.market-name,.market-quote,.market-freshness { min-width:0; }
.market-name strong {
  display:block;
  overflow:hidden;
  color:#e5e2db;
  font-size:11px;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.market-name small {
  display:block;
  overflow:hidden;
  margin-top:3px;
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.market-quote { text-align:right; }
.market-quote strong {
  display:block;
  color:#fff;
  font:12px "IBM Plex Mono",Consolas,monospace;
}
.market-quote span {
  display:block;
  margin-top:3px;
  font:10px "IBM Plex Mono",Consolas,monospace;
}
.market-freshness { text-align:right; }
.market-freshness span {
  display:inline-block;
  padding:2px 5px;
  border:1px solid #3a413c;
  border-radius:2px;
  color:#aab0ab;
  font:8px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.04em;
}
.market-freshness .fresh-live { border-color:#326a40; color:var(--desk-green); }
.market-freshness .fresh-stale { border-color:#715f2a; color:var(--desk-yellow); }
.market-freshness time {
  display:block;
  overflow:hidden;
  margin-top:4px;
  color:#777d78;
  font:8px "IBM Plex Mono",Consolas,monospace;
  text-overflow:ellipsis;
  white-space:nowrap;
}
.calendar-next {
  display:grid;
  grid-template-columns:150px minmax(0,1fr) auto;
  gap:16px;
  align-items:center;
  min-height:112px;
  margin-bottom:12px;
  padding:16px;
  border:1px solid #554224;
  border-left:3px solid var(--desk-orange);
  border-radius:4px;
  background:linear-gradient(110deg,rgba(233,140,50,.09),transparent 58%),var(--desk-panel);
}
.calendar-countdown span {
  display:block;
  color:var(--desk-orange);
  font:9px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.08em;
  text-transform:uppercase;
}
.calendar-countdown strong {
  display:block;
  margin-top:7px;
  color:#fff;
  font:21px "IBM Plex Mono",Consolas,monospace;
}
.calendar-next-copy h2 { margin:0; color:#f0ede6; font-size:16px; line-height:1.35; }
.calendar-next-copy p { margin:6px 0 0; color:var(--desk-muted); font-size:10px; }
.calendar-open {
  padding:8px 10px;
  border:1px solid var(--desk-line);
  border-radius:3px;
  color:#d9d6ce !important;
  font:9px "IBM Plex Mono",Consolas,monospace;
  text-decoration:none !important;
  white-space:nowrap;
}
.calendar-open:hover { border-color:var(--desk-orange); color:#fff !important; }
.calendar-timeline { display:flex; flex-direction:column; gap:11px; }
.calendar-day {
  overflow:hidden;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
}
.calendar-day-heading {
  display:flex;
  align-items:center;
  justify-content:space-between;
  min-height:37px;
  padding:0 12px;
  border-bottom:1px solid var(--desk-line);
  background:#141714;
}
.calendar-day-heading strong { color:#f0ede6; font-size:11px; }
.calendar-day-heading span { color:var(--desk-muted); font:9px "IBM Plex Mono",Consolas,monospace; }
.calendar-event {
  display:grid;
  grid-template-columns:94px minmax(0,1fr) auto;
  gap:12px;
  align-items:center;
  min-height:65px;
  padding:9px 12px;
  border-bottom:1px solid #252825;
  border-left:2px solid #3d433f;
  color:var(--desk-text) !important;
  text-decoration:none !important;
  transition:background-color .15s ease;
}
.calendar-event:last-child { border-bottom:0; }
.calendar-event:hover { background:#181b18; }
.calendar-event.importance-high { border-left-color:var(--desk-orange); }
.calendar-event-time strong { display:block; color:#fff; font:11px "IBM Plex Mono",Consolas,monospace; }
.calendar-event-time span {
  display:inline-block;
  margin-top:5px;
  color:var(--desk-muted);
  font:8px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.06em;
}
.calendar-event-copy { min-width:0; }
.calendar-event-copy strong { display:block; color:#e8e5de; font-size:11px; line-height:1.35; }
.calendar-event-copy small { display:block; margin-top:4px; color:var(--desk-muted); font-size:9px; }
.calendar-event-data { display:flex; gap:7px; align-items:center; }
.calendar-stat {
  min-width:60px;
  padding-left:7px;
  border-left:1px solid var(--desk-line);
  text-align:right;
}
.calendar-stat span { display:block; color:#777d78; font:8px "IBM Plex Mono",Consolas,monospace; text-transform:uppercase; }
.calendar-stat strong { display:block; margin-top:3px; color:#e9e6df; font:10px "IBM Plex Mono",Consolas,monospace; }
.calendar-stat.is-pending strong { color:#69798a; font-size:8px; font-weight:500; }
.calendar-stat.is-highlight strong { color:var(--desk-blue); }
.calendar-provider {
  display:flex; align-items:center; justify-content:space-between; gap:14px;
  margin-bottom:9px; padding:9px 12px; border:1px solid var(--desk-line);
  border-radius:4px; background:var(--desk-panel); color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
}
.calendar-provider strong { color:var(--desk-blue); letter-spacing:.08em; }
.calendar-provider.is-live::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--desk-green); box-shadow:0 0 8px var(--desk-green); }
.calendar-provider.is-warning::before { content:""; width:7px; height:7px; border-radius:50%; background:var(--desk-yellow); }
.calendar-partial {
  margin-top:10px;
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
}
.calendar-empty {
  padding:35px 18px;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
  color:var(--desk-muted);
  text-align:center;
  font:11px "IBM Plex Mono",Consolas,monospace;
}
#terminal-tabs > .tab-nav {
  border-bottom:1px solid var(--desk-line) !important;
  background:var(--desk-bg) !important;
  gap:1px !important;
  flex-wrap:nowrap !important;
  overflow:visible !important;
}
#terminal-tabs > .tab-nav button {
  min-height:42px !important;
  min-width:0 !important;
  padding:0 10px !important;
  border-radius:4px 4px 0 0 !important;
  border:0 !important;
  background:transparent !important;
  color:#a8ada9 !important;
  font-size:12px !important;
  font-weight:650 !important;
}
#terminal-tabs > .tab-nav button.selected {
  color:#fff !important;
  background:#1a1d1b !important;
  box-shadow:inset 0 -2px 0 var(--desk-orange) !important;
}
#terminal-tabs > .tab-nav button:nth-child(4) { order:-1; color:#d8b488 !important; }
#terminal-tabs > .tab-nav button:nth-child(4)::before { content:"●"; color:var(--desk-orange); margin-right:7px; font-size:8px; }
.tabitem { padding-top:12px !important; }
.section-title {
  margin:0 0 8px;
  color:var(--desk-orange);
  font:700 12px "IBM Plex Mono",Consolas,monospace;
  letter-spacing:.07em;
  text-transform:uppercase;
}
.agent-hero {
  display:flex;
  align-items:flex-end;
  justify-content:space-between;
  gap:18px;
  margin-bottom:10px;
  padding:20px 22px;
  border:1px solid var(--desk-line);
  border-left:3px solid var(--desk-orange);
  border-radius:4px;
  background:linear-gradient(110deg,rgba(233,140,50,.15),rgba(233,140,50,.025) 58%),var(--desk-panel);
}
.agent-hero h2 { margin:0; color:#f3efe7; font-size:24px; letter-spacing:-.02em; }
.agent-hero p { margin:7px 0 0; color:#b8b3aa; font-size:12px; max-width:680px; }
.agent-hero span { color:var(--desk-green); font:9px "IBM Plex Mono",Consolas,monospace; white-space:nowrap; }
.agent-context-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px; margin:0 0 10px; }
.agent-context-card { min-height:62px; padding:10px 12px; border:1px solid var(--desk-line); border-radius:4px; background:var(--desk-panel); }
.agent-context-card span { display:block; color:var(--desk-muted); font:8px "IBM Plex Mono",Consolas,monospace; letter-spacing:.08em; text-transform:uppercase; }
.agent-context-card strong { display:block; margin-top:6px; color:var(--desk-text); font-size:11px; line-height:1.3; }
.agent-context-card:first-child { border-color:rgba(233,140,50,.55); }
.agent-context-card:first-child strong { color:var(--desk-orange); }
.agent-actions { gap:7px !important; margin-bottom:9px !important; }
.agent-actions button {
  min-height:38px !important;
  border:1px solid var(--desk-line) !important;
  border-radius:4px !important;
  background:var(--desk-panel-2) !important;
  color:#ddd9d1 !important;
  font-size:10px !important;
}
.agent-actions button:hover { border-color:var(--desk-orange) !important; color:#fff !important; }
.agent-query-panel { padding:12px !important; }
.agent-answer-panel { min-height:500px; border-top:2px solid var(--desk-orange) !important; }
.agent-answer-panel h2 { color:var(--desk-orange) !important; font-size:13px !important; letter-spacing:.04em; }
.agent-answer-panel h3 { color:var(--desk-yellow) !important; font-size:12px !important; }
.agent-note {
  color:var(--desk-muted);
  font:9px "IBM Plex Mono",Consolas,monospace;
  margin:2px 0 10px;
}
.agent-product-note { margin:12px 0 0; padding:10px 12px; border-left:2px solid var(--desk-orange); background:rgba(233,140,50,.05); color:#aaa69e; font:9px/1.55 "IBM Plex Mono",Consolas,monospace; }
#desk-profile-select {
  flex:0 0 160px !important;
  width:160px !important;
  max-width:160px !important;
  min-width:160px !important;
  align-self:center !important;
  justify-content:center !important;
  margin:0 !important;
  padding:0 !important;
  gap:0 !important;
  border:0 !important;
  background:transparent !important;
}
#desk-profile-select::before { content:none !important; }
#desk-profile-select .desk-lens-control {
  padding:0 !important;
  margin:0 !important;
  min-height:32px !important;
  border:1px solid var(--desk-line) !important;
  border-radius:4px !important;
  background:var(--desk-panel-2) !important;
  box-shadow:none !important;
}
#desk-profile-select .wrap,
#desk-profile-select .wrap-inner,
#desk-profile-select .secondary-wrap,
#desk-profile-select .input-container,
#desk-profile-select [role="combobox"] {
  min-height:30px !important;
  padding:0 !important;
  border:0 !important;
  background:transparent !important;
  box-shadow:none !important;
  align-items:center !important;
}
#desk-profile-select input {
  height:30px !important;
  min-height:30px !important;
  padding:0 8px !important;
  border:0 !important;
  background:transparent !important;
  text-align:center !important;
  color:var(--desk-text) !important;
  font:600 11px Inter,Arial,sans-serif !important;
}
#desk-profile-select:focus-within .desk-lens-control { border-color:var(--desk-orange) !important; }
#desk-profile-select svg { color:var(--desk-muted) !important; }
.rag-shell { margin-top:12px; padding:13px; border:1px solid var(--desk-line); border-radius:4px; background:var(--desk-panel); }
.rag-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; margin-bottom:10px; }
.rag-header h3 { margin:0; color:#eef5ff; font-size:13px; }
.rag-header p { margin:4px 0 0; color:var(--desk-muted); font-size:10px; }
.rag-count { padding:5px 8px; border:1px solid var(--desk-blue); border-radius:3px; color:var(--desk-blue); font:9px "IBM Plex Mono",Consolas,monospace; white-space:nowrap; }
.rag-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; }
.rag-doc { display:block; padding:10px; border:1px solid var(--desk-line); border-radius:4px; background:var(--desk-panel-2); text-decoration:none !important; transition:border-color .15s ease,transform .15s ease; }
.rag-doc:hover { border-color:var(--desk-blue); transform:translateY(-1px); }
.rag-doc strong { display:block; color:#e9f1fb; font-size:10px; line-height:1.35; }
.rag-doc span { display:block; margin-top:5px; color:var(--desk-muted); font:8px "IBM Plex Mono",Consolas,monospace; }
.rag-doc em { color:var(--desk-blue); font-style:normal; }
.rag-local { border-left:2px solid var(--desk-blue); }
.rag-dynamic { border-left:2px solid var(--desk-green); }
.rag-open { float:right; color:var(--desk-blue); font:8px "IBM Plex Mono",Consolas,monospace; letter-spacing:.06em; }
.rag-manager { margin-top:8px !important; border-color:var(--desk-line) !important; background:var(--desk-panel) !important; }
.snapshot-time {
  color:var(--desk-muted);
  font:10px "IBM Plex Mono",Consolas,monospace;
  margin:2px 0 8px;
}
.kpi-grid {
  display:grid;
  grid-template-columns:repeat(6,minmax(105px,1fr));
  gap:7px;
  margin-bottom:9px;
}
.kpi {
  min-height:83px;
  padding:11px 12px;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
  display:flex;
  flex-direction:column;
}
.kpi span,.kpi small { color:var(--desk-muted); font-size:11px; }
.kpi strong {
  color:#fff;
  font:17px "IBM Plex Mono",Consolas,monospace;
  margin:6px 0 4px;
}
.move-grid {
  display:grid;
  grid-template-columns:repeat(3,minmax(180px,1fr));
  gap:7px;
  margin-bottom:9px;
}
.move-card {
  padding:11px 12px;
  border:1px solid var(--desk-line);
  border-radius:4px;
  background:var(--desk-panel);
}
.move-card h4 { margin:0 0 6px; color:var(--desk-yellow); font-size:12px; }
.move-card p { margin:0 0 5px; color:#dedbd3; font-size:12px; }
.move-card small { color:var(--desk-muted); font-size:10px; }
.terminal-copy {
  border:1px solid var(--desk-line) !important;
  border-radius:4px !important;
  background:var(--desk-panel) !important;
  padding:5px 16px !important;
}
.terminal-copy .prose { max-width:none !important; font-size:12px !important; line-height:1.48 !important; }
.terminal-copy .prose h2 { color:#fff !important; font-size:18px !important; margin-top:10px !important; }
.terminal-copy .prose h3 { color:var(--desk-orange) !important; font-size:12px !important; text-transform:uppercase; letter-spacing:.05em; }
.terminal-form, .terminal-output {
  border:1px solid var(--desk-line) !important;
  border-radius:4px !important;
  background:var(--desk-panel) !important;
  padding:12px !important;
}
.gradio-container .block {
  --block-background-fill:var(--desk-panel);
  --block-border-color:var(--desk-line);
  --block-label-background-fill:var(--desk-panel);
}
.gradio-container button { border-radius:4px !important; }
.gradio-container input,.gradio-container textarea,.gradio-container select {
  background:var(--desk-field) !important;
  border-color:var(--desk-line) !important;
  color:var(--desk-text) !important;
}
.gradio-container .desk-input {
  background:transparent !important;
  border-color:transparent !important;
  box-shadow:none !important;
}
.gradio-container .desk-input .wrap,
.gradio-container .desk-input .wrap-inner,
.gradio-container .desk-input .secondary-wrap,
.gradio-container .desk-input .input-container,
.gradio-container .desk-input [role="combobox"] {
  background:var(--desk-field) !important;
  border-color:#363c37 !important;
  border-radius:4px !important;
  color:var(--desk-text) !important;
  box-shadow:none !important;
}
.gradio-container .desk-input:hover .wrap,
.gradio-container .desk-input:hover .wrap-inner,
.gradio-container .desk-input:hover .secondary-wrap,
.gradio-container .desk-input:hover .input-container {
  background:var(--desk-field-hover) !important;
}
.gradio-container .desk-input:focus-within .wrap,
.gradio-container .desk-input:focus-within .wrap-inner,
.gradio-container .desk-input:focus-within .secondary-wrap,
.gradio-container .desk-input:focus-within .input-container {
  border-color:var(--desk-orange) !important;
}
.gradio-container .desk-input input,
.gradio-container .desk-input textarea,
.gradio-container .desk-input select {
  background:var(--desk-field) !important;
  border:0 !important;
  outline:0 !important;
  box-shadow:none !important;
  color:var(--desk-text) !important;
}
.gradio-container .desk-input:hover input,
.gradio-container .desk-input:hover textarea,
.gradio-container .desk-input:hover select {
  background:var(--desk-field-hover) !important;
}
.gradio-container .desk-input input::placeholder,
.gradio-container .desk-input textarea::placeholder {
  color:#788397 !important;
  opacity:1 !important;
}
.gradio-container .desk-input svg {
  color:#d6d8d5 !important;
}
.gradio-container label span {
  color:var(--desk-muted) !important;
  font-size:11px !important;
  letter-spacing:.03em;
}
.gradio-container table { font-family:"IBM Plex Mono",Consolas,monospace !important; }
.gradio-container .plot-container { background:var(--desk-panel) !important; }
footer { display:none !important; }
@media(max-width:1180px) {
  #terminal-workspace { flex-direction:column !important; }
  #desk-rail { position:static; width:100%; }
  .market-clocks { display:none; }
  .kpi-grid { grid-template-columns:repeat(3,1fr); }
}
@media(max-width:720px) {
  .gradio-container { padding:0 7px 15px !important; }
  .terminal-header { padding:0 10px; }
  .terminal-brand span { display:none; }
  .ticker-item { padding:9px 14px; }
  #terminal-workspace { padding:4px 4px 0 !important; }
  .kpi-grid { grid-template-columns:repeat(2,1fr); }
  .move-grid { grid-template-columns:1fr; }
  .news-grid { grid-template-columns:1fr; }
  .news-card-visual { height:112px; }
  .market-pulse { grid-template-columns:repeat(2,minmax(0,1fr)); }
  .market-board-grid { grid-template-columns:1fr; }
  .market-line { grid-template-columns:minmax(120px,1.4fr) minmax(88px,.8fr); }
  .market-freshness { display:none; }
  .calendar-next { grid-template-columns:1fr; gap:9px; }
  .calendar-event { grid-template-columns:76px minmax(0,1fr); }
  .calendar-event-data { grid-column:2; }
  #desk-profile-select { min-width:130px; }
  .rag-grid { grid-template-columns:1fr; }
  .agent-context-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
  #terminal-tabs > .tab-nav button { padding:0 7px !important; font-size:11px !important; }
}
@media(prefers-reduced-motion:reduce) {
  .ticker-track { animation-duration:90s; }
}
"""


THEME_VARIANT = "orange"

if THEME_VARIANT == "blue":
    _BLUE_REPLACEMENTS = {
        "#070908": "#071019",
        "#0f1210": "#0c1722",
        "#141714": "#122130",
        "#1c201d": "#182b3a",
        "#242925": "#20384a",
        "#2a2e2b": "#2b4052",
        "#eeeae2": "#eaf2f8",
        "#8c918d": "#8ea2b3",
        "#e98c32": "#35b6d4",
        "#e3ca58": "#76d7e8",
        "#7892ff": "#6ea8fe",
        "#050706": "#050d14",
        "#101310": "#0b1721",
        "#171a17": "#122634",
        "#080a08": "#041014",
        "rgba(233,140,50": "rgba(53,182,212",
    }
    for _old_color, _new_color in _BLUE_REPLACEMENTS.items():
        CSS = CSS.replace(_old_color, _new_color)


_THEME_COLORS = {
    "orange": {
        "primary": "orange",
        "secondary": "amber",
        "background": "#070908",
        "panel": "#0f1210",
        "panel_2": "#141714",
        "field": "#1c201d",
        "field_hover": "#242925",
        "line": "#2a2e2b",
        "accent": "#e98c32",
        "text": "#eeeae2",
        "muted": "#8c918d",
        "button_text": "#080a08",
    },
    "blue": {
        "primary": "cyan",
        "secondary": "blue",
        "background": "#071019",
        "panel": "#0c1722",
        "panel_2": "#122130",
        "field": "#182b3a",
        "field_hover": "#20384a",
        "line": "#2b4052",
        "accent": "#35b6d4",
        "text": "#eaf2f8",
        "muted": "#8ea2b3",
        "button_text": "#041014",
    },
}
_ACTIVE_THEME = _THEME_COLORS[THEME_VARIANT]


APP_THEME = gr.themes.Base(
    primary_hue=_ACTIVE_THEME["primary"],
    secondary_hue=_ACTIVE_THEME["secondary"],
    neutral_hue="zinc",
).set(
    body_background_fill=_ACTIVE_THEME["background"],
    body_background_fill_dark=_ACTIVE_THEME["background"],
    background_fill_primary=_ACTIVE_THEME["panel"],
    background_fill_primary_dark=_ACTIVE_THEME["panel"],
    background_fill_secondary=_ACTIVE_THEME["panel_2"],
    background_fill_secondary_dark=_ACTIVE_THEME["panel_2"],
    block_background_fill=_ACTIVE_THEME["panel"],
    block_background_fill_dark=_ACTIVE_THEME["panel"],
    block_label_background_fill=_ACTIVE_THEME["panel"],
    block_label_background_fill_dark=_ACTIVE_THEME["panel"],
    panel_background_fill=_ACTIVE_THEME["panel"],
    panel_background_fill_dark=_ACTIVE_THEME["panel"],
    input_background_fill=_ACTIVE_THEME["field"],
    input_background_fill_dark=_ACTIVE_THEME["field"],
    input_background_fill_focus=_ACTIVE_THEME["field"],
    input_background_fill_hover=_ACTIVE_THEME["field_hover"],
    input_background_fill_hover_dark=_ACTIVE_THEME["field_hover"],
    input_border_color=_ACTIVE_THEME["line"],
    input_border_color_dark=_ACTIVE_THEME["line"],
    input_border_color_focus=_ACTIVE_THEME["accent"],
    input_border_color_focus_dark=_ACTIVE_THEME["accent"],
    body_text_color=_ACTIVE_THEME["text"],
    body_text_color_dark=_ACTIVE_THEME["text"],
    body_text_color_subdued=_ACTIVE_THEME["muted"],
    body_text_color_subdued_dark=_ACTIVE_THEME["muted"],
    border_color_primary=_ACTIVE_THEME["line"],
    border_color_primary_dark=_ACTIVE_THEME["line"],
    button_primary_background_fill=_ACTIVE_THEME["accent"],
    button_primary_background_fill_dark=_ACTIVE_THEME["accent"],
    button_primary_text_color=_ACTIVE_THEME["button_text"],
    button_primary_text_color_dark=_ACTIVE_THEME["button_text"],
)


METHODOLOGY = """## Methodology and sources

The application combines deterministic market calculations with a controlled research workflow. The agent classifies each question, selects bounded tools, registers evidence and then asks the configured model to synthesize an answer.

### Data

- Public intraday quotes for FX, equities, volatility and commodity futures.
- U.S. Treasury official daily par-yield closes.
- FRED for macro, policy, credit and historical series.
- DBnomics only as a transparent mirror when FRED is unreachable.
- Federal Reserve, ECB, Bank of England, Bank of Japan, BLS and BEA official sources.

### Controls

Observed market moves are separated from interpretation. Missing data remain unavailable. External text is treated as untrusted input. Secrets stay in environment variables and session memory is not intentionally persisted.
"""


ABOUT = """## About

AI Sales Desk Assistant is a public-source market intelligence prototype for FICC and cross-asset Sales workflows.

Designed and developed by Théo Caruana, Financial Markets & Investments master's student, drawing on experience in Fixed Income and Derivatives Brokerage, Liquidity Sales and Global Markets Risk.

This application is decision support, not investment advice. Client-facing text requires human approval.
"""


@dataclass
class Snapshot:
    points: list[MarketPoint]
    news: list[NewsItem]
    events: list[CalendarEvent]
    status: dict[str, object]
    news_errors: list[str]
    calendar_error: str | None
    expectations_status: str = "Market expectations loading"


class SnapshotStore:
    def __init__(self):
        self.collector = MarketDataCollector()
        self._lock = threading.RLock()
        self._refresh_lock = threading.Lock()
        points = empty_points()
        self._snapshot = Snapshot(
            points, [], [], service_summary(points), [], "Live calendar is loading.", "Market expectations loading",
        )

    def _load(self) -> Snapshot:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="live-source") as pool:
            market_future = pool.submit(load_snapshot, self.collector)
            news_future = pool.submit(load_news)
            calendar_future = pool.submit(load_calendar)
            expectations_future = pool.submit(fetch_market_expectations)
            points, status = market_future.result()
            news, news_errors = news_future.result()
            events, calendar_error = calendar_future.result()
            market_events, expectations_status = expectations_future.result()
        events = enrich_events(events, points, market_events)
        return Snapshot(points, news, events, status, news_errors, calendar_error, expectations_status)

    def refresh(self) -> Snapshot:
        with self._refresh_lock:
            snapshot = self._load()
            with self._lock:
                self._snapshot = snapshot
            return snapshot

    def refresh_intraday(self) -> Snapshot:
        """Refresh quote-capable series only; preserve FRED, calendar, news and reports."""
        if not self._refresh_lock.acquire(blocking=False):
            return self.get()
        try:
            current = self.get()
            points = self.collector.refresh_intraday(current.points)
            snapshot = Snapshot(
                points, current.news, current.events, service_summary(points),
                current.news_errors, current.calendar_error, current.expectations_status,
            )
            with self._lock:
                self._snapshot = snapshot
            return snapshot
        finally:
            self._refresh_lock.release()

    def refresh_macro(self) -> Snapshot:
        """Refresh the market/macro layer without reloading news, calendar or reports."""
        if not self._refresh_lock.acquire(blocking=False):
            return self.get()
        try:
            current = self.get()
            points, status = load_snapshot(self.collector)
            market_events, expectations_status = fetch_market_expectations()
            events = enrich_events(current.events, points, market_events)
            snapshot = Snapshot(points, current.news, events, status, current.news_errors, current.calendar_error, expectations_status)
            with self._lock:
                self._snapshot = snapshot
            return snapshot
        finally:
            self._refresh_lock.release()

    def get(self) -> Snapshot:
        with self._lock:
            return self._snapshot


def _market_clock(label: str, zone: str, now: datetime) -> str:
    try:
        market_time = now.astimezone(ZoneInfo(zone)).strftime("%H:%M")
    except ZoneInfoNotFoundError:
        market_time = now.strftime("%H:%M")
    return (
        '<span class="market-clock"><i class="market-dot"></i>'
        f'{html.escape(label)} <b>{html.escape(market_time)}</b></span>'
    )


def _header_html() -> str:
    now = datetime.now(timezone.utc)
    clocks = "".join([
        _market_clock("NY", "America/New_York", now),
        _market_clock("LDN", "Europe/London", now),
        _market_clock("PAR", "Europe/Paris", now),
        _market_clock("TYO", "Asia/Tokyo", now),
    ])
    return (
        '<header class="terminal-header">'
        '<div class="terminal-brand"><strong>AI SALES COPILOT</strong><span>MARKET INTELLIGENCE</span></div>'
        f'<div class="market-clocks">{clocks}</div>'
        '</header>'
    )


def _move_class(point: MarketPoint | None) -> str:
    if point is None or point.change in (None, 0):
        return "neutral"
    return "positive" if point.change > 0 else "negative"


def _ticker_html(points: list[MarketPoint]) -> str:
    values = point_map(points)
    instruments = [
        ("US 2Y", "DGS2"),
        ("US 10Y", "DGS10"),
        ("EUR/USD", "DEXUSEU"),
        ("USD/JPY", "DEXJPUS"),
        ("S&P 500", "SP500"),
        ("VIX", "VIXCLS"),
        ("BRENT", "DCOILBRENTEU"),
        ("GOLD", "GOLDAMGBD228NLBM"),
        ("HY OAS", "BAMLH0A0HYM2"),
    ]
    items: list[str] = []
    for label, series_id in instruments:
        point = values.get(series_id)
        value = format_value(point) if point and point.value is not None else "N/A"
        move = format_change(point) if point and point.value is not None else ""
        items.append(
            '<div class="ticker-item">'
            f'<b>{html.escape(label)}</b>'
            f'<span class="price">{html.escape(value)}</span>'
            f'<span class="{_move_class(point)}">{html.escape(move)}</span>'
            '</div>'
        )
    group = "".join(items)
    return (
        '<div class="ticker-shell" aria-label="Live market ticker">'
        '<div class="ticker-track">'
        f'<div class="ticker-group">{group}</div>'
        f'<div class="ticker-group" aria-hidden="true">{group}</div>'
        '</div></div>'
    )


def _desk_rail_html(points: list[MarketPoint]) -> str:
    values = point_map(points)
    spreads = curve_spreads(points)
    instruments = [
        ("VIX", values.get("VIXCLS")),
        ("S&P 500", values.get("SP500")),
        ("US 10Y", values.get("DGS10")),
        ("EUR/USD", values.get("DEXUSEU")),
        ("USD/JPY", values.get("DEXJPUS")),
        ("Brent", values.get("DCOILBRENTEU")),
        ("Gold", values.get("GOLDAMGBD228NLBM")),
        ("US HY", values.get("BAMLH0A0HYM2")),
    ]
    rows: list[str] = []
    for label, point in instruments:
        value = format_value(point) if point and point.value is not None else "N/A"
        move = format_change(point) if point and point.value is not None else ""
        rows.append(
            '<div class="desk-row">'
            f'<span class="label">{html.escape(label)}</span>'
            f'<span class="value">{html.escape(value)}</span>'
            f'<span class="move {_move_class(point)}">{html.escape(move)}</span>'
            '</div>'
        )
    spread = spreads.get("US 2s10s")
    spread_value = "N/A" if spread is None else f"{spread:+.1f} bp"
    rows.insert(
        3,
        '<div class="desk-row">'
        '<span class="label">2s10s</span>'
        f'<span class="value {"positive" if spread is not None and spread >= 0 else "negative"}">{html.escape(spread_value)}</span>'
        '<span class="move neutral"></span>'
        '</div>',
    )
    return (
        '<section class="rail-panel"><div class="rail-heading">Desk</div>'
        f'<div class="desk-table">{"".join(rows)}</div></section>'
    )


def _market_move_magnitude(point: MarketPoint) -> float:
    if point.change is None:
        return -1.0
    if point.category in {"Rates", "Policy", "Credit"} and point.unit == "%":
        return abs(point.change * 100)
    if point.previous not in (None, 0):
        return abs(point.change / point.previous * 100)
    return abs(point.change)


def _market_freshness(point: MarketPoint) -> tuple[str, str]:
    status = (point.status or "").lower()
    source = (point.source_name or "").lower()
    if point.value is None:
        return "UNAVAILABLE", ""
    if "intraday" in status or "yahoo" in source:
        return "LIVE", "fresh-live"
    if "stale" in status:
        return "STALE", "fresh-stale"
    return "OFFICIAL CLOSE", ""


def _market_pulse_html(points: list[MarketPoint]) -> str:
    groups = [
        ("Rates move", {"Rates", "Policy", "Credit"}),
        ("FX move", {"FX"}),
        ("Risk move", {"Risk"}),
        ("Commodity move", {"Commodities"}),
    ]
    cards: list[str] = []
    for heading, categories in groups:
        candidates = [point for point in points if point.category in categories and point.value is not None]
        point = max(candidates, key=_market_move_magnitude) if candidates else None
        if point is None:
            label, value, move, move_class = "Unavailable", "N/A", "", "neutral"
        else:
            label = point.label
            value = format_value(point)
            move = format_change(point)
            move_class = _move_class(point)
        cards.append(
            '<div class="pulse-card">'
            f'<span>{html.escape(heading)}</span>'
            f'<strong>{html.escape(label)}</strong>'
            '<footer>'
            f'<b>{html.escape(value)}</b>'
            f'<em class="{move_class}">{html.escape(move)}</em>'
            '</footer></div>'
        )
    return f'<div class="market-pulse">{"".join(cards)}</div>'


def _market_line_html(point: MarketPoint) -> str:
    available = point.value is not None
    value = format_value(point) if available else "Unavailable"
    move = format_change(point) if available else ""
    freshness, freshness_class = _market_freshness(point)
    date_text = point.date or "No observation"
    source_url = html.escape(point.source_url, quote=True)
    return (
        f'<a class="market-line{"" if available else " is-unavailable"}" href="{source_url}" '
        'target="_blank" rel="noopener noreferrer">'
        '<div class="market-name">'
        f'<strong>{html.escape(point.label)}</strong>'
        f'<small>{html.escape(point.source_name)}</small>'
        '</div>'
        '<div class="market-quote">'
        f'<strong>{html.escape(value)}</strong>'
        f'<span class="{_move_class(point)}">{html.escape(move)}</span>'
        '</div>'
        '<div class="market-freshness">'
        f'<span class="{freshness_class}">{html.escape(freshness)}</span>'
        f'<time>{html.escape(date_text)}</time>'
        '</div></a>'
    )


def _markets_html(points: list[MarketPoint]) -> str:
    sections = [
        ("Rates", {"Rates"}),
        ("FX", {"FX"}),
        ("Policy & Credit", {"Policy", "Credit"}),
        ("Equities & Volatility", {"Risk"}),
        ("Macro", {"Macro"}),
        ("Commodities", {"Commodities"}),
    ]
    panels: list[str] = []
    for title, categories in sections:
        section_points = [point for point in points if point.category in categories]
        rows = "".join(_market_line_html(point) for point in section_points)
        if not rows:
            rows = '<div class="calendar-empty">No market observation available.</div>'
        panels.append(
            '<section class="market-section">'
            '<header class="market-section-header">'
            f'<h3>{html.escape(title)}</h3><span>{len(section_points)} instruments</span>'
            '</header>'
            f'{rows}</section>'
        )
    return _market_pulse_html(points) + f'<div class="market-board-grid">{"".join(panels)}</div>'


def _calendar_event_datetime(event: CalendarEvent) -> datetime:
    try:
        time_text = event.time.replace("UTC", "").strip()[:5]
        return datetime.strptime(f"{event.date} {time_text}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.strptime(event.date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return datetime.max.replace(tzinfo=timezone.utc)


def _calendar_countdown(event_time: datetime, now: datetime) -> str:
    if event_time < now:
        return "SCHEDULED"
    seconds = max(0, int((event_time - now).total_seconds()))
    if event_time.date() == now.date():
        if seconds < 3600:
            return f"IN {max(1, seconds // 60)} MIN"
        return f"IN {seconds // 3600}H"
    days = (event_time.date() - now.date()).days
    if days == 1:
        return "TOMORROW"
    return f"IN {days} DAYS"


def _calendar_day_label(event_time: datetime, now: datetime) -> str:
    if event_time.date() == now.date():
        return "Today"
    if event_time.date() == (now + timedelta(days=1)).date():
        return "Tomorrow"
    return event_time.strftime("%A %d %B")


def _calendar_metric_available(value: str) -> bool:
    return str(value or "").strip().lower() not in {"", "-", "n/a", "none", "unavailable"}


def _calendar_event_html(event: CalendarEvent) -> str:
    stats: list[str] = []
    core_metrics = (
        ("Previous", event.previous),
        ("Consensus", event.consensus),
        ("Actual", event.actual),
    )
    for label, value in core_metrics:
        display = str(value) if _calendar_metric_available(value) else "Awaiting release"
        state = "" if _calendar_metric_available(value) else " is-pending"
        stats.append(
            f'<div class="calendar-stat{state}">'
            f'<span>{html.escape(label)}</span><strong>{html.escape(display)}</strong>'
            '</div>'
        )
    for label, value in (("Surprise", surprise_text(event)), ("Reaction", event.market_reaction)):
        if _calendar_metric_available(value):
            stats.append('<div class="calendar-stat is-highlight">'
                         f'<span>{html.escape(label)}</span><strong>{html.escape(str(value))}</strong></div>')
    region_codes = {
        "United States": "US",
        "Euro Area": "EU",
        "United Kingdom": "UK",
        "Japan": "JP",
    }
    region = region_codes.get(event.region, event.region)
    importance_class = " importance-high" if event.importance.lower() == "high" else ""
    return (
        f'<a class="calendar-event{importance_class}" href="{html.escape(event.url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">'
        '<div class="calendar-event-time">'
        f'<strong>{html.escape(event.time)}</strong>'
        f'<span>{html.escape(region)} · {html.escape(event.importance.upper())}</span>'
        '</div>'
        '<div class="calendar-event-copy">'
        f'<strong>{html.escape(event.title)}</strong>'
        f'<small>{html.escape(event.institution)} · {html.escape(event.event_type)}</small>'
        '</div>'
        f'<div class="calendar-event-data">{"".join(stats)}</div>'
        '</a>'
    )


def _calendar_html(events: list[CalendarEvent], error: str | None = None, expectations_status: str = "") -> str:
    if not events:
        message = error or "No upcoming official event is available."
        return f'<div class="calendar-empty">{html.escape(message)}</div>'

    now = datetime.now(timezone.utc)
    ordered = sorted(events, key=_calendar_event_datetime)
    next_event = next(
        (event for event in ordered if _calendar_event_datetime(event) >= now - timedelta(hours=2)),
        ordered[0],
    )
    next_time = _calendar_event_datetime(next_event)
    next_card = (
        '<section class="calendar-next">'
        '<div class="calendar-countdown"><span>Next event</span>'
        f'<strong>{html.escape(_calendar_countdown(next_time, now))}</strong></div>'
        '<div class="calendar-next-copy">'
        f'<h2>{html.escape(next_event.title)}</h2>'
        f'<p>{html.escape(next_event.date)} · {html.escape(next_event.time)} · '
        f'{html.escape(next_event.institution)} · {html.escape(next_event.importance)} importance</p>'
        '</div>'
        f'<a class="calendar-open" href="{html.escape(next_event.url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer">OPEN SOURCE</a>'
        '</section>'
    )

    grouped: dict[str, list[CalendarEvent]] = {}
    for event in ordered:
        grouped.setdefault(event.date, []).append(event)
    days: list[str] = []
    for event_date, day_events in grouped.items():
        event_time = _calendar_event_datetime(day_events[0])
        label = _calendar_day_label(event_time, now)
        rows = "".join(_calendar_event_html(event) for event in day_events)
        days.append(
            '<section class="calendar-day">'
            '<header class="calendar-day-heading">'
            f'<strong>{html.escape(label)}</strong>'
            f'<span>{html.escape(event_date)} · {len(day_events)} events</span>'
            '</header>'
            f'{rows}</section>'
        )
    provider_class = "is-live" if expectations_status.startswith("Market expectations:") else "is-warning"
    provider = (
        f'<div class="calendar-provider {provider_class}"><strong>EXPECTATIONS FEED</strong>'
        f'<span>{html.escape(expectations_status or "Official schedule only")}</span></div>'
    )
    partial = f'<div class="calendar-partial">{html.escape(error)}</div>' if error else ""
    return provider + next_card + f'<div class="calendar-timeline">{"".join(days)}</div>' + partial


def _events_rail_html(events: list[CalendarEvent]) -> str:
    if not events:
        body = '<div class="empty-rail">No upcoming official event is available.</div>'
    else:
        rows = []
        for event in events[:5]:
            event_url = html.escape(event.url, quote=True)
            rows.append(
                f'<a class="rail-event" href="{event_url}" target="_blank" rel="noopener noreferrer">'
                f'<time>{html.escape(event.date)} | {html.escape(event.time)}</time>'
                f'<strong>{html.escape(event.title)}</strong>'
                f'<small>{html.escape(event.institution)}</small>'
                '</a>'
            )
        body = f'<div class="events-list">{"".join(rows)}</div>'
    return f'<section class="rail-panel"><div class="rail-heading">Upcoming events</div>{body}</section>'


def _news_source_identity(source: str) -> tuple[str, str]:
    lowered = source.lower()
    if "federal reserve" in lowered:
        return "FED", "source-fed"
    if "european central bank" in lowered:
        return "ECB", "source-ecb"
    if "bank of england" in lowered:
        return "BOE", "source-boe"
    if "bank of japan" in lowered:
        return "BOJ", "source-boj"
    initials = "".join(word[0] for word in source.split() if word)[:4].upper() or "NEWS"
    return initials, "source-market"


def _news_age(published: str) -> str:
    try:
        observed = datetime.strptime(published, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return published or "time unavailable"
    seconds = max(0, int((datetime.now(timezone.utc) - observed).total_seconds()))
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m ago"
    if seconds < 86_400:
        return f"{seconds // 3600}h ago"
    if seconds < 604_800:
        return f"{seconds // 86_400}d ago"
    return observed.strftime("%d %b %Y")


def _news_cards_html(
    items: list[NewsItem],
    errors: list[str],
    official: bool = True,
) -> str:
    selected = list(items)
    if not selected:
        if errors:
            message = "News sources are temporarily unavailable."
        else:
            message = "Recent official news is loading."
        return f'<div class="news-grid"><div class="news-empty">{html.escape(message)}</div></div>'

    cards: list[str] = []
    for item in selected:
        mark, source_class = _news_source_identity(item.source)
        cards.append(
            f'<a class="news-card" href="{html.escape(item.url, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">'
            f'<div class="news-card-visual {source_class}">'
            f'<span class="news-source-official">{"OFFICIAL SOURCE" if official else "VIA GOOGLE NEWS"}</span>'
            f'<span class="news-source-mark">{html.escape(mark)}</span>'
            '</div>'
            '<div class="news-card-copy">'
            '<div class="news-card-meta">'
            f'<span class="news-card-source">{html.escape(item.source)}</span>'
            f'<span class="news-card-topic">{html.escape(item.category)}</span>'
            f'<time class="news-card-time">{html.escape(_news_age(item.published))}</time>'
            '</div>'
            f'<h3>{html.escape(item.title)}</h3>'
            '</div></a>'
        )
    return f'<div class="news-grid">{"".join(cards)}</div>'


def _headlines_html(items: list[NewsItem]) -> str:
    fresh = recent_news(items)
    # Lead with policy/macro catalysts, then broad market coverage. No LLM call.
    priority = ("rate", "inflation", "payroll", "fomc", "ecb", "fed", "yield", "oil", "stocks", "markets")
    fresh.sort(key=lambda item: (any(term in item.title.casefold() for term in priority), item.published), reverse=True)
    chosen = fresh[:5]
    rows = []
    for item in chosen:
        title = item.title if len(item.title) <= 145 else item.title[:142].rsplit(" ", 1)[0] + "..."
        rows.append(
            f'<a class="headline-row" href="{html.escape(item.url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<strong>{html.escape(title)}</strong><span>{html.escape(item.source)} · {html.escape(_news_age(item.published))}</span></a>'
        )
    content = "".join(rows) or '<div class="news-empty">No verified publication timestamps within the past 48 hours. Older headlines are excluded.</div>'
    return '<section class="headline-brief"><div class="overview-subhead"><strong>What matters now</strong><span>Past 48 hours · source headlines</span></div>' + content + '</section>'


def _status_html(snapshot: Snapshot) -> str:
    status = snapshot.status
    if set(status.get("statuses", [])) == {"loading"}:
        return (
            '<div class="status-strip"><span class="status-warn">CONNECTING</span> | '
            '<b>Public market sources are loading in the background</b></div>'
        )
    availability = "status-ok" if status["unavailable"] == 0 else "status-warn"
    llm = "enabled" if settings.llm_ready else "fallback"
    return (
        '<div class="status-strip">'
        f'<span class="{availability}">LIVE</span> | '
        f'<b>{status["available"]}/{status["total"]}</b> indicators | '
        f'{status.get("intraday", 0)} intraday | {status.get("official_close", 0)} official close | '
        f'{status["unavailable"]} unavailable | {status["elapsed_seconds"]}s | agent {html.escape(llm)}'
        '</div>'
    )


def _agent_context_html(snapshot: Snapshot, agent: MarketAgent, profile: str) -> str:
    available = int(snapshot.status.get("available", 0))
    total = int(snapshot.status.get("total", len(snapshot.points)))
    now = datetime.now(timezone.utc)
    upcoming = sorted(
        (event for event in snapshot.events if _calendar_event_datetime(event) >= now - timedelta(hours=2)),
        key=_calendar_event_datetime,
    )
    next_event = upcoming[0] if upcoming else None
    catalyst = (
        f"{next_event.title} · {next_event.date} {next_event.time}"
        if next_event else "No verified upcoming event"
    )
    official_news = len(snapshot.news)
    return (
        '<div class="agent-context-grid">'
        f'<div class="agent-context-card"><span>Active desk lens</span><strong>{html.escape(profile)}</strong></div>'
        f'<div class="agent-context-card"><span>Market coverage</span><strong>{available}/{total} verified indicators</strong></div>'
        f'<div class="agent-context-card"><span>Next catalyst</span><strong>{html.escape(catalyst)}</strong></div>'
        f'<div class="agent-context-card"><span>Research memory</span><strong>{official_news} official updates · {html.escape(agent.rag_summary())}</strong></div>'
        '</div>'
    )


def _rag_library_html(agent: MarketAgent) -> str:
    local = agent.rag.documents()
    dynamic = agent.dynamic_rag.documents()[:10]
    cards: list[str] = []
    permanent = agent.dynamic_rag.archive.documents()
    for item in sorted(permanent, key=lambda doc: doc.get("published", ""), reverse=True):
        saved_url = "/gradio_api/file=" + quote(str((agent.dynamic_rag.archive.root / item["file"]).resolve()), safe="/:")
        cards.append(
            f'<a class="rag-doc rag-local" href="{html.escape(saved_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="rag-open">OPEN SAVED {item["format"]} ↗</span><strong>{html.escape(item["title"])}</strong>'
            f'<span><em>PERMANENT</em> · {html.escape(item["institution"])} · published {html.escape(item["published"][:10])}</span>'
            f'<span>Saved {html.escape(item["added_at"][:10])} · {"Automatic" if item["automatic"] else "Manual"}</span></a>'
        )
    for item in local:
        pdf_path = str((RAG_ROOT / item["filename"]).resolve())
        pdf_url = "/gradio_api/file=" + quote(pdf_path, safe="/:")
        cards.append(
            f'<a class="rag-doc rag-local" href="{html.escape(pdf_url, quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="rag-open">OPEN PDF ↗</span><strong>{html.escape(item["title"])}</strong>'
            f'<span><em>LOCAL PDF</em> · {html.escape(item["issuer"])} · published {html.escape(item["date"])}</span>'
            f'<span>Added {html.escape(item["added_at"])} · {html.escape(item["filename"])}</span>'
            '</a>'
        )
    for item in dynamic:
        cards.append(
            f'<a class="rag-doc rag-dynamic" href="{html.escape(item["url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<span class="rag-open">OPEN SOURCE ↗</span><strong>{html.escape(item["title"])}</strong>'
            f'<span><em>OFFICIAL FEED</em> · {html.escape(item["institution"])} · {html.escape(item["freshness"])}</span>'
            f'<span>Published {html.escape(item["published"][:10])} · indexed {html.escape(item["fetched_at"][:10])}</span>'
            '</a>'
        )
    empty = '<div class="calendar-empty">No RAG document is currently indexed.</div>'
    return (
        '<section class="rag-shell"><div class="rag-header"><div><h3>Research library</h3>'
        '<p>Local PDFs are editable. Official-feed documents refresh automatically and prioritize recent publications.</p></div>'
        f'<span class="rag-count">{len(local)} LOCAL · {len(permanent)} SAVED · {len(agent.dynamic_rag.documents())} DYNAMIC</span></div>'
        f'<div class="rag-grid">{"".join(cards) if cards else empty}</div></section>'
    )


def research_download_paths(agent: MarketAgent) -> list[str]:
    """Expose only files linked from the research library, never its indexes."""
    paths: set[str] = set()
    for item in agent.rag.documents():
        path = (RAG_ROOT / item["filename"]).resolve()
        if path.parent == RAG_ROOT.resolve() and path.is_file() and path.suffix.lower() == ".pdf":
            paths.add(str(path))
    archive_root = agent.dynamic_rag.archive.root.resolve()
    for item in agent.dynamic_rag.archive.documents():
        path = (archive_root / item["file"]).resolve()
        if path.parent == archive_root and path.is_file() and path.suffix.lower() in {".pdf", ".txt"}:
            paths.add(str(path))
    return sorted(paths)


def _outputs(snapshot: Snapshot, profile: str = "Cross-Asset", agent: MarketAgent | None = None):
    return (
        _ticker_html(snapshot.points),
        profiled_cockpit_html(snapshot.points, snapshot.status, profile),
        profiled_brief(snapshot.points, snapshot.events, snapshot.news, profile),
        _markets_html(snapshot.points),
        yield_curve_figure(snapshot.points) if profile in {"Rates Sales", "Cross-Asset"} else desk_focus_figure(snapshot.points, profile),
        desk_focus_figure(snapshot.points, profile),
        _calendar_html(snapshot.events, snapshot.calendar_error, snapshot.expectations_status),
        _news_cards_html(snapshot.news, snapshot.news_errors),
        _status_html(snapshot),
        _desk_rail_html(snapshot.points),
        _events_rail_html(snapshot.events),
        _agent_context_html(snapshot, agent, profile) if agent else "",
        _headlines_html(snapshot.news + cached_global_news()[0]),
    )


def build_app() -> gr.Blocks:
    store = SnapshotStore()
    agent = MarketAgent()
    initial = store.get()
    agent.dynamic_rag.ingest_news(initial.news)
    series_labels = {spec.label: spec.series_id for spec in SERIES}

    with gr.Blocks(title=settings.app_name) as app_blocks:
        app_blocks.allowed_paths = research_download_paths(agent)
        with gr.Row(elem_id="global-header"):
            with gr.Column(scale=10, min_width=520):
                live_header = gr.HTML(_header_html(), elem_id="live-terminal-header")
            with gr.Column(scale=0, min_width=160, elem_id="desk-profile-select"):
                desk_profile = gr.Dropdown(
                    choices=list(PROFILES), value="Cross-Asset", label="Desk lens", show_label=False,
                    filterable=False, container=False,
                    elem_classes=["desk-lens-control"],
                )
            with gr.Column(scale=1, min_width=112, elem_id="refresh-button"):
                refresh = gr.Button("Refresh data")
        clock_timer = gr.Timer(value=30.0, active=True)
        clock_timer.tick(
            fn=_header_html,
            inputs=[],
            outputs=live_header,
            queue=False,
            show_progress="hidden",
        )
        intraday_timer = gr.Timer(value=float(settings.intraday_refresh_seconds), active=True)
        macro_timer = gr.Timer(value=float(settings.macro_refresh_seconds), active=True)
        ticker = gr.HTML(_ticker_html(initial.points), elem_id="market-ticker")

        status_box = gr.HTML(_status_html(initial), visible=False)

        session_state = gr.State(new_session_state())
        last_answer_state = gr.State(profiled_brief(initial.points, initial.events, initial.news, "Cross-Asset"))
        initial_chart_frame = pd.DataFrame(columns=["Date"])
        chart_state = gr.State(initial_chart_frame.to_dict(orient="list"))

        with gr.Row(elem_id="terminal-workspace"):
            with gr.Column(scale=9, min_width=620, elem_id="main-terminal"):
                with gr.Tabs(selected="research-agent", elem_id="terminal-tabs"):
                    with gr.Tab("Overview"):
                        gr.HTML(
                            '<div class="news-toolbar overview-toolbar"><div><h2>Overview</h2>'
                            '<p>LIVE CROSS-ASSET SNAPSHOT AND DAILY DESK BRIEF</p>'
                            '</div><span>MARKET MONITOR</span></div>'
                        )
                        headline_brief = gr.HTML(_headlines_html(initial.news + cached_global_news()[0]))
                        cockpit = gr.HTML(profiled_cockpit_html(initial.points, initial.status, "Cross-Asset"))
                        gr.HTML(
                            '<div class="overview-subhead"><strong>Market moves</strong>'
                            '<span>Latest versus previous observation</span></div>'
                        )
                        with gr.Row(equal_height=True):
                            with gr.Column(scale=1, min_width=330, elem_classes=["terminal-panel"]):
                                curve_plot = gr.Plot(yield_curve_figure(initial.points), show_label=False)
                            with gr.Column(scale=1, min_width=330, elem_classes=["terminal-panel"]):
                                asset_plot = gr.Plot(desk_focus_figure(initial.points, "Cross-Asset"), show_label=False)
                        gr.HTML(
                            '<div class="overview-subhead"><strong>Morning brief</strong>'
                            '<span>Observed data and verified catalysts</span></div>'
                        )
                        with gr.Accordion("Desk briefing", open=True):
                            briefing = gr.Markdown(
                                profiled_brief(initial.points, initial.events, initial.news, "Cross-Asset"),
                                elem_classes=["terminal-copy"],
                            )
                            regenerate_brief = gr.Button("Refresh brief")

                    with gr.Tab("Markets"):
                        gr.HTML(
                            '<div class="tab-toolbar"><div><h2>Markets</h2>'
                            '<p>LEVELS, MOVES, FRESHNESS AND OFFICIAL SOURCE LINKS</p>'
                            '</div></div>'
                        )
                        market_board = gr.HTML(
                            _markets_html(initial.points),
                            elem_id="market-board-panel",
                        )

                    with gr.Tab("News"):
                        gr.HTML(
                            '<div class="tab-toolbar"><div><h2>News</h2>'
                            '<p>RECENT CENTRAL-BANK AND MACRO INTELLIGENCE FROM OFFICIAL SOURCES</p>'
                            '</div></div>'
                        )
                        with gr.Tabs(elem_id="news-source-tabs"):
                            with gr.Tab("Central banks"):
                                news_cards = gr.HTML(
                                    _news_cards_html(initial.news, initial.news_errors),
                                    elem_id="news-grid-panel",
                                )
                            with gr.Tab("Global markets"):
                                gr.Markdown("Recent publisher headlines via Google News. Open an article to read the original coverage.")
                                global_news_cards = gr.HTML(_news_cards_html(*cached_global_news(), official=False))

                    with gr.Tab("Research Agent", id="research-agent"):
                        gr.HTML(
                            '<div class="agent-hero"><div><h2>Your AI Sales Copilot</h2>'
                            '<p>Turn live markets, official research and upcoming catalysts into a desk view, a client angle and a clear next question.</p>'
                            '</div><span>PRIMARY WORKSPACE · AUDITED</span></div>'
                        )
                        agent_context = gr.HTML(_agent_context_html(initial, agent, "Cross-Asset"))
                        with gr.Row(equal_height=True, elem_classes=["agent-actions"]):
                            morning_action = gr.Button("Start my day")
                            changes_action = gr.Button("What changed?")
                            move_action = gr.Button("Explain the move")
                        with gr.Row(equal_height=True, elem_classes=["agent-actions"]):
                            event_action = gr.Button("Prepare an event")
                            client_action = gr.Button("Prep a client call")
                            scenario_action = gr.Button("Build scenarios")
                        with gr.Row(equal_height=False):
                            with gr.Column(scale=5, min_width=320, elem_classes=["terminal-form", "agent-query-panel"]):
                                question = gr.Textbox(
                                    label="Research request",
                                    lines=5,
                                    max_lines=8,
                                    placeholder="Example: Prepare my EUR rates client call: what moved, why it matters and what should I ask?",
                                    elem_classes=["desk-input"],
                                )
                                ask = gr.Button("Run research", variant="primary")
                                gr.HTML('<div class="agent-note">Grounded in the current snapshot, official news, macro events and approved research documents.</div>')
                                gr.HTML('<div class="agent-product-note">The agent is the decision layer. Markets, News, Calendar and Charts remain available as evidence workspaces for checking its conclusions.</div>')
                                with gr.Accordion("Session memory", open=False):
                                    memory_box = gr.Markdown("*No conversation context is currently held.*")
                                    clear_memory = gr.Button("Clear memory")
                            with gr.Column(scale=8, min_width=440, elem_classes=["terminal-output", "agent-answer-panel"]):
                                answer = gr.Markdown(
                                    "*Choose a workflow or enter a desk question. The copilot will return a bottom line, evidence, confidence, client angle and next catalysts.*",
                                    elem_classes=["terminal-copy"],
                                )
                                client_ready = gr.Button("Create client-ready copy")
                                with gr.Accordion("Evidence audit", open=False):
                                    trace = gr.Markdown("*No Research Trace yet.*")
                        rag_library = gr.HTML(_rag_library_html(agent))
                        with gr.Accordion("Manage research documents", open=False, elem_classes=["rag-manager"]):
                            gr.Markdown(
                                "Add a PDF to the agent or remove a local document. Title, institution and date are detected automatically."
                            )
                            rag_upload = gr.File(label="PDF document", file_types=[".pdf"], type="filepath")
                            rag_add = gr.Button("Add PDF to library", variant="primary")
                            with gr.Row():
                                rag_keep_choice = gr.Dropdown(
                                    choices=[(item["title"], item["url"]) for item in agent.dynamic_rag.documents()],
                                    label="Official publication to keep", elem_classes=["desk-input"], scale=4,
                                )
                                rag_keep = gr.Button("Keep permanently", scale=1)
                            gr.Markdown("Important policy publications are saved automatically in the background. Saved copies remain available after restart.")
                            with gr.Row(equal_height=True):
                                rag_delete_choice = gr.Dropdown(
                                    choices=[item["filename"] for item in agent.rag.documents()],
                                    label="Local document", elem_classes=["desk-input"], scale=4,
                                )
                                rag_delete = gr.Button("Remove", scale=1)
                                rag_sync = gr.Button("Sync official sources", scale=2)
                            rag_status = gr.Markdown("*Research library ready.*")

                    with gr.Tab("Calendar"):
                        gr.HTML(
                            '<div class="tab-toolbar"><div><h2>Calendar</h2>'
                            '<p>UPCOMING OFFICIAL MACRO AND CENTRAL-BANK EVENTS</p>'
                            '</div></div>'
                        )
                        calendar_view = gr.HTML(
                            _calendar_html(initial.events, initial.calendar_error, initial.expectations_status),
                            elem_id="calendar-view-panel",
                        )

                    with gr.Tab("Historical Charts"):
                        gr.HTML(
                            '<div class="tab-toolbar"><div><h2>Historical Charts</h2>'
                            '<p>OFFICIAL TIME SERIES, MARKET HISTORY AND COMPARATIVE TRENDS</p>'
                            '</div></div>'
                        )
                        with gr.Row(equal_height=False):
                            with gr.Column(scale=2, min_width=245, elem_classes=["terminal-form"]):
                                history_series = gr.Dropdown(
                                    list(series_labels),
                                    value=["US Treasury 10Y", "EUR/USD"],
                                    multiselect=True,
                                    label="Series, maximum 6",
                                    elem_classes=["desk-input"],
                                )
                                history_period = gr.Dropdown(
                                    [90, 180, 365, 730, 1825],
                                    value=365,
                                    label="Lookback days",
                                    elem_classes=["desk-input"],
                                )
                                load_history = gr.Button("Load history", variant="primary")
                                history_status = gr.Markdown("*Select up to six series, then load history.*")
                            with gr.Column(scale=8, min_width=430, elem_classes=["terminal-panel"]):
                                history_plot = gr.Plot(
                                    history_figure(initial_chart_frame, "Select series to load live history"),
                                    show_label=False,
                                )

                    with gr.Tab("Reports"):
                        gr.HTML(
                            '<div class="tab-toolbar"><div><h2>Reports</h2>'
                            '<p>AI DESK REPORT · CLIENT-READY BRIEFS WITH DATA, CHARTS AND SOURCES</p>'
                            '</div></div>'
                        )
                        with gr.Row(equal_height=False):
                            with gr.Column(scale=4, min_width=285, elem_classes=["terminal-form"]):
                                report_title = gr.Textbox(
                                    value="AI Desk Report", label="Report title", elem_classes=["desk-input"],
                                )
                                report_type = gr.Dropdown(
                                    ["Client Market Update", "Morning Brief", "Event Preview"],
                                    value="Client Market Update",
                                    label="Report type",
                                    elem_classes=["desk-input"],
                                )
                                report_focus = gr.Dropdown(
                                    ["Global Macro", "Rates", "FX", "Cross-Asset"],
                                    value="Global Macro",
                                    label="Focus",
                                    elem_classes=["desk-input"],
                                )
                                report_audience = gr.Textbox(
                                    label="Client or audience",
                                    placeholder="European institutional clients",
                                    elem_classes=["desk-input"],
                                )
                                include_chart = gr.Checkbox(value=True, label="Include selected historical chart")
                                generate_report = gr.Button("Generate report", variant="primary")
                            with gr.Column(scale=7, min_width=380, elem_classes=["terminal-output"]):
                                pdf_output = gr.File(label="PDF report")
                                email_output = gr.Markdown("*No email draft generated.*")

            with gr.Column(scale=3, min_width=290, elem_id="desk-rail"):
                desk_rail = gr.HTML(_desk_rail_html(initial.points))
                events_rail = gr.HTML(_events_rail_html(initial.events))

        with gr.Accordion("About, methodology and runtime controls", open=False, elem_id="about-panel"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=1):
                    gr.Markdown(METHODOLOGY, elem_classes=["terminal-copy"])
                with gr.Column(scale=1):
                    gr.Markdown(ABOUT, elem_classes=["terminal-copy"])
                    gr.Markdown(registry_markdown())
                    gr.Markdown(
                        f"""### Runtime controls

- Model calls per session/hour: **{settings.max_llm_calls}**
- Maximum agent steps: **{settings.max_agent_steps}**
- Tool calls per session: **{settings.max_tool_calls}**
- Calls per tool: **{settings.max_calls_per_tool}**
- Memory turns: **{settings.max_memory_turns}**
- Web search: **{'enabled' if settings.web_search_enabled else 'disabled'}**
"""
                    )

        def refresh_dashboard(profile: str):
            snapshot = store.refresh()
            agent.dynamic_rag.ingest_news(snapshot.news)
            return _outputs(snapshot, profile, agent)

        dashboard_outputs = [
            ticker,
            cockpit,
            briefing,
            market_board,
            curve_plot,
            asset_plot,
            calendar_view,
            news_cards,
            status_box,
            desk_rail,
            events_rail,
            agent_context,
            headline_brief,
        ]
        refresh.click(refresh_dashboard, inputs=[desk_profile], outputs=dashboard_outputs)

        app_blocks.load(refresh_dashboard, inputs=[desk_profile], outputs=dashboard_outputs)
        def refresh_market_news():
            items, errors = fetch_global_news()
            return _news_cards_html(items, errors, official=False), _headlines_html(store.get().news + items)

        news_timer = gr.Timer(value=300, active=True)
        news_timer.tick(refresh_market_news, outputs=[global_news_cards, headline_brief], show_progress="hidden")
        app_blocks.load(refresh_market_news, outputs=[global_news_cards, headline_brief], show_progress="hidden")
        refresh.click(refresh_market_news, outputs=[global_news_cards, headline_brief], show_progress="hidden")
        regenerate_brief.click(
            lambda profile: profiled_brief(store.get().points, store.get().events, store.get().news, profile),
            inputs=[desk_profile],
            outputs=[briefing],
        )
        desk_profile.change(
            lambda profile: (
                profiled_cockpit_html(store.get().points, store.get().status, profile),
                profiled_brief(store.get().points, store.get().events, store.get().news, profile),
                yield_curve_figure(store.get().points) if profile in {"Rates Sales", "Cross-Asset"} else desk_focus_figure(store.get().points, profile),
                desk_focus_figure(store.get().points, profile),
                _agent_context_html(store.get(), agent, profile),
            ),
            inputs=[desk_profile], outputs=[cockpit, briefing, curve_plot, asset_plot, agent_context], queue=False,
        )

        def refresh_intraday_view(profile: str):
            snapshot = store.refresh_intraday()
            return (
                _ticker_html(snapshot.points), profiled_cockpit_html(snapshot.points, snapshot.status, profile),
                _markets_html(snapshot.points),
                yield_curve_figure(snapshot.points) if profile in {"Rates Sales", "Cross-Asset"} else desk_focus_figure(snapshot.points, profile),
                desk_focus_figure(snapshot.points, profile), _desk_rail_html(snapshot.points),
                _agent_context_html(snapshot, agent, profile),
            )

        intraday_timer.tick(
            refresh_intraday_view, inputs=[desk_profile],
            outputs=[ticker, cockpit, market_board, curve_plot, asset_plot, desk_rail, agent_context],
            queue=False, show_progress="hidden",
        )

        def refresh_macro_view(profile: str):
            snapshot = store.refresh_macro()
            agent.dynamic_rag.ingest_news(snapshot.news)
            return (
                _ticker_html(snapshot.points), profiled_cockpit_html(snapshot.points, snapshot.status, profile),
                profiled_brief(snapshot.points, snapshot.events, snapshot.news, profile),
                _markets_html(snapshot.points),
                yield_curve_figure(snapshot.points) if profile in {"Rates Sales", "Cross-Asset"} else desk_focus_figure(snapshot.points, profile),
                desk_focus_figure(snapshot.points, profile), _desk_rail_html(snapshot.points),
                _agent_context_html(snapshot, agent, profile),
            )

        macro_timer.tick(
            refresh_macro_view, inputs=[desk_profile],
            outputs=[ticker, cockpit, briefing, market_board, curve_plot, asset_plot, desk_rail, agent_context],
            queue=False, show_progress="hidden",
        )
        quick_prompts = {
            morning_action: "Start my day with a source-backed Sales brief. Give me the bottom line, the three moves that matter for my desk, likely drivers with confidence, today's catalysts and two client questions.",
            changes_action: "What has changed since the previous close? Rank the important moves for my desk, separate signal from noise, and tell me which clients may care and why.",
            move_action: "Explain the most important move in the current snapshot. Separate observed facts from confirmed, likely, possible and unverified drivers. Include the next catalyst that could validate or reverse the move.",
            event_action: "Prepare me for the next high-importance macro or central-bank event. Include current pricing and setup, an upside/base/downside scenario map, assets to watch and questions clients may ask.",
            client_action: "Prepare a concise institutional client call from the current snapshot. Give me an opening line, three evidence-backed talking points, one intelligent client question, one objection to anticipate and a compliant follow-up angle.",
            scenario_action: "Build a concise scenario map for the most relevant upcoming catalyst. For each scenario state the trigger, likely cross-asset reaction, confidence, invalidation signal and a useful client discussion angle.",
        }
        for action, prompt in quick_prompts.items():
            action.click(lambda text=prompt: text, outputs=[question])

        def ask_agent(user_query: str, state: object, profile: str):
            snapshot = store.get()
            result, research_trace, updated_state, memory = agent.research(
                user_query, snapshot.points, snapshot.news, snapshot.events, state, profile,
            )
            return result, research_trace, updated_state, memory, result

        ask.click(
            ask_agent,
            inputs=[question, session_state, desk_profile],
            outputs=[answer, trace, session_state, memory_box, last_answer_state],
        )
        question.submit(
            ask_agent,
            inputs=[question, session_state, desk_profile],
            outputs=[answer, trace, session_state, memory_box, last_answer_state],
        )

        def make_client_ready(body: str):
            clean = (body or "").split("### Audited sources", 1)[0].strip()
            if not clean:
                return "*Run research before creating client-ready copy.*"
            clean = clean.replace("## BOTTOM LINE", "## Opening message")
            clean = clean.replace("## WHAT MOVED", "## Supporting facts")
            clean = clean.replace("## DRIVERS AND CONFIDENCE", "## Market interpretation")
            clean = clean.replace("## CLIENT ANGLE", "## Discussion points")
            clean = clean.replace("## NEXT CATALYSTS", "## What to watch next")
            clean = clean.replace("## RISKS AND OPEN QUESTIONS", "## Risks and open questions")
            return clean + "\n\n*Draft for human review before external use.*"

        client_ready.click(make_client_ready, inputs=[last_answer_state], outputs=[answer])

        def reset_memory():
            state = new_session_state()
            return state, memory_markdown(state)

        clear_memory.click(reset_memory, outputs=[session_state, memory_box])

        def rag_controls(status: str):
            app_blocks.allowed_paths = research_download_paths(agent)
            filenames = [item["filename"] for item in agent.rag.documents()]
            return (
                _rag_library_html(agent),
                gr.Dropdown(choices=filenames, value=None),
                status,
                gr.Dropdown(choices=[(item["title"], item["url"]) for item in agent.dynamic_rag.documents()], value=None),
            )

        def add_rag_document(file_path: str | None):
            if not file_path:
                return rag_controls("**Select a PDF before adding a document.**")
            try:
                filename = agent.rag.add_document(file_path, "", "", "")
                return rag_controls(f"**Indexed:** `{filename}`")
            except (OSError, ValueError) as exc:
                return rag_controls(f"**Document not added:** {html.escape(str(exc))}")

        def delete_rag_document(filename: str | None):
            if not filename:
                return rag_controls("**Select a local document to remove.**")
            try:
                agent.rag.remove_document(filename)
                return rag_controls(f"**Removed:** `{filename}`")
            except (OSError, ValueError) as exc:
                return rag_controls(f"**Document not removed:** {html.escape(str(exc))}")

        def sync_dynamic_rag():
            count = agent.dynamic_rag.sync(force=True)
            return rag_controls(
                f"**Official publications synchronized:** {count} indexed. "
                f"{agent.dynamic_rag.sync_status()}"
            )

        def keep_dynamic_document(url):
            document = next((item for item in agent.dynamic_rag.documents() if item["url"] == url), None)
            if not document:
                return rag_controls("Select an official publication to keep.")
            try:
                agent.dynamic_rag.archive.keep(document)
                return rag_controls("Publication saved permanently and available to the agent.")
            except (OSError, ValueError, requests.RequestException) as exc:
                return rag_controls(f"Publication not saved: {html.escape(str(exc))}")

        rag_keep.click(keep_dynamic_document, inputs=[rag_keep_choice],
                       outputs=[rag_library, rag_delete_choice, rag_status, rag_keep_choice])
        archive_timer = gr.Timer(value=60, active=True)
        def refresh_research_library():
            app_blocks.allowed_paths = research_download_paths(agent)
            return _rag_library_html(agent)

        archive_timer.tick(refresh_research_library, outputs=[rag_library], queue=False, show_progress="hidden")

        rag_add.click(
            add_rag_document,
            inputs=[rag_upload],
            outputs=[rag_library, rag_delete_choice, rag_status, rag_keep_choice],
        )
        rag_delete.click(
            delete_rag_document, inputs=[rag_delete_choice],
            outputs=[rag_library, rag_delete_choice, rag_status, rag_keep_choice],
        )
        rag_sync.click(
            sync_dynamic_rag, outputs=[rag_library, rag_delete_choice, rag_status, rag_keep_choice],
        )

        def load_history_chart(labels: list[str], days: int):
            ids = [series_labels[label] for label in (labels or []) if label in series_labels][:6]
            frame, errors = store.collector.fetch_history(ids, int(days))
            status = f"History loaded for {max(0, len(frame.columns) - 1)} series."
            if errors:
                status += " Unavailable: " + "; ".join(errors)
            return (
                history_figure(frame, "Historical observations"),
                status,
                frame.to_dict(orient="list"),
            )

        load_history.click(
            load_history_chart,
            inputs=[history_series, history_period],
            outputs=[history_plot, history_status, chart_state],
        )

        def create_report(
            title: str,
            report_type_value: str,
            focus: str,
            audience: str,
            add_chart: bool,
            chart: dict[str, list[object]],
        ):
            snapshot = store.get()
            audience_text = redact_secrets(audience).strip()[:100] or "institutional clients"
            prompt = (
                f"Prepare a professional {report_type_value} for {audience_text}, focused on {focus}. "
                "Prioritize verified overnight moves, rates and curve implications, cross-asset confirmation, "
                "upcoming catalysts, client talking points and risks. Use concise institutional language."
            )
            body, _, _, _ = agent.research(
                prompt,
                snapshot.points,
                snapshot.news,
                snapshot.events,
                new_session_state(),
            )
            safe_title = redact_secrets(title).strip()[:120] or "Daily Market Brief"
            sources = report_sources(snapshot.points, snapshot.events, snapshot.news)
            report_options = {}
            if "report_type" in inspect.signature(build_pdf).parameters:
                report_options = {
                    "report_type": report_type_value,
                    "audience": audience_text,
                    "focus": focus,
                }
            pdf = build_pdf(
                safe_title,
                body,
                sources,
                chart if add_chart else None,
                snapshot.points,
                snapshot.events,
                snapshot.news,
                **report_options,
            )
            return pdf, email_ready(safe_title, body)

        generate_report.click(
            create_report,
            inputs=[
                report_title,
                report_type,
                report_focus,
                report_audience,
                include_chart,
                chart_state,
            ],
            outputs=[pdf_output, email_output],
        )

    return app_blocks

