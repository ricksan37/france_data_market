"""
Thème Plotly "Millimeter Dark", enregistré une fois et appliqué à chaque
figure via template="millimeter_dark". Couleurs et règles data-viz reprises
telles quelles du skill millimeter-visual-identity (references/dataviz.md) :
fond Slate, grille Hairline sur l'axe de valeur uniquement, texte Paper Muted
en mono, un seul accent qui mène par chart (Signal Blue par défaut).

Polices système de secours (décision Session 7) : pas de dépendance Google
Fonts, le rapport doit rester un fichier HTML autonome consultable hors ligne.
"""

import plotly.graph_objects as go
import plotly.io as pio

# Palette exacte du skill millimeter-visual-identity
VOID = "#0B0C0F"
SLATE = "#15171C"
SLATE_RAISED = "#1E2128"
HAIRLINE = "#2A2E37"
HAIRLINE_BRIGHT = "#3A404C"
PAPER = "#F2F3F5"
PAPER_MUTED = "#9BA1AC"

BLUE = "#4C8DFF"      # accent principal, série unique par défaut
AMBER = "#FFC24B"     # deuxième série
VERMILION = "#FF6B5A" # négatif / troisième série
GREEN = "#4ADE80"     # positif / quatrième série
# Violet volontairement absent : réservé aux CTA, jamais aux charts (règle skill)

FONT_TITRE = "'Arial Black', 'Helvetica Neue', sans-serif"
FONT_CORPS = "-apple-system, 'Segoe UI', Roboto, sans-serif"
FONT_MONO = "'SF Mono', 'Consolas', 'Monaco', monospace"

_template = go.layout.Template()

_template.layout = go.Layout(
    paper_bgcolor=SLATE,
    plot_bgcolor=SLATE,
    font=dict(family=FONT_MONO, color=PAPER_MUTED, size=11),
    # Titre en wrap automatique (largeur limitée) plutôt que tronqué par le
    # bord de la carte -- corrige le débordement observé sur les titres
    # longs (ex. "DOMAINES D'INTERVENTION (CLUSTERS NORMALISÉS)").
    title=dict(
        font=dict(family=FONT_TITRE, color=PAPER, size=17),
        x=0, xanchor="left",
        automargin=True,
    ),
    colorway=[BLUE, AMBER, VERMILION, GREEN],
    xaxis=dict(
        showgrid=False,
        showline=True,
        linecolor=HAIRLINE,
        tickfont=dict(family=FONT_MONO, color=PAPER_MUTED, size=10),
        ticks="",
        automargin=True,
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor=HAIRLINE,
        gridwidth=1,
        showline=False,
        tickfont=dict(family=FONT_MONO, color=PAPER_MUTED, size=10),
        ticks="",
        automargin=True,
    ),
    # automargin sur titre + axes : Plotly calcule la marge nécessaire selon
    # le contenu réel plutôt qu'une valeur fixe, ce qui corrige le
    # chevauchement titre / label d'axe Y observé sur les charts avec un
    # long libellé d'axe (ex. "% d'offres avec salaire").
    margin=dict(l=60, r=30, t=70, b=90, autoexpand=True),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="left", x=0,
        font=dict(family=FONT_MONO, color=PAPER_MUTED, size=10),
        bgcolor="rgba(0,0,0,0)",
    ),
    hoverlabel=dict(
        bgcolor=SLATE_RAISED,
        bordercolor=HAIRLINE_BRIGHT,
        font=dict(family=FONT_MONO, color=PAPER, size=11),
    ),
    autosize=True,
)

pio.templates["millimeter_dark"] = _template


def figure_vide(message: str) -> go.Figure:
    """
    Remplace un chart par un état "section indisponible" plutôt qu'un
    graphique cassé ou une exception. Utilisé quand la requête source dépend
    de stg_offres_skills et que CI_SANS_EXTRACTION=true a renvoyé 0 ligne
    (schéma présent, données absentes -- cf. macro en_ci_sans_extraction()).
    Documente l'absence au lieu de la cacher, cohérent avec le principe du
    projet : jamais de correction silencieuse.
    """
    fig = go.Figure()
    fig.update_layout(
        template="millimeter_dark",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=200,
        annotations=[
            dict(
                text=message,
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(family=FONT_MONO, color=PAPER_MUTED, size=12),
            )
        ],
    )
    return fig


if __name__ == "__main__":
    # Vérification rapide : le template s'enregistre et un chart minimal
    # se génère sans erreur avant de l'utiliser dans le vrai script.
    fig = go.Figure(go.Bar(x=["Python", "SQL", "Power BI"], y=[152, 148, 104]))
    fig.update_layout(template="millimeter_dark", title="Test thème Millimeter Dark")
    print("Thème enregistré :", "millimeter_dark" in pio.templates)
    print("Figure générée :", len(fig.data), "trace(s)")

    fig_vide = figure_vide("Section indisponible en environnement CI (extraction LLM non exécutée)")
    print("Figure vide générée :", len(fig_vide.layout.annotations), "annotation(s)")