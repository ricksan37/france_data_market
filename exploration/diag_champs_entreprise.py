import json
from collections import Counter

with open('../data/raw/offres_2026-07-17_1403.json') as f:
    d = json.load(f)

offres = d['resultats']
print(f"Offres brutes : {len(offres)}")

# 1. Quelles clés apparaissent dans le bloc "entreprise", et à quelle fréquence ?
cles_entreprise = Counter()
for o in offres:
    for cle in o.get('entreprise', {}).keys():
        cles_entreprise[cle] += 1

print("\nClés présentes dans 'entreprise' :")
for cle, n in cles_entreprise.most_common():
    print(f"  {cle} : {n}")

# 2. Quelles clés existent au niveau racine de l'offre (pour repérer
#    tout champ identifiant qu'on n'aurait jamais remonté) ?
cles_racine = Counter()
for o in offres:
    for cle in o.keys():
        cles_racine[cle] += 1

print("\nClés au niveau racine de l'offre :")
for cle, n in cles_racine.most_common():
    print(f"  {cle} : {n}")