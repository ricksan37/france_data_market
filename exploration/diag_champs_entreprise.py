import json
from collections import Counter

with open('../data/raw/job_offers_2026-07-17_1403.json') as f:
    d = json.load(f)

offres = d['resultats']
print(f"Offres brutes : {len(offres)}")

# 1. Which keys appear in the "entreprise" block, and how often?
cles_entreprise = Counter()
for o in offres:
    for cle in o.get('entreprise', {}).keys():
        cles_entreprise[cle] += 1

print("\nClés présentes dans 'entreprise' :")
for cle, n in cles_entreprise.most_common():
    print(f"  {cle} : {n}")

# 2. Which keys exist at the root level of the offer (to spot any
#    identifying field we never surfaced)?
cles_racine = Counter()
for o in offres:
    for cle in o.keys():
        cles_racine[cle] += 1

print("\nClés au niveau racine de l'offre :")
for cle, n in cles_racine.most_common():
    print(f"  {cle} : {n}")