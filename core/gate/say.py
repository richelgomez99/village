"""Gate-owned spoken lines.

Voice agents and UI surfaces must use these strings verbatim for safety
outcomes.  Empty strings are represented by ``say("silent")``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Say:
    es: str
    en: str

    def to_dict(self) -> dict[str, str]:
        return {"es": self.es, "en": self.en}


TEMPLATES: dict[str, Say] = {
    "silent": Say("", ""),
    "money_hold": Say(
        "Voy a confirmar con {claimed_name} ahora mismo. No mande dinero todavía.",
        "I'm checking with {claimed_name} right now. Please don't send any money yet.",
    ),
    "money_denied": Say(
        "Ese no era {claimed_name}. No mande dinero. {coordinator_name} ya lo sabe.",
        "That wasn't {claimed_name}. Don't send any money. {coordinator_name} already knows.",
    ),
    "money_timeout": Say(
        "No pude confirmar con {claimed_name}. No mande dinero. Le aviso a {coordinator_name}.",
        "I couldn't confirm with {claimed_name}. Don't send any money. I'm letting {coordinator_name} know.",
    ),
    "money_confirmed": Say(
        "{claimed_name} dice que sí fue {pronoun_es}. Village nunca envía dinero; hable con {coordinator_name} antes de hacer algo.",
        "{claimed_name} says it was really {pronoun_en}. Village never sends money; please talk to {coordinator_name} before you do anything.",
    ),
    "money_unknown": Say(
        "No puedo confirmar quién llamó. No mande dinero ni dé datos de su banco. Le aviso a {coordinator_name}.",
        "I can't confirm who called. Don't send money or give out bank details. I'm letting {coordinator_name} know.",
    ),
    "money_never": Say(
        "Village nunca envía dinero, ni compra tarjetas, ni da datos de cuentas. Le aviso a {coordinator_name}.",
        "Village never sends money, buys gift cards or gives out account details. I'm letting {coordinator_name} know.",
    ),
    "money_share_disclosure": Say(
        "Entiendo. {coordinator_name} solo va a saber que alguien pidió dinero usando el nombre de {claimed_name}, y que usted no mandó nada.",
        "I understand. {coordinator_name} will only see that someone asked for money using {claimed_name}'s name, and that you didn't send anything.",
    ),
    "dd_report": Say(
        "Esta tapa ya se anotó a las {logged_time}. Le avisamos a {on_duty_name}.",
        "This lid was already logged at {logged_time}. We're letting {on_duty_name} know.",
    ),
    "dose_recorded": Say(
        "Anotado.",
        "Recorded.",
    ),
    "advise_911_first": Say(
        "Llame al 911 ahora. No espere a Village.",
        "Call 911 now. Do not wait for Village.",
    ),
    "no_dose_advice": Say(
        "No puedo decirle qué dosis tomar. Le aviso a su familia para que lo revise.",
        "I can't tell you what dose to take. I'm letting your family know so they can check.",
    ),
    "schedule_readback": Say(
        "El registro actual dice: {schedule}.",
        "The current record says: {schedule}.",
    ),
    "family_notified": Say(
        "Le avisamos a {on_duty_name}.",
        "We're letting {on_duty_name} know.",
    ),
    "core_down": Say(
        "No pude revisar Village ahora. Le aviso a {coordinator_name}.",
        "I couldn't check Village right now. I'm letting {coordinator_name} know.",
    ),
    "money_core_down": Say(
        "No pude revisar Village ahora. No mande dinero. Le aviso a {coordinator_name}.",
        "I couldn't check Village right now. Don't send money. I'm letting {coordinator_name} know.",
    ),
    "quiet_hours": Say(
        "No llamo a {recipient_name} en horas de descanso. Le aviso a {on_duty_name}.",
        "I don't call {recipient_name} during quiet hours. I'm letting {on_duty_name} know.",
    ),
}


def _pronouns(pronoun: str | None) -> dict[str, str]:
    if pronoun == "she":
        return {"pronoun_es": "ella", "pronoun_en": "her"}
    if pronoun == "they":
        return {"pronoun_es": "elle", "pronoun_en": "them"}
    return {"pronoun_es": "él", "pronoun_en": "him"}


# D30: names are parameters. The gate fills coordinator_name / recipient_name from village_state
# (rules/common.finish); these neutral words are used only when a village has no such member.
_NEUTRAL: dict[str, tuple[str, str]] = {
    "coordinator_name": ("su familia", "your family"),
    "recipient_name": ("su familiar", "your family member"),
    "on_duty_name": ("la familia", "the family"),
}


def say(key: str, **vars: object) -> dict[str, str]:
    try:
        template = TEMPLATES[key]
    except KeyError as exc:
        raise KeyError(f"unknown say template: {key}") from exc

    values = {k: str(v) for k, v in vars.items()}
    values.update({k: v for k, v in _pronouns(values.get("pronoun")).items() if k not in values})
    es_values = {**{k: es for k, (es, _) in _NEUTRAL.items()}, **values}
    en_values = {**{k: en for k, (_, en) in _NEUTRAL.items()}, **values}
    return {
        "es": template.es.format(**es_values),
        "en": template.en.format(**en_values),
    }
