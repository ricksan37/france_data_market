"""
Output schema of the LLM skill extraction (extract_skills.py).

Ollama compiles this schema into a decoding grammar that constrains the
model's JSON output. The grammar encodes structure only (keys, types,
nesting): Field descriptions never reach the model, so every instruction
about meaning lives in extract_skills.PROMPT, and this file holds none.

Every field is required, with no default: the model MUST produce a value,
so null is a measurable fact (the information is absent from the text)
rather than a silent omission. Lists are list[str] without None, since an
empty list already expresses absence; scalars have no empty equivalent,
hence `| None`.

Field names stay in French: the prompt's per-field instructions are
anchored to these exact names (settled decision, see CLAUDE.md).
"""

from pydantic import BaseModel


class ExtractionOffre(BaseModel):
    """Fields extracted from the free text of a data job offer."""

    technologies: list[str]
    domaines: list[str]
    niveau_etudes: str | None
    annees_experience_min: int | None
    teletravail: str | None
    anglais_requis: bool | None
    salaire_texte: str | None
    entreprise_nom_texte: str | None
    client_final_masque: bool | None
