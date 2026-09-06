"""
Genere dashboard/rapport.html : rapport statique Millimeter Dark sur l'etat
du marche data France. Lit warehouse.duckdb en lecture seule, produit une
figure Plotly par requete, assemble le tout dans template_rapport.html.

AUCUN CHIFFRE EN DUR. Tout compte affiche vient desormais d'une requete.

DEGRADATION PROPRE (CI_SANS_EXTRACTION) : detectee par resultat vide plutot
que par relecture de la variable d'environnement, plus robuste car elle
mesure l'etat reel des donnees. Concerne uniquement les deux requetes qui
dependent de stg_offres_skills.

Pas de dependance pandas/numpy : reservees au dev local
(requirements-dev.txt), absentes du runner CI.

Usage : depuis la racine du repo -> .venv/bin/python3 dashboard/generer_rapport.py
"""

import base64
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import plotly.graph_objects as go
import plotly.io as pio

from theme_millimeter import (
    figure_vide, chart_barres_horizontales, chart_colonnes,
    chart_barres_groupees, chart_ligne, BLUE, AMBER,
)

RACINE = Path(__file__).resolve().parent.parent
DOSSIER = Path(__file__).resolve().parent
DB_PATH = RACINE / "data" / "warehouse.duckdb"
TEMPLATE_PATH = DOSSIER / "template_rapport.html"
SORTIE_PATH = DOSSIER / "rapport.html"
DOSSIER_POLICES = DOSSIER / "fonts"

MESSAGE_INDISPONIBLE = (
    "Section indisponible : extraction LLM non exécutée dans cet environnement "
    "(Ollama ne tourne pas sur un runner CI, cf. CI_SANS_EXTRACTION)"
)

# Traductions de presentation. Les modeles dbt conservent les valeurs
# canoniques ; seul l'affichage est humanise.
LIBELLES_CATEGORIE = {
    "EMPLOYEUR_DIRECT": "Employeur direct",
    "INTERMEDIAIRE": "Intermédiaire",
    "INTERMEDIAIRE_reclasse": "Intermédiaire (reclassé)",
    "ANONYME": "Employeur masqué",
}

# Nomenclature France Travail du champ experienceExige. Mesure du 31/08 :
# seules D et E sont presentes dans le corpus, S (souhaitee) est absente.
LIBELLES_EXPERIENCE = {
    "D": "Débutant accepté",
    "E": "Expérience exigée",
    "S": "Expérience souhaitée",
}

POLICES_EMBARQUEES = [
    ("Archivo Black", "ArchivoBlack.woff2", 400),
    ("Inter", "Inter-Regular.woff2", 400),
    ("Inter", "Inter-SemiBold.woff2", 600),
    ("JetBrains Mono", "JetBrainsMono-Regular.woff2", 400),
]


def css_polices() -> str:
    """Regles @font-face avec les WOFF2 encodes en base64.

    Le rapport doit rester un fichier unique ouvrable hors ligne, et afficher
    la meme chose partout. Declarer des polices systeme tenait la premiere
    exigence en sacrifiant la seconde : rendu sur une machine sans Arial
    Black, les titres de charts perdent leurs accents (mesure du 31/08).
    Embarquer 50 Ko de WOFF2 tient les deux.

    Absence de fonts/ : on n'echoue pas, on retombe sur les polices systeme
    en le signalant. Regenerer les polices demande le reseau et fonttools,
    dont le runner CI ne dispose pas (cf. preparer_polices.py).
    """
    regles = []
    for famille, fichier, graisse in POLICES_EMBARQUEES:
        chemin = DOSSIER_POLICES / fichier
        if not chemin.exists():
            print(f"  ATTENTION : {fichier} absent, repli sur les polices système")
            return "/* polices non embarquées : dashboard/fonts/ absent */"
        b64 = base64.b64encode(chemin.read_bytes()).decode("ascii")
        regles.append(
            # Accolades simples : cette chaine est passee en argument a
            # .format(), qui ne retraite pas les valeurs substituees. Les
            # doubler ici les ferait ressortir litteralement dans le CSS.
            f"@font-face {{ font-family: '{famille}'; font-weight: {graisse}; "
            f"font-style: normal; font-display: swap; "
            f"src: url(data:font/woff2;base64,{b64}) format('woff2'); }}"
        )
    return "\n".join(regles)


def executer(con, sql: str) -> list:
    """Execute une requete et retourne une liste de dictionnaires.

    pandas et numpy sont volontairement exclus de requirements.txt : .df()
    les importe implicitement et casse sur un runner CI minimal (decouvert
    en Session 7). duckdb expose .description et .fetchall() nativement.
    """
    curseur = con.execute(sql)
    colonnes = [c[0] for c in curseur.description]
    return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]


def traduire(lignes: list, colonne: str, dictionnaire: dict) -> list:
    """Remplace les codes bruts par leurs libelles lisibles."""
    return [
        {**ligne, colonne: dictionnaire.get(ligne[colonne], ligne[colonne])}
        for ligne in lignes
    ]


# Sous ce seuil, une mediane est portee par une ou deux valeurs : elle se
# lit comme un resultat alors qu'elle n'en est pas un. Mesure du 03/09 :
# INTERMEDIAIRE_reclasse affichait 65 000 EUR en tete du graphique, calcules
# sur 3 offres. Le seuil ecarte la barre du graphique ; la note sous la carte
# nomme ce qui a ete ecarte et pourquoi -- ecarter en silence serait le
# contraire du principe du projet.
SEUIL_EFFECTIF = 10


def separer_par_effectif(lignes: list, col_effectif: str = "n") -> tuple[list, list]:
    """Scinde un jeu de lignes selon SEUIL_EFFECTIF."""
    gardees = [l for l in lignes if l[col_effectif] >= SEUIL_EFFECTIF]
    ecartees = [l for l in lignes if l[col_effectif] < SEUIL_EFFECTIF]
    return gardees, ecartees


def note_effectif(ecartees: list, col_libelle: str) -> str | None:
    """Phrase qui nomme les categories ecartees, ou None s'il n'y en a pas."""
    if not ecartees:
        return None
    details = ", ".join(f"{l[col_libelle]} ({l['n']} offres)" for l in ecartees)
    return (f"Écarté faute d'effectif : {details}. Sous {SEUIL_EFFECTIF} offres "
            f"au salaire annuel exploitable, une médiane est portée par une ou "
            f"deux valeurs.")


def etiquettes_mediane(lignes: list, col_libelle: str, col_valeur: str) -> dict:
    """Etiquette de barre : la mediane ET son effectif, jamais l'une sans l'autre."""
    return {
        l[col_libelle]: f"{l[col_valeur]:,.0f} € · n={l['n']}".replace(",", " ")
        for l in lignes
    }


def big_stat_html(valeur: str, libelle: str, centre: bool = False) -> str:
    """Un chiffre qui vaut mieux qu'un graphique : bloc HTML, pas un chart."""
    classe = "big-stat big-stat-centre" if centre else "big-stat"
    return f"""
    <div class="{classe}">
        <div class="big-stat-valeur">{valeur}</div>
        <div class="big-stat-libelle">{libelle}</div>
    </div>
    """


def html_figure(fig, premiere: bool = False) -> str:
    """Titre en HTML puis figure. include_plotlyjs inline sur la premiere seulement.

    Le titre est ecrit hors de la figure, en <h3>, et lu depuis layout.meta ou
    la fabrique l'a range. Plotly rogne les accents des capitales de son
    propre titre (mesure du 31/08) ; en HTML, rien ne les rogne, et le
    libelle prend la meme typographie que le reste de la page.

    Le JS Plotly complet est embarque plutot que charge depuis un CDN : sans
    cela, l'ouverture par double-clic (file://) donne "Plotly is not defined"
    (corrige en Session 7).
    """
    meta = fig.layout.meta or {}
    titre = meta.get("titre", "")
    note = meta.get("note")
    entete = f'<h3 class="titre-carte">{titre}</h3>' if titre else ""
    if note:
        entete += f'<p class="note-carte">{note}</p>'
    return entete + pio.to_html(
        fig,
        include_plotlyjs="inline" if premiere else False,
        full_html=False,
        config={"displayModeBar": False},
    )


def generer() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # ---------- Perimetre : deux comptes, parce qu'il y a deux questions ----------
    # Une meme annonce publiee dans plusieurs villes recoit un identifiant par
    # ville. "Combien d'offres" et "combien d'annonces" n'ont donc pas la meme
    # reponse, et le rapport affiche les deux plutot que d'en choisir une.
    perimetre = executer(con, """
        select count(*) as offres,
               count(case when est_annonce_canonique then 1 end) as annonces
        from fct_offre
    """)[0]
    nb_offres, nb_annonces = perimetre["offres"], perimetre["annonces"]

    # ---------- KPI ----------
    # Par annonce : afficher ou non son salaire est un comportement d'employeur,
    # et un annonceur qui publie 25 fois le meme texte ne le manifeste qu'une
    # fois. Mesure : 32,6 % par offre contre 30,0 % par annonce.
    taux_transp = executer(con, """
        select round(100.0 * count(case when salaire_mentionne then 1 end)
                     / nullif(count(*), 0), 1) as pct
        from fct_offre
        where est_annonce_canonique
    """)[0]["pct"]

    hebdo = executer(con, """
        select semaine, nb_offres_total, taux_anonymat_pct
        from fct_marche_hebdo
        order by semaine
    """)
    taux_anonymat = hebdo[-1]["taux_anonymat_pct"] if hebdo else None

    flux = executer(con, """
        select semaine, semaines_depuis_precedente, nb_actives,
               nb_nouvelles, nb_sorties, taux_sortie_pct
        from fct_marche_flux
        order by semaine
    """)
    # La derniere ligne portant un taux de sortie : NULL sur la premiere
    # semaine, faute de point de comparaison.
    sorties = next((l for l in reversed(flux) if l["taux_sortie_pct"] is not None), None)

    kpi_offres = big_stat_html(
        f"{nb_offres}", f"Offres analysées, {nb_annonces} annonces distinctes")
    kpi_transparence = big_stat_html(f"{taux_transp:.1f} %", "Offres affichant un salaire")
    kpi_anonymat = (
        big_stat_html(f"{taux_anonymat:.1f} %", "Offres à employeur masqué")
        if taux_anonymat is not None
        else big_stat_html("N/A", "Employeur masqué, historique insuffisant")
    )
    kpi_sorties = (
        big_stat_html(
            f"{sorties['taux_sortie_pct']:.1f} %",
            # Accord du pluriel : l'ecart valait six semaines tant qu'il n'y
            # avait que deux points de mesure, il vaut 1 depuis le troisieme.
            # Un libelle genere doit rester grammatical quelle que soit la valeur.
            f"Offres disparues en {sorties['semaines_depuis_precedente']} "
            f"semaine{'s' if sorties['semaines_depuis_precedente'] > 1 else ''}",
        )
        if sorties
        else big_stat_html("N/A", "Flux, une seule semaine mesurée")
    )

    # ---------- 01 Flux ----------
    if len(flux) >= 2:
        # Axe categoriel et non temporel : deux mesures espacees de six
        # semaines donneraient deux barres filiformes noyees dans du vide.
        flux_libelle = [{**l, "semaine": l["semaine"].strftime("%d/%m")} for l in flux]
        fig_flux = chart_barres_groupees(
            flux_libelle, "semaine",
            [("nb_nouvelles", "Nouvelles"), ("nb_sorties", "Disparues")],
            "FLUX HEBDOMADAIRE DES OFFRES",
        )
    else:
        fig_flux = figure_vide("Flux disponible à partir de deux semaines mesurées")

    # Axe categoriel, comme le flux. Sur un axe temporel, Plotly place ses
    # propres graduations : il affichait "Aug 9, Aug 16, Aug 23, Aug 30" quand
    # les semaines mesurees sont les 10, 17, 24 et 31 -- des dates fausses,
    # en anglais, sur un rapport francais.
    hebdo_libelle = [{**l, "semaine": l["semaine"].strftime("%d/%m")} for l in hebdo]
    fig_anonymat = chart_ligne(
        hebdo_libelle, "semaine", "taux_anonymat_pct",
        "PART DES OFFRES À EMPLOYEUR MASQUÉ", suffixe=" %",
    )

    # ---------- 02 Remuneration ----------
    # Filtre sur salaire_annuel_plausible et non plus sur un offre_id ecrit en
    # dur. La version precedente excluait nommement l'offre 4933945, seul cas
    # connu en Session 4 ; il y en a 15 au 03/09. Une exclusion nominative ne
    # passe pas a l'echelle, une regle si.
    salaire_cat = traduire(executer(con, """
        select categorie_employeur,
               count(*) as n,
               median(salaire_min) as salaire_median
        from fct_offre
        where salaire_periode = 'annuel' and salaire_annuel_plausible
          and est_annonce_canonique
        group by categorie_employeur
        order by salaire_median desc
    """), "categorie_employeur", LIBELLES_CATEGORIE)
    cat_gardees, cat_ecartees = separer_par_effectif(salaire_cat)
    fig_salaire_cat = chart_barres_horizontales(
        cat_gardees, "categorie_employeur", "salaire_median",
        "SALAIRE MÉDIAN PAR CATÉGORIE D'EMPLOYEUR",
        etiquettes=etiquettes_mediane(cat_gardees, "categorie_employeur", "salaire_median"),
        note=note_effectif(cat_ecartees, "categorie_employeur"),
    )

    salaire_exp = traduire(executer(con, """
        select experience_exige,
               count(*) as n,
               median(salaire_min) as salaire_median
        from fct_offre
        where salaire_periode = 'annuel' and salaire_annuel_plausible
          and est_annonce_canonique
        group by experience_exige
        order by salaire_median
    """), "experience_exige", LIBELLES_EXPERIENCE)
    exp_gardees, exp_ecartees = separer_par_effectif(salaire_exp)
    # Blue seul : deux barres d'une meme mesure, pas deux series ni un delta.
    # La version precedente coloriait "debutant" en Vermilion et "experience
    # exigee" en Green, ce qui detournait le codage positif/negatif de
    # l'identite pour porter un jugement de valeur sur un niveau d'experience.
    fig_salaire_exp = chart_colonnes(
        exp_gardees, "experience_exige", "salaire_median",
        "SALAIRE MÉDIAN PAR NIVEAU D'EXPÉRIENCE", hauteur=364,
        etiquettes=etiquettes_mediane(exp_gardees, "experience_exige", "salaire_median"),
        note=note_effectif(exp_ecartees, "experience_exige"),
    )

    # ---------- 03 Transparence ----------
    stat_transparence = big_stat_html(
        f"{taux_transp:.1f} %",
        f"Offres affichant un salaire, sur {nb_offres} analysées",
        centre=True,
    )
    transparence_cat = traduire(executer(con, """
        select categorie_employeur,
               round(100.0 * count(distinct case when salaire_mentionne then offre_id end)
                     / nullif(count(distinct offre_id), 0), 1) as taux_pct
        from fct_offre
        where est_annonce_canonique
        group by categorie_employeur
        order by taux_pct desc
    """), "categorie_employeur", LIBELLES_CATEGORIE)
    fig_transparence_cat = chart_barres_horizontales(
        transparence_cat, "categorie_employeur", "taux_pct",
        "SALAIRE AFFICHÉ, PAR CATÉGORIE", suffixe=" %",
    )

    # ---------- 04 Geographie ----------
    # Jointure sur cle_commune et non sur code_postal : Paris, Lyon et Marseille
    # arrivent sans code postal, avec leur seul code INSEE de commune globale.
    # Avant ce correctif le rapport affichait 71 offres parisiennes ; il y en a
    # 148. Les trois plus grandes villes du pays etaient sous-comptees de moitie.
    geo = executer(con, """
        select c.nom_commune, count(distinct o.offre_id) as nb_offres
        from fct_offre o
        join dim_commune c on c.cle_commune = o.cle_commune
        where c.nom_commune is not null and c.nom_commune != 'NON_RESOLU'
        group by c.nom_commune
        order by nb_offres desc
        limit 10
    """)
    # Seul graphique compté par OFFRE et non par annonce, volontairement : un
    # poste ouvert dans plusieurs communes represente une opportunite dans
    # chacune. Le compter une fois, dans la ville de la publication la plus
    # ancienne, effacerait les autres. L'exception est signalee sous la carte.
    fig_geo = chart_barres_horizontales(
        geo, "nom_commune", "nb_offres", "DIX PREMIÈRES COMMUNES PAR NOMBRE D'OFFRES",
        note="Compté par offre, et non par annonce comme le reste du rapport : "
             "un poste ouvert dans plusieurs communes représente une opportunité "
             "dans chacune.",
    )

    # ---------- 05 Technologies ----------
    skills = executer(con, """
        select t.technologie, count(distinct t.offre_id) as nb_offres
        from fct_offre_technologie t
        join fct_offre o using (offre_id)
        where o.est_annonce_canonique
        group by t.technologie
        order by nb_offres desc
        limit 10
    """)
    fig_skills = (
        chart_barres_horizontales(skills, "technologie", "nb_offres",
                                  "DIX TECHNOLOGIES LES PLUS DEMANDÉES")
        if skills else figure_vide(MESSAGE_INDISPONIBLE)
    )

    # ---------- 06 Domaines ----------
    domaines = executer(con, """
        select d.domaine_normalise, count(distinct d.offre_id) as nb_offres
        from fct_offre_domaine d
        join fct_offre o using (offre_id)
        where o.est_annonce_canonique
          and d.domaine_normalise in (select distinct domaine_canonique from mapping_domaines)
        group by d.domaine_normalise
        order by nb_offres desc
    """)
    if domaines:
        fig_domaines = chart_barres_horizontales(
            domaines, "domaine_normalise", "nb_offres", "DOMAINES D'INTERVENTION",
        )
        taux_couv = executer(con, """
            select round(100.0 * count(case when domaine_normalise in
                       (select distinct domaine_canonique from mapping_domaines)
                     then 1 end) / nullif(count(*), 0), 1) as pct
            from fct_offre_domaine
        """)[0]["pct"]
        stat_couverture = big_stat_html(
            f"{taux_couv:.1f} %",
            "Couverture du mapping de domaines. La longue traîne n'est pas mappée, "
            "par décision documentée",
            centre=True,
        )
    else:
        fig_domaines = figure_vide(MESSAGE_INDISPONIBLE)
        stat_couverture = big_stat_html("N/A", "Couverture du mapping, indisponible en CI",
                                        centre=True)

    con.close()

    rendu = TEMPLATE_PATH.read_text(encoding="utf-8").format(
        polices=css_polices(),
        nb_offres=nb_offres,
        date_generation=datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC"),
        kpi_offres=kpi_offres,
        kpi_sorties=kpi_sorties,
        kpi_anonymat=kpi_anonymat,
        kpi_transparence=kpi_transparence,
        chart_flux=html_figure(fig_flux, premiere=True),
        chart_anonymat=html_figure(fig_anonymat),
        chart_salaire_cat=html_figure(fig_salaire_cat),
        chart_salaire_exp=html_figure(fig_salaire_exp),
        stat_transparence=stat_transparence,
        chart_transparence_cat=html_figure(fig_transparence_cat),
        chart_geo=html_figure(fig_geo),
        chart_skills=html_figure(fig_skills),
        chart_domaines=html_figure(fig_domaines),
        stat_couverture=stat_couverture,
    )
    SORTIE_PATH.write_text(rendu, encoding="utf-8")

    print(f"Rapport généré : {SORTIE_PATH}")
    print(f"  Périmètre       : {nb_offres} offres")
    print(f"  Semaines flux   : {len(flux)}")
    print(f"  Semaines corpus : {len(hebdo)}")
    print(f"  Technologies    : {len(skills) or 'indisponible (CI)'}")
    print(f"  Domaines        : {len(domaines) or 'indisponible (CI)'}")


if __name__ == "__main__":
    generer()
