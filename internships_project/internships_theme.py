"""Shared appearance for the full dashboard and offers-only deployment."""
import base64
from pathlib import Path
import gradio as gr

CSS = Path(__file__).with_name('ui_styles.css').read_text(encoding='utf-8')
# New SKEMA emblem published on the school's 2026 brand announcement.
SKEMA_EMBLEM = base64.b64encode(
    (Path(__file__).parent / 'assets' / 'skema_emblem_2026.png').read_bytes()
).decode('ascii')

DESK_BLUE = gr.themes.Color(
    c50="#f3f6fa", c100="#eaf0f6", c200="#d2deea", c300="#b4c7da",
    c400="#8aa6c1", c500="#5d7f9f", c600="#3c6084", c700="#304d6b",
    c800="#263e57", c900="#203449", c950="#162536",
)
APP_THEME = gr.themes.Base(primary_hue=DESK_BLUE, secondary_hue=DESK_BLUE, neutral_hue="slate").set(
    body_background_fill="#f3f6fa", body_background_fill_dark="#f3f6fa",
    background_fill_primary="#ffffff", background_fill_primary_dark="#ffffff",
    background_fill_secondary="#f1f3f7", background_fill_secondary_dark="#f1f3f7",
    block_background_fill="#ffffff", block_background_fill_dark="#ffffff",
    block_label_background_fill="#ffffff", block_label_background_fill_dark="#ffffff",
    panel_background_fill="#ffffff", panel_background_fill_dark="#ffffff",
    input_background_fill="#ffffff", input_background_fill_dark="#ffffff",
    input_background_fill_hover="#f5f9fc", input_background_fill_hover_dark="#f5f9fc",
    input_border_color="#dce1e8", input_border_color_dark="#dce1e8",
    border_color_primary="#dfe3e9", border_color_primary_dark="#dfe3e9",
    body_text_color="#17202b", body_text_color_dark="#17202b",
    body_text_color_subdued="#647184", body_text_color_subdued_dark="#647184",
    button_primary_background_fill="*primary_600", button_primary_background_fill_dark="*primary_600",
    button_primary_background_fill_hover="*primary_700", button_primary_background_fill_hover_dark="*primary_700",
    button_primary_text_color="#ffffff", button_primary_text_color_dark="#ffffff",
)
