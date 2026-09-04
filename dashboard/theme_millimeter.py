"""
Theme Plotly "Millimeter Dark", enregistre une fois et applique a chaque
figure via template="millimeter_dark". Couleurs et regles data-viz reprises
du skill millimeter-visual-identity (references/dataviz.md) : fond Slate,
grille Hairline sur l'axe de valeur uniquement, texte Paper Muted en mono,
un seul accent qui mene par chart (Signal Blue par defaut).

POLICES (revision Session 8). Le theme declarait des polices systeme pour
garder un fichier autonome. Mesure du 31/08 : rendu sur une machine sans
Arial Black, les titres perdent leurs accents -- le HTML contient bien
\\u00c9, l'affichage sort "DEMANDEES". Les trois familles de l'identite sont
desormais embarquees en base64 (cf. preparer_polices.py) ; ce module ne
declare plus que leurs noms, avec un repli systeme au cas ou le CSS ne
serait pas charge.
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

BLUE = "#4C8DFF"      # accent principal, serie unique par defaut
AMBER = "#FFC24B"     # deuxieme serie (paire imposee : Blue + Amber)
VERMILION = "#FF6B5A" # delta negatif uniquement
GREEN = "#4ADE80"     # delta positif uniquement
# Violet volontairement absent : reserve aux CTA, jamais aux charts (regle skill)

FONT_TITRE = "'Archivo Black', 'Arial Black', sans-serif"
FONT_CORPS = "'Inter', -apple-system, 'Segoe UI', Roboto, sans-serif"
FONT_MONO = "'JetBrains Mono', 'SF Mono', 'Consolas', monospace"

_template = go.layout.Template()

_template.layout = go.Layout(
    paper_bgcolor=SLATE,
    plot_bgcolor=SLATE,
    font=dict(family=FONT_MONO, color=PAPER_MUTED, size=11),
    # AUCUN TITRE DANS LA FIGURE. Mesure du 31/08 : Plotly cale la boite de
    # son titre sur la hauteur des capitales, et les accents qui depassent
    # au-dessus sont rognes -- "CATEGORIE" s'affichait sans accent alors que
    # le DOM contenait bien \u00c9 et que la police embarquee possede le
    # glyphe (verifie en isolant HTML et SVG cote a cote). Les titres vivent
    # desormais dans la carte HTML, ou rien ne les rogne. C'est aussi plus
    # conforme : dans ce systeme, la carte porte le libelle.
    title=dict(text=None),
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
    margin=dict(l=20, r=24, t=16, b=40, autoexpand=True),
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

_FONT_LABEL = dict(family=FONT_MONO, size=10, color=PAPER)


def chart_barres_horizontales(lignes, cat_col, val_col, titre, suffixe="",
                              couleur=BLUE, hauteur=None, note=None,
                              etiquettes=None):
    """Barres horizontales : le format par defaut des que les libelles sont longs.

    Les barres verticales obligeaient a incliner les libelles a 45 degres ;
    sur les douze clusters de domaines, ils se chevauchaient et debordaient de
    la carte. A l'horizontale, un libelle se lit sans rotation quelle que soit
    sa longueur, et l'ordre decroissant devient une lecture naturelle de haut
    en bas.

    Plotly dessine la premiere categorie en bas : on trie donc en croissant
    pour que la plus grande valeur arrive en haut.
    """
    donnees = sorted(lignes, key=lambda l: l[val_col])
    cats = [l[cat_col] for l in donnees]
    vals = [l[val_col] for l in donnees]

    if etiquettes:
        textes = [etiquettes[l[cat_col]] for l in donnees]
    else:
        textes = [f"{v:,.0f}{suffixe}".replace(",", " ") for v in vals]

    fig = go.Figure(go.Bar(
        x=vals, y=cats,
        orientation="h",
        text=textes,
        textposition="outside",
        textfont=_FONT_LABEL,
        marker_color=couleur,
        cliponaxis=False,  # sinon le label de la plus longue barre est rogne
    ))
    fig.update_layout(
        template="millimeter_dark",
        meta=dict(titre=titre, note=note),
        height=hauteur or max(240, 42 * len(cats) + 60),
        xaxis=dict(showgrid=True, gridcolor=HAIRLINE, showline=False,
                   showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showline=False,
                   tickfont=dict(family=FONT_MONO, color=PAPER_MUTED, size=11)),
        # Marge droite calculee sur l'etiquette la plus longue et non fixee :
        # les labels sortent du bout des barres, et une valeur fixe calibree
        # pour "283" tronquait "45 000 EUR - n=136" des que l'effectif a ete
        # ajoute. JetBrains Mono a une chasse fixe, la largeur d'une etiquette
        # est donc exactement proportionnelle a son nombre de caracteres.
        margin=dict(l=20, r=30 + 7 * max(len(t) for t in textes),
                    t=16, b=16, autoexpand=True),
    )
    return fig


def chart_colonnes(lignes, cat_col, val_col, titre, y_titre="", suffixe="",
                   couleur=BLUE, hauteur=340, note=None, etiquettes=None):
    """Colonnes verticales : reserve aux categories peu nombreuses et courtes.

    Une seule teinte, labels directs au-dessus des barres (regle skill :
    "Direct labels. Label the data, not a legend").
    """
    cats = [l[cat_col] for l in lignes]
    vals = [l[val_col] for l in lignes]

    fig = go.Figure(go.Bar(
        x=cats, y=vals,
        text=([etiquettes[l[cat_col]] for l in lignes] if etiquettes
              else [f"{v:,.0f}{suffixe}".replace(",", " ") for v in vals]),
        textposition="outside",
        textfont=_FONT_LABEL,
        marker_color=couleur,
        cliponaxis=False,
    ))
    fig.update_layout(template="millimeter_dark", meta=dict(titre=titre, note=note),
                      yaxis_title=y_titre, height=hauteur)
    return fig


def chart_barres_groupees(lignes, cat_col, series, titre, hauteur=340):
    """Deux series comparees : Blue + Amber, la paire imposee par l'identite.

    `series` : liste de (colonne, libelle). Plafonnee a deux -- au-dela,
    l'identite impose de regrouper la queue plutot que d'ajouter une teinte.
    """
    assert len(series) <= 2, "Deux series maximum (regle d'identite)"
    cats = [l[cat_col] for l in lignes]
    fig = go.Figure()
    for (col, libelle), couleur in zip(series, [BLUE, AMBER]):
        vals = [l[col] for l in lignes]
        fig.add_trace(go.Bar(
            x=cats, y=vals, name=libelle,
            text=vals, textposition="outside", textfont=_FONT_LABEL,
            marker_color=couleur, cliponaxis=False,
        ))
    fig.update_layout(template="millimeter_dark", meta=dict(titre=titre, note=None),
                      barmode="group", height=hauteur)
    return fig


def chart_ligne(lignes, x_col, y_col, titre, suffixe="", couleur=BLUE, hauteur=340):
    """Tendance : segments droits, aucun lissage.

    Le lissage inventerait des valeurs entre deux mesures. Sur quatre points,
    ce serait particulierement malhonnete. Marqueurs cercles bagues de Void
    pour rester lisibles quand deux points se chevauchent (regle skill).
    """
    xs = [l[x_col] for l in lignes]
    ys = [l[y_col] for l in lignes]

    fig = go.Figure(go.Scatter(
        x=xs, y=ys,
        mode="lines+markers+text",
        line=dict(color=couleur, width=2, shape="linear"),
        marker=dict(size=8, color=couleur, line=dict(color=VOID, width=1.5)),
        text=[f"{v}{suffixe}" for v in ys],
        textposition="top center",
        textfont=_FONT_LABEL,
    ))
    fig.update_layout(template="millimeter_dark", meta=dict(titre=titre, note=None), height=hauteur)
    return fig


def figure_vide(message: str) -> go.Figure:
    """Etat "section indisponible" plutot qu'un graphique casse ou une exception.

    Utilise quand la requete source depend de stg_offres_skills et que
    CI_SANS_EXTRACTION=true a renvoye 0 ligne (schema present, donnees
    absentes). Documente l'absence au lieu de la cacher, coherent avec le
    principe du projet : jamais de correction silencieuse.
    """
    fig = go.Figure()
    fig.update_layout(
        template="millimeter_dark",
        meta=dict(titre="", note=None),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        height=200,
        annotations=[dict(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False,
            font=dict(family=FONT_MONO, color=PAPER_MUTED, size=12),
        )],
    )
    return fig
