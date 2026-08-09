"""
Génère dashboard/rapport.html : rapport statique Millimeter Dark sur l'état
actuel du marché data France (552 offres). Lit warehouse.duckdb en lecture
seule, exécute les 8 requêtes documentées dans requetes.sql, produit une
figure Plotly par requête, assemble le tout dans template_rapport.html.

Dégradation propre (CI_SANS_EXTRACTION) : détectée par DataFrame vide plutôt
que par relecture de la variable d'environnement -- plus robuste, mesure
l'état réel des données plutôt qu'un signal indirect (cf. Session 7).
Concerne uniquement les 2 requêtes dépendant de stg_offres_skills
(SKILLS_TOP10, DOMAINES_CLUSTERS).

Usage : depuis la racine du repo, venv actif :
    python3 dashboard/generer_rapport.py
"""

import duckdb
from datetime import datetime, timezone
from pathlib import Path

from theme_millimeter import figure_vide, BLUE, AMBER, VERMILION, GREEN
import plotly.graph_objects as go
import plotly.io as pio

RACINE = Path(__file__).resolve().parent.parent
DB_PATH = RACINE / "data" / "warehouse.duckdb"
TEMPLATE_PATH = Path(__file__).resolve().parent / "template_rapport.html"
SORTIE_PATH = Path(__file__).resolve().parent / "rapport.html"

MESSAGE_INDISPONIBLE = (
    "Section indisponible : extraction LLM non exécutée dans cet environnement "
    "(Ollama ne tourne pas sur un runner CI, cf. CI_SANS_EXTRACTION)"
)


def executer(con: duckdb.DuckDBPyConnection, sql: str):
    """Exécute une requête et retourne un DataFrame pandas."""
    return con.execute(sql).df()


def chart_column(df, x_col: str, y_col: str, titre: str, y_titre: str = "",
                  couleurs_barres=None, hauteur: int = 420):
    """
    Column chart standard : une série, Signal Blue par défaut, labels mono
    au-dessus des barres (règle skill : "Direct labels. Label the data, not
    a legend"). Hauteur fixée explicitement (plutôt que 100% du conteneur)
    pour donner à Plotly une zone de dessin stable où calculer ses marges
    automatiques -- corrige les titres tronqués et le chevauchement observés
    quand la figure hérite d'une taille trop contrainte par la carte HTML.

    couleurs_barres : liste optionnelle, une couleur par barre. Réservé aux
    cas où la couleur encode un vrai delta (règle skill : "Positive delta ->
    Green. Negative delta -> Vermilion.") -- jamais pour varier la couleur
    sans signification, ce qui casse la règle "fixed hue per série".
    """
    fig = go.Figure(
        go.Bar(
            x=df[x_col],
            y=df[y_col],
            text=df[y_col],
            textposition="outside",
            textfont=dict(family="'SF Mono', 'Consolas', 'Monaco', monospace", size=10),
            marker_color=couleurs_barres if couleurs_barres else BLUE,
        )
    )
    fig.update_layout(
        template="millimeter_dark",
        title=titre,
        yaxis_title=y_titre,
        height=hauteur,
        width=None,  # laisse Plotly s'adapter à la largeur du conteneur HTML
    )
    return fig


def big_stat_html(valeur: str, libelle: str) -> str:
    """
    "Big stat" : pas un chart Plotly, un bloc HTML/CSS direct -- la charte
    prévoit ce cas pour "un chiffre qui vaut mieux qu'un graphique"
    (Archivo Black 44-64pt en accent sur carte Slate, jamais accent-remplie).
    """
    return f"""
    <div class="big-stat">
        <div class="big-stat-valeur">{valeur}</div>
        <div class="big-stat-libelle">{libelle}</div>
    </div>
    """


def generer():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # --- Section 1 : Skills Demand ---
    df_skills = executer(con, """
        select technologie, count(distinct offre_id) as nb_offres
        from fct_offre_technologie
        group by technologie
        order by nb_offres desc
        limit 10
    """)
    if len(df_skills) == 0:
        fig_skills = figure_vide(MESSAGE_INDISPONIBLE)
    else:
        fig_skills = chart_column(df_skills, "technologie", "nb_offres",
                                   "TOP 10 TECHNOLOGIES DEMANDÉES", "Nombre d'offres")

    # --- Section 2 : Domaines ---
    df_domaines = executer(con, """
        select domaine_normalise, count(distinct offre_id) as nb_offres
        from fct_offre_domaine
        where domaine_normalise in (select distinct domaine_canonique from mapping_domaines)
        group by domaine_normalise
        order by nb_offres desc
    """)
    if len(df_domaines) == 0:
        fig_domaines = figure_vide(MESSAGE_INDISPONIBLE)
        couverture_html = big_stat_html("N/A", "Taux de couverture du mapping (indisponible en CI)")
    else:
        fig_domaines = chart_column(df_domaines, "domaine_normalise", "nb_offres",
                                     "DOMAINES D'INTERVENTION", "Nombre d'offres")
        df_couverture = executer(con, """
            select round(
                100.0 * count(case when domaine_normalise in (select distinct domaine_canonique from mapping_domaines) then 1 end)
                / nullif(count(*), 0), 1
            ) as taux_couverture_pct
            from fct_offre_domaine
        """)
        taux = df_couverture["taux_couverture_pct"].iloc[0]
        couverture_html = big_stat_html(
            f"{taux:.1f}%",
            "Taux de couverture du mapping de domaines (longue traîne non mappée volontairement)"
        )

    # --- Section 3 : Salary Intelligence ---
    df_salaire_cat = executer(con, """
        select categorie_employeur, count(offre_id) as nb_offres, median(salaire_min) as salaire_median
        from fct_offre
        where salaire_periode = 'annuel' and offre_id != '4933945'
        group by categorie_employeur
        order by salaire_median desc
    """)
    fig_salaire_cat = chart_column(df_salaire_cat, "categorie_employeur", "salaire_median",
                                    "SALAIRE PAR CATÉGORIE D'EMPLOYEUR", "Salaire médian annuel (€)")

    df_salaire_exp = executer(con, """
        select experience_exige, count(offre_id) as nb_offres, median(salaire_min) as salaire_median
        from fct_offre
        where salaire_periode = 'annuel' and offre_id != '4933945'
        group by experience_exige
        order by experience_exige
    """)
    # Delta encoding légitime (règle skill : "Positive delta -> Green"). Ici
    # E (expérience exigée) représente une progression de +8000€ par rapport
    # à D (débutant accepté) -- pas une variation de couleur arbitraire, un
    # vrai delta mesuré (cf. notebook Session 7).
    couleurs_exp = [VERMILION if niveau == "D" else GREEN for niveau in df_salaire_exp["experience_exige"]]
    fig_salaire_exp = chart_column(df_salaire_exp, "experience_exige", "salaire_median",
                                    "SALAIRE PAR EXPÉRIENCE EXIGÉE", "Salaire médian annuel (€)",
                                    couleurs_barres=couleurs_exp)

    # --- Section 4 : Transparence salariale ---
    df_transparence_globale = executer(con, """
        select round(100.0 * count(case when salaire_mentionne then 1 end) / nullif(count(*), 0), 1) as taux_transparence_pct
        from fct_offre
    """)
    taux_transp = df_transparence_globale["taux_transparence_pct"].iloc[0]
    transparence_html = big_stat_html(f"{taux_transp:.1f}%", "Offres avec salaire affiché (552 offres)")

    df_transparence_cat = executer(con, """
        select categorie_employeur,
            count(distinct offre_id) as nb_offres_total,
            count(distinct case when salaire_mentionne then offre_id end) as nb_avec_salaire,
            round(100.0 * count(distinct case when salaire_mentionne then offre_id end) / nullif(count(distinct offre_id), 0), 1) as taux_pct
        from fct_offre
        group by categorie_employeur
        order by taux_pct desc
    """)
    fig_transparence_cat = chart_column(df_transparence_cat, "categorie_employeur", "taux_pct",
                                         "TRANSPARENCE PAR CATÉGORIE", "% avec salaire")

    # --- Section 5 : Géographie ---
    df_geo = executer(con, """
        select c.nom_commune, count(distinct o.offre_id) as nb_offres
        from fct_offre o
        left join dim_commune c on c.code_postal = o.code_postal
        where c.nom_commune is not null
        group by c.nom_commune
        order by nb_offres desc
        limit 10
    """)
    fig_geo = chart_column(df_geo, "nom_commune", "nb_offres",
                            "TOP 10 COMMUNES PAR NOMBRE D'OFFRES", "Nombre d'offres")

    con.close()

    # --- Assemblage ---
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendu = template.format(
        date_generation=datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC"),
        chart_skills=pio.to_html(fig_skills, include_plotlyjs="cdn", full_html=False, config={"displayModeBar": False}),
        chart_domaines=pio.to_html(fig_domaines, include_plotlyjs=False, full_html=False, config={"displayModeBar": False}),
        stat_couverture=couverture_html,
        chart_salaire_cat=pio.to_html(fig_salaire_cat, include_plotlyjs=False, full_html=False, config={"displayModeBar": False}),
        chart_salaire_exp=pio.to_html(fig_salaire_exp, include_plotlyjs=False, full_html=False, config={"displayModeBar": False}),
        stat_transparence=transparence_html,
        chart_transparence_cat=pio.to_html(fig_transparence_cat, include_plotlyjs=False, full_html=False, config={"displayModeBar": False}),
        chart_geo=pio.to_html(fig_geo, include_plotlyjs=False, full_html=False, config={"displayModeBar": False}),
    )

    SORTIE_PATH.write_text(rendu, encoding="utf-8")
    print(f"Rapport généré : {SORTIE_PATH}")
    print(f"  Skills Demand    : {len(df_skills)} technologies" if len(df_skills) else "  Skills Demand    : indisponible (CI)")
    print(f"  Domaines         : {len(df_domaines)} clusters" if len(df_domaines) else "  Domaines         : indisponible (CI)")
    print(f"  Salary (cat.)    : {len(df_salaire_cat)} catégories")
    print(f"  Salary (exp.)    : {len(df_salaire_exp)} niveaux")
    print(f"  Transparence     : {taux_transp}% global")
    print(f"  Géographie       : {len(df_geo)} communes")


if __name__ == "__main__":
    generer()