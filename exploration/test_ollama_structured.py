"""
Dry test of Ollama constrained decoding, before any work on the offers.

Single goal: verify that the `format` parameter really constrains the output
to the Pydantic schema, rather than getting JSON "by luck" through the prompt.
This is the distinction required by constrained JSON schema (constrained
grammar, not JSON mode). Two unknowns not to mix up: "is Ollama running?" and
"is the schema actually respected?": hence a trivial case, unrelated to the
business, to isolate the second.

Run: from france_data_market/  ->  python3 ../exploration/test_ollama_structured.py
"""

from ollama import chat
from pydantic import BaseModel


class Ville(BaseModel):
    """Deliberately minimal schema: 3 fields, 3 different types."""
    nom: str
    pays: str
    habitants: int


reponse = chat(
    model="mistral",
    messages=[{
        "role": "user",
        "content": "Donne-moi des informations sur la ville de Lyon.",
    }],
    format=Ville.model_json_schema(),
)

print("--- Sortie brute du modele ---")
print(reponse.message.content)

print("\n--- Apres validation Pydantic ---")
ville = Ville.model_validate_json(reponse.message.content)
print(ville)
print(f"\nType de 'habitants' : {type(ville.habitants).__name__}  (attendu : int)")