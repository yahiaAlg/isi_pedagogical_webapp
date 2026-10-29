"""Auto-generated 'fiche technique' content for a formation.

Builds the five fields the website's fiche page renders (description,
objectives, program_outline, main_tasks, prerequisites) from what the
pedagogical app knows about a Formation. Deterministic and offline (no AI
call): it follows the sizing/tone rules of the website's own brief
(docs/FICHE_TECHNIQUE_AI_BRIEF.md) — French, one list item per line,
objectives start with an infinitive verb, program sized by duration, no
invented regulatory citations (a text is only mentioned when
`legal_references` / `accreditation_body` names it).

Staff can refine the result on the website; later ISI edits never overwrite
text edited there (see the website's bridge.formation_sync).
"""

import re
from decimal import Decimal


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _num(value):
    d = Decimal(str(value)).normalize()
    s = format(d, "f")
    return s.replace(".", ",")


def _one_line(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def _domain(formation):
    if formation.category_id and formation.category.name:
        return formation.category.name.strip()
    if formation.specialty_id:
        return (formation.specialty.branch.name or "").strip()
    return ""


def generate_fiche(formation):
    f = formation
    title = _one_line(f.title)
    domain = _domain(f)
    days = int(f.duration_days or 0)
    hours = int(f.duration_hours or 0)
    ev = f.evaluation_type
    theory = ev in ("theory_only", "both")
    practice = ev in ("practice_only", "both")
    legal = _one_line(f.legal_references)
    score = f"{_num(f.passing_score)}/{_num(f.max_score)}"
    is_diploma = f.attestation_type == "diplome"
    cert_given = "Un diplôme est délivré" if is_diploma else "Une attestation de formation est délivrée"
    cert_goal = "le diplôme" if is_diploma else "l'attestation de formation"
    min_days = int(f.min_attendance_days or 0)

    # -- description (one paragraph, no line breaks) ----------------------
    own = _one_line(f.description)
    if own:
        parts = [own if own.endswith((".", "!", "?")) else own + "."]
    else:
        scope = f"relevant du domaine « {domain} »" if domain else "dispensée par l'Institut"
        dur = _plural(days, "jour", "jours") + (f" ({hours} h)" if hours else "")
        parts = [
            f"« {title} » est une formation de {dur} {scope}.",
            "Elle s'adresse aux professionnels, agents et encadrants concernés par ce "
            "domaine d'activité, ainsi qu'aux personnes qui souhaitent acquérir ou "
            "actualiser leurs compétences.",
        ]
    parts.append(
        {
            "theory_only": "Format théorique avec études de cas.",
            "practice_only": "Format pratique : exercices, ateliers et mises en situation.",
            "both": "Format théorique et pratique (exercices, mises en situation), sanctionné par une évaluation.",
        }.get(ev, "")
    )
    if f.produces_certificate:
        parts.append(
            f"{cert_given} aux participants remplissant les conditions "
            "de présence et d'évaluation."
        )
    if _one_line(f.accreditation_body):
        parts.append(f"Formation dispensée sous l'agrément de {_one_line(f.accreditation_body)}.")
    description = " ".join(p for p in parts if p)

    # -- objectives (4-7 lines, infinitive verbs) -------------------------
    obj = [
        f"Comprendre les enjeux, les concepts et la terminologie de « {title} »",
        "Identifier les situations, les acteurs et les responsabilités propres à ce domaine",
        "Appliquer le cadre réglementaire et les référentiels en vigueur"
        if legal
        else "Appliquer les méthodes et les bonnes pratiques du domaine",
        "Mettre en œuvre les gestes, procédures et outils lors d'exercices pratiques encadrés"
        if practice
        else "Analyser des cas concrets issus de la pratique professionnelle",
        "Transposer les acquis dans son environnement de travail",
    ]
    if ev == "both":
        obj.append(f"Valider ses acquis par une évaluation théorique et pratique (note de passage : {score})")
    elif ev == "theory_only":
        obj.append(f"Valider ses connaissances par une évaluation théorique (note de passage : {score})")
    elif ev == "practice_only":
        obj.append(f"Valider ses compétences par une évaluation pratique (note de passage : {score})")
    if f.produces_certificate:
        cond = f" sous réserve d'une présence minimale de {_plural(min_days, 'jour', 'jours')}" if min_days else ""
        obj.append(f"Obtenir {cert_goal}{cond}")

    # -- program outline (sized by duration, theory / practice split) -----
    prog = [
        f"Accueil, objectifs et cadre général : définitions et enjeux de « {title} »",
        "Cadre réglementaire et référentiels applicables"
        if legal
        else "Référentiels, normes et bonnes pratiques du domaine",
    ]
    if theory:
        prog.append("Théorie : principes, méthodes et outils")
    prog.append("Études de cas et analyse de situations professionnelles")
    if practice:
        prog.append("Pratique : exercices d'application et mises en situation encadrées")
    if days > 10:
        prog.append("Approfondissement : consolidation des acquis et travaux dirigés")
    if days > 30:
        prog.append("Mise en situation professionnelle : projet ou stage encadré, avec suivi individuel")
    if theory:
        prog.append(f"Évaluation théorique (note de passage : {score})")
    if practice:
        prog.append(f"Évaluation pratique (note de passage : {score})")
    prog.append(
        "Bilan de la formation et remise des attestations"
        if f.produces_certificate
        else "Bilan de la formation"
    )

    # -- main tasks (blank for purely theoretical formations) -------------
    tasks = []
    if practice:
        tasks = [
            f"Appliquer sur le terrain les procédures et gestes essentiels liés à « {title} »",
            "Utiliser correctement les équipements, outils et supports du domaine",
            "Respecter les consignes de sécurité et les règles de l'art de la profession",
            "Renseigner les documents et enregistrements associés à l'activité",
        ]

    # -- prerequisites (2-4 lines) ----------------------------------------
    pre = [
        "Niveau d'instruction adapté à la spécialité (vérifié à l'inscription)"
        if days >= 90
        else "Aucun niveau académique minimum requis",
        f"Exercer ou se destiner à une activité relevant du domaine « {domain} »"
        if domain
        else "Exercer ou se destiner à une activité liée à cette formation",
    ]
    if min_days:
        pre.append(
            f"Être disponible sur toute la durée de la formation (présence minimale : "
            f"{_plural(min_days, 'jour', 'jours')} sur {days})"
        )

    return {
        "description": description,
        "objectives": "\n".join(obj),
        "program_outline": "\n".join(prog),
        "main_tasks": "\n".join(tasks),
        "prerequisites": "\n".join(pre),
    }
