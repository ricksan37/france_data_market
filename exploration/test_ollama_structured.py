"""
Test à blanc du décodage contraint Ollama, avant tout travail sur les offres.

Objectif unique : vérifier que le paramètre `format` contraint réellement la
sortie au schéma Pydantic, et non qu'on obtient du JSON "par chance" via le
prompt. C'est la distinction exigée par le schéma JSON contraint (grammaire contrainte,
pas JSON mode). Deux inconnues à ne pas mélanger : "Ollama tourne-t-il ?" et
"le schéma est-il bien respecté ?" : d'où un cas trivial, sans rapport avec
le métier, pour isoler la seconde.

Lancement : depuis france_data_market/  ->  python3 ../exploration/test_ollama_structured.py
"""

from ollama import chat
from pydantic import BaseModel


class Ville(BaseModel):
    """Schéma volontairement minimal : 3 champs, 3 types différents."""
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