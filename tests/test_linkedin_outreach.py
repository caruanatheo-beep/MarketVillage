import os
import re
from pathlib import Path

import pytest

from internships_project import career_agent
from internships_project.candidate_profiles import extract_linkedin_recipient_profile


RECIPIENT = {
    "full_name": "Morgan Lee",
    "first_name": "Morgan",
    "name_confidence": "high",
    "headline": "Rates Sales Director at Bank A",
    "main_column_text": "Morgan Lee\nRates Sales Director at Bank A\nRates sales and client coverage.",
    "sidebar_text": "Top Skills\nBloomberg, Excel",
    "linkedin_pdf_text": (
        "Nom identifié dans l’en-tête : Morgan Lee\n"
        "Titre professionnel proche du nom : Rates Sales Director at Bank A\n"
        "Parcours : Rates sales and client coverage. " * 4
    ),
}


@pytest.mark.parametrize("language", ["Français", "English"])
@pytest.mark.parametrize("tone", ["Professionnel", "Naturel", "Direct et concis"])
@pytest.mark.parametrize("objective", [
    "Demander un conseil", "Échanger sur son parcours", "Se renseigner sur une opportunité",
])
def test_all_18_linkedin_tone_objective_language_combinations(
        monkeypatch, language, tone, objective):
    sender_name = "Alex Martin"
    career_objective = objective == "Échanger sur son parcours"
    opportunity = objective == "Se renseigner sur une opportunité"
    if language == "English":
        if opportunity:
            body = ("Our shared focus on Rates Sales is why I am contacting you. I am a student at SKEMA with markets experience. "
                    "What internship possibilities may be available in your team?")
        elif career_objective:
            body = ("Our shared focus on Rates Sales is why I am contacting you. I am a student at SKEMA with markets experience. "
                    "Would you be open to 10–15 minutes about a career decision that shaped your path?")
        else:
            body = ("Our shared focus on Rates Sales is why I am contacting you. I am a student at SKEMA with markets experience. "
                    "What helps you explain rate moves to clients?")
    else:
        if opportunity:
            body = ("Nous avons un intérêt commun pour les Rates Sales, ce qui motive mon message. Je suis étudiant à SKEMA avec une expérience de marché. "
                    "Quelles possibilités de stage pourraient exister dans votre équipe ?")
        elif career_objective:
            body = ("Nous avons un intérêt commun pour les Rates Sales, ce qui motive mon message. Je suis étudiant à SKEMA avec une expérience de marché. "
                    "Accepteriez-vous un échange de 10 à 15 minutes sur un choix qui a orienté votre parcours ?")
        else:
            body = ("Nous avons un intérêt commun pour les Rates Sales, ce qui motive mon message. Je suis étudiant à SKEMA avec une expérience de marché. "
                    "Quel élément vous aide le plus à expliquer les mouvements de taux aux clients ?")
    captured = {}
    calls = []

    def fake_openai_json(name, schema, instructions, payload):
        calls.append(name)
        captured.update(name=name, schema=schema, instructions=instructions, payload=payload)
        if language == "Français":
            followup = (
                "Je reviens sur ma question au sujet des possibilités de stage dans votre équipe. Si vous avez un moment pour m'indiquer les options possibles, merci."
                if opportunity else
                "Je reviens sur mon message au sujet de votre parcours en Rates Sales. Si vous avez 10 à 15 minutes pour parler d'un choix de carrière, je serais ravi de vous lire."
                if career_objective else
                "Je reviens sur ma question concernant les mouvements de taux en Rates Sales. Si vous avez un moment pour y répondre, votre avis m'aiderait."
            )
        else:
            followup = (
                "I wanted to follow up on my question about internship possibilities in your team. If you have a moment to share what may be available, thank you."
                if opportunity else
                "I wanted to follow up on my note about your Rates Sales career. If you have 10 to 15 minutes to discuss that career choice, I would be glad to hear from you."
                if career_objective else
                "I wanted to follow up on my question about rate moves in Rates Sales. If you have a moment to answer it, I would appreciate your view."
            )
        return {"body": body, "follow_up_body": followup}

    monkeypatch.setattr(career_agent, "_openai_json", fake_openai_json)
    sender_profile = {
        "name": sender_name,
        "overview": "18 months of market-finance internships; MSc Financial Markets & Investments, in progress.",
        "source_text": "Rates Sales internship; Fixed Income internship; MSc FMI at SKEMA.",
        "experience": ["Rates Sales internship", "Fixed Income internship"],
        "target_roles": ["Rates Sales"],
        "start_window": "May 2027",
    }
    message, followup = career_agent.generate_linkedin_messages(
        RECIPIENT, sender_profile, sender_name, tone, objective,
        language=language, message_type="Premier message après connexion",
    )

    payload = captured["payload"]
    assert payload["sender_candidate"]["name"] == sender_name
    assert payload["sender_candidate"]["profile"] == sender_profile
    assert payload["recipient_contact"]["full_name"] == "Morgan Lee"
    assert payload["recipient_contact"]["headline"] == RECIPIENT["headline"]
    assert payload["template_reference"] in career_agent._LINKEDIN_TEMPLATE_REFERENCES.values()
    assert payload["template_reference"] == career_agent._LINKEDIN_TEMPLATE_REFERENCES[(
        career_agent._linkedin_ascii(language), career_agent._linkedin_ascii(tone),
        career_agent._linkedin_ascii(objective),
    )]
    assert payload["follow_up_template_reference"] == career_agent._LINKEDIN_FOLLOWUP_REFERENCES[(
        career_agent._linkedin_ascii(language), career_agent._linkedin_ascii(tone),
    )]
    assert calls == ["linkedin_outreach_message"]
    assert "do not imply colleagueship or a shared team from an employer name alone" in captured["instructions"].casefold()
    assert message.startswith(("Bonjour Morgan,", "Hi Morgan,"))
    assert message.endswith("\n\nAlex")
    assert followup.startswith(("Bonjour Morgan,", "Hi Morgan,"))
    assert followup.endswith("\n\nMerci,\nAlex" if language == "Français" else "\n\nThanks,\nAlex")
    assert ("team" in followup.casefold() if opportunity else "Rates Sales" in followup)
    assert "did not reply" not in followup.casefold()
    assert "Alex Martin" not in message
    assert "Morgan" not in message.rsplit("\n\n", 1)[-1]
    if not opportunity:
        assert not re.search(
            r"\b(?:stage|internship|candidature|application|looking for a job|available for)\b",
            message + "\n" + followup, re.I,
        )
        assert "neither text may mention internship/job search" in captured["instructions"].casefold()
    elif language == "English":
        assert "internship" in message.casefold()
    else:
        assert "stage" in message.casefold()


def test_linkedin_invitation_has_no_signature_and_respects_character_limit(monkeypatch):
    captured = {}

    def fake_openai_json(name, schema, instructions, payload):
        captured.update(instructions=instructions, payload=payload)
        return {
            "body": "Votre activité en Rates Sales m’intéresse. Quel conseil donneriez-vous sur le suivi des clients ?",
            "follow_up_body": "Je reviens sur ma question au sujet de votre activité en Rates Sales. Si vous avez un moment pour y répondre, votre avis m'aiderait.",
        }

    monkeypatch.setattr(career_agent, "_openai_json", fake_openai_json)
    message = career_agent.generate_linkedin_message(
        RECIPIENT, "Profil candidat avec une expérience et un objectif précis." * 4,
        "Alex Martin", "Naturel", "Demander un conseil", message_type="Invitation",
    )
    assert message.startswith("Bonjour Morgan,")
    assert not message.endswith("\n\nAlex")
    assert len(message) <= career_agent.LINKEDIN_INVITATION_MAX_CHARS
    assert f"hard limit of {career_agent.LINKEDIN_INVITATION_MAX_CHARS} characters" in captured["instructions"]
    assert "No optional precision was provided" in captured["instructions"]
    assert captured["payload"]["optional_context"] == ""


def test_linkedin_manual_blank_recipient_name_uses_generic_greeting(monkeypatch):
    monkeypatch.setattr(career_agent, "_openai_json", lambda *args, **kwargs: {
        "body": "Votre activité sur les taux m’intéresse. Quel conseil donneriez-vous sur ce sujet ?",
        "follow_up_body": "Je reviens sur ma question concernant votre activité sur les taux. Si vous avez un moment pour y répondre, merci d'avance.",
    })
    message = career_agent.generate_linkedin_message(
        RECIPIENT, "Profil candidat complet, expérience et préférences de marché." * 3,
        "Alex Martin", "Naturel", "Demander un conseil", recipient_name_override="",
    )
    assert message.startswith("Bonjour,")


@pytest.mark.parametrize(("filename", "expected_name", "expected_headline"), [
    ("Profile (2).pdf", "Ben Pattenaude", "Corporate Treasury Analyst at PACCAR"),
    ("Profile (1).pdf", "Cam Trew", "Making sense of AI."),
])
def test_linkedin_profile_pdf_identity_comes_from_primary_column(
        filename, expected_name, expected_headline):
    pdf_dir = Path(os.getenv("LINKEDIN_TEST_PDF_DIR", str(Path.home() / "Downloads")))
    path = pdf_dir / filename
    if not path.is_file():
        pytest.skip(f"Personal test PDF not available at {path}")
    recipient = extract_linkedin_recipient_profile(path.read_bytes())
    assert recipient["full_name"] == expected_name
    assert recipient["first_name"] == expected_name.split()[0]
    assert recipient["name_confidence"] == "high"
    assert " ".join(recipient["headline"].split()) == expected_headline
    assert expected_name in recipient["main_column_text"]
    assert "Top Skills" not in recipient["full_name"]


def test_linkedin_profile_payload_keeps_candidate_and_recipient_experience_separate(monkeypatch):
    captured = {}
    def fake_openai_json(name, schema, instructions, payload):
        captured.update(payload=payload, instructions=instructions)
        return {"body": "Votre poste en Corporate Treasury m’intéresse. Quel aspect de cette transition vous a le plus servi ?",
                "follow_up_body": "Je reviens sur ma question au sujet de votre parcours en Corporate Treasury. Si vous avez un moment pour y répondre, votre avis m'aiderait."}

    monkeypatch.setattr(career_agent, "_openai_json", fake_openai_json)
    sender = {
        "experience": ["Rates Sales internship"],
        "overview": "18 months of markets internships; MSc FMI in progress.",
        "source_text": "Rates Sales internship at Bank X.",
    }
    recipient = {
        **RECIPIENT, "full_name": "Ben Pattenaude", "first_name": "Ben",
        "headline": "Corporate Treasury Analyst at PACCAR",
        "main_column_text": "Ben Pattenaude\nCorporate Treasury Analyst at PACCAR",
    }
    career_agent.generate_linkedin_message(
        recipient, sender, "Ari Lane", "Professionnel", "Demander un conseil",
    )
    assert captured["payload"]["sender_candidate"]["profile"] == sender
    assert captured["payload"]["recipient_contact"]["headline"] == "Corporate Treasury Analyst at PACCAR"
    assert "Rates Sales internship" in captured["payload"]["sender_candidate"]["profile"]["source_text"]
    assert "Corporate Treasury Analyst" in captured["payload"]["recipient_contact"]["main_column_text"]
    assert "beginner" in captured["instructions"].casefold()

