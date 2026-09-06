"""
Generates dashboard/report.html: a static, dark-themed report on the
state of the French data job market. Reads warehouse.duckdb read-only,
produces one Plotly figure per query, assembles it all into
report_template.html.

NO HARDCODED FIGURE. Every count displayed now comes from a query.

CLEAN DEGRADATION (CI_WITHOUT_EXTRACTION): detected via an empty result
rather than by re-reading the environment variable, more robust because it
measures the data's actual state. Applies only to the two queries that
depend on stg_extraction__skills.

No pandas/numpy dependency: reserved for local dev (requirements-dev.txt),
absent from the CI runner.

Usage: from the repo root -> .venv/bin/python3 dashboard/generate_report.py
"""

import base64
from datetime import datetime, timezone
from pathlib import Path
import string

import duckdb
import plotly.graph_objects as go
import plotly.io as pio

from theme import (
    empty_figure, horizontal_bar_chart, column_chart,
    grouped_bar_chart, line_chart, BLUE, AMBER,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = Path(__file__).resolve().parent
DB_PATH = ROOT_DIR / "data" / "warehouse.duckdb"
TEMPLATE_PATH = DASHBOARD_DIR / "report_template.html"
OUTPUT_PATH = DASHBOARD_DIR / "report.html"
FONTS_DIR = DASHBOARD_DIR / "fonts"


# Display translations. The dbt models keep the canonical values; only the
# display is humanized.
CATEGORY_LABELS = {
    "DIRECT_EMPLOYER": "Direct employer",
    "INTERMEDIARY": "Intermediary",
    "INTERMEDIARY_RECLASSIFIED": "Intermediary (reclassified)",
    "ANONYMOUS": "Masked employer",
}

# France Travail's nomenclature for the experienceExige field. Measured
# 2026-08-31: only D and E are present in the corpus, S (desired) is absent.
EXPERIENCE_LABELS = {
    "D": "No experience required",
    "E": "Experience required",
    "S": "Experience desired",
}

EMBEDDED_FONTS = [
    ("Archivo Black", "ArchivoBlack.woff2", 400),
    ("Inter", "Inter-Regular.woff2", 400),
    ("Inter", "Inter-SemiBold.woff2", 600),
    ("JetBrains Mono", "JetBrainsMono-Regular.woff2", 400),
]


def fonts_css() -> str:
    """@font-face rules with the WOFF2 files base64-encoded.

    The report must stay a single file, openable offline, and look the same
    everywhere. Declaring system fonts met the first requirement while
    sacrificing the second: rendered on a machine without Arial Black, chart
    titles lose their accents (measured 2026-08-31). Embedding 50 KB of
    WOFF2 satisfies both.

    Missing fonts/: we don't fail, we fall back to system fonts while
    reporting it. Regenerating the fonts needs network access and fonttools,
    which the CI runner doesn't have (see prepare_fonts.py).
    """
    rules = []
    for family, file, weight in EMBEDDED_FONTS:
        path = FONTS_DIR / file
        if not path.exists():
            print(f"  WARNING: {file} missing, falling back to system fonts")
            return "/* fonts not embedded: dashboard/fonts/ missing */"
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        rules.append(
            # Single braces: this string is passed as an argument to
            # .format(), which doesn't reprocess substituted values.
            # Doubling them here would make them show up literally in the CSS.
            f"@font-face {{ font-family: '{family}'; font-weight: {weight}; "
            f"font-style: normal; font-display: swap; "
            f"src: url(data:font/woff2;base64,{b64}) format('woff2'); }}"
        )
    return "\n".join(rules)


def execute(con, sql: str) -> list:
    """Runs a query and returns a list of dictionaries.

    pandas and numpy are deliberately excluded from requirements.txt: .df()
    implicitly imports them and breaks on a minimal CI runner. duckdb
    exposes .description and .fetchall() natively.
    """
    cursor = con.execute(sql)
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def humanize_column(rows: list, column: str, mapping: dict) -> list:
    """Replaces raw codes with their readable labels."""
    return [
        {**row, column: mapping.get(row[column], row[column])}
        for row in rows
    ]


# Below this threshold, a median is carried by one or two values: it reads
# as a result when it isn't one. Measured 2026-09-03: INTERMEDIARY_RECLASSIFIED
# used to show 65,000 EUR at the top of the chart, computed on 3 offers. The
# threshold drops the bar from the chart; the note under the card names what
# was dropped and why -- dropping it silently would be the opposite of the
# project's principle.
SAMPLE_SIZE_THRESHOLD = 10


def split_by_sample_size(rows: list, count_col: str = "n") -> tuple[list, list]:
    """Splits a set of rows by SAMPLE_SIZE_THRESHOLD."""
    kept = [r for r in rows if r[count_col] >= SAMPLE_SIZE_THRESHOLD]
    excluded = [r for r in rows if r[count_col] < SAMPLE_SIZE_THRESHOLD]
    return kept, excluded


def sample_size_note(excluded: list, label_col: str) -> str | None:
    """Sentence naming the excluded categories, or None if there are none."""
    if not excluded:
        return None
    details = ", ".join(f"{r[label_col]} ({r['n']} offers)" for r in excluded)
    return (f"Excluded for insufficient sample size: {details}. Below "
            f"{SAMPLE_SIZE_THRESHOLD} offers with a usable annual salary, a "
            f"median is carried by one or two values.")


def median_labels(rows: list, label_col: str, value_col: str) -> dict:
    """Bar label: the median AND its sample size, never one without the other."""
    return {
        r[label_col]: f"{r[value_col]:,.0f} € · n={r['n']}".replace(",", " ")
        for r in rows
    }


def big_stat_html(value: str, label: str, centered: bool = False) -> str:
    """A number worth more than a chart: an HTML block, not a chart."""
    css_class = "big-stat big-stat-centered" if centered else "big-stat"
    return f"""
    <div class="{css_class}">
        <div class="big-stat-value">{value}</div>
        <div class="big-stat-label">{label}</div>
    </div>
    """


def html_figure(fig, first: bool = False) -> str:
    """HTML title then figure. include_plotlyjs inline on the first one only.

    The title is written outside the figure, as <h3>, read from layout.meta
    where the factory stored it. Plotly clips the accents of its own title's
    capital letters (measured 2026-08-31); in HTML, nothing clips them, and
    the label gets the same typography as the rest of the page.

    The full Plotly JS is embedded rather than loaded from a CDN: without
    that, opening the file by double-click (file://) gives "Plotly is not
    defined" (fixed since).
    """
    meta = fig.layout.meta or {}
    title = meta.get("title", "")
    note = meta.get("note")
    header = f'<h3 class="card-title">{title}</h3>' if title else ""
    if note:
        header += f'<p class="card-note">{note}</p>'
    return header + pio.to_html(
        fig,
        include_plotlyjs="inline" if first else False,
        full_html=False,
        config={"displayModeBar": False},
    )


def generate() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # ---------- Scope: two counts, because there are two questions ----------
    # The same listing published in several cities gets one identifier per
    # city. "How many offers" and "how many listings" therefore don't share
    # an answer, and the report shows both rather than picking one.
    scope = execute(con, """
        select count(*) as offers,
               count(case when is_canonical_listing then 1 end) as listings
        from fct_job_offer
    """)[0]
    offer_count, listing_count = scope["offers"], scope["listings"]

    # ---------- KPIs ----------
    # By listing: showing a salary or not is an employer behavior, and an
    # advertiser publishing the same text 25 times only shows it once.
    # Measured: 32.6% by offer versus 30.0% by listing.
    transparency_rate = execute(con, """
        select round(100.0 * count(case when salary_mentioned then 1 end)
                     / nullif(count(*), 0), 1) as pct
        from fct_job_offer
        where is_canonical_listing
    """)[0]["pct"]

    weekly = execute(con, """
        select week_start_date, total_offer_count, anonymous_rate_pct
        from fct_weekly_market
        order by week_start_date
    """)
    anonymous_rate = weekly[-1]["anonymous_rate_pct"] if weekly else None

    flow = execute(con, """
        select week_start_date, weeks_since_previous, active_offer_count,
               new_offer_count, exit_count, exit_rate_pct
        from fct_weekly_market_flow
        order by week_start_date
    """)
    # The last row carrying an exit rate: NULL on the first week, for lack of
    # a comparison point.
    exits = next((r for r in reversed(flow) if r["exit_rate_pct"] is not None), None)

    kpi_offers = big_stat_html(
        f"{offer_count}", f"Offers analyzed, {listing_count} distinct listings")
    kpi_transparency = big_stat_html(f"{transparency_rate:.1f} %", "Offers disclosing a salary")
    kpi_anonymity = (
        big_stat_html(f"{anonymous_rate:.1f} %", "Offers with a masked employer")
        if anonymous_rate is not None
        else big_stat_html("N/A", "Masked employer, insufficient history")
    )
    kpi_exits = (
        big_stat_html(
            f"{exits['exit_rate_pct']:.1f} %",
            # Plural agreement: the gap was six weeks while there were only
            # two data points, it's been 1 since the third. A generated
            # label must stay grammatical regardless of the value.
            f"Offers exited over {exits['weeks_since_previous']} "
            f"week{'s' if exits['weeks_since_previous'] > 1 else ''}",
        )
        if exits
        else big_stat_html("N/A", "Flow, only one week measured")
    )

    # ---------- 01 Flow ----------
    if len(flow) >= 2:
        # Categorical axis rather than temporal: two measurements six weeks
        # apart would give two thin bars lost in empty space.
        flow_labeled = [{**r, "week_start_date": r["week_start_date"].strftime("%d/%m")} for r in flow]
        flow_fig = grouped_bar_chart(
            flow_labeled, "week_start_date",
            [("new_offer_count", "New"), ("exit_count", "Exited")],
            "WEEKLY OFFER FLOW",
        )
    else:
        flow_fig = empty_figure("Flow available from two measured weeks onward")

    # Categorical axis, like the flow. On a temporal axis, Plotly places its
    # own ticks: it showed "Aug 9, Aug 16, Aug 23, Aug 30" when the measured
    # weeks are the 10th, 17th, 24th and 31st -- wrong dates, in English, on
    # a report about France.
    weekly_labeled = [{**r, "week_start_date": r["week_start_date"].strftime("%d/%m")} for r in weekly]
    anonymity_fig = line_chart(
        weekly_labeled, "week_start_date", "anonymous_rate_pct",
        "SHARE OF OFFERS WITH A MASKED EMPLOYER", suffix=" %",
    )

    # ---------- 02 Compensation ----------
    # Filters on annual_salary_plausible rather than a hardcoded
    # job_offer_id. The previous version explicitly excluded offer 4933945,
    # the only known case at the time; there are 15 as of 2026-09-03. A
    # named exclusion doesn't scale, a rule does.
    salary_by_category = humanize_column(execute(con, """
        select employer_category,
               count(*) as n,
               median(salary_min) as median_salary
        from fct_job_offer
        where salary_period = 'annual' and annual_salary_plausible
          and is_canonical_listing
        group by employer_category
        order by median_salary desc
    """), "employer_category", CATEGORY_LABELS)
    kept_categories, excluded_categories = split_by_sample_size(salary_by_category)
    salary_by_category_fig = horizontal_bar_chart(
        kept_categories, "employer_category", "median_salary",
        "MEDIAN SALARY BY EMPLOYER CATEGORY",
        labels=median_labels(kept_categories, "employer_category", "median_salary"),
        note=sample_size_note(excluded_categories, "employer_category"),
    )

    salary_by_experience = humanize_column(execute(con, """
        select required_experience,
               count(*) as n,
               median(salary_min) as median_salary
        from fct_job_offer
        where salary_period = 'annual' and annual_salary_plausible
          and is_canonical_listing
        group by required_experience
        order by median_salary
    """), "required_experience", EXPERIENCE_LABELS)
    kept_experience, excluded_experience = split_by_sample_size(salary_by_experience)
    # Blue alone: two bars of the same measurement, not two series or a
    # delta. The previous version colored "beginner" Vermilion and
    # "experience required" Green, which repurposed the identity's
    # positive/negative coding to pass a value judgment on an experience
    # level.
    salary_by_experience_fig = column_chart(
        kept_experience, "required_experience", "median_salary",
        "MEDIAN SALARY BY EXPERIENCE LEVEL", height=364,
        labels=median_labels(kept_experience, "required_experience", "median_salary"),
        note=sample_size_note(excluded_experience, "required_experience"),
    )

    # ---------- 03 Transparency ----------
    transparency_stat = big_stat_html(
        f"{transparency_rate:.1f} %",
        f"Offers disclosing a salary, out of {offer_count} analyzed",
        centered=True,
    )
    transparency_by_category = humanize_column(execute(con, """
        select employer_category,
               round(100.0 * count(distinct case when salary_mentioned then job_offer_id end)
                     / nullif(count(distinct job_offer_id), 0), 1) as rate_pct
        from fct_job_offer
        where is_canonical_listing
        group by employer_category
        order by rate_pct desc
    """), "employer_category", CATEGORY_LABELS)
    transparency_by_category_fig = horizontal_bar_chart(
        transparency_by_category, "employer_category", "rate_pct",
        "SALARY DISCLOSED, BY CATEGORY", suffix=" %",
    )

    # ---------- 04 Geography ----------
    # Joined on commune_key rather than postal_code: Paris, Lyon and
    # Marseille arrive with no postal code, only their overall commune's
    # INSEE code. Before this fix the report showed 71 Parisian offers;
    # there are 148. The country's three biggest cities were undercounted
    # by half.
    geo = execute(con, """
        select c.commune_name, count(distinct o.job_offer_id) as offer_count
        from fct_job_offer o
        join dim_commune c on c.commune_key = o.commune_key
        where c.commune_name is not null and c.commune_name != 'UNRESOLVED'
        group by c.commune_name
        order by offer_count desc
        limit 10
    """)
    # The only chart counted by OFFER rather than listing, deliberately: a
    # position opened in several communes represents an opportunity in
    # each. Counting it once, in the city of the earliest publication, would
    # erase the others. The exception is noted under the card.
    geo_fig = horizontal_bar_chart(
        geo, "commune_name", "offer_count", "TOP 10 COMMUNES BY OFFER COUNT",
        note="Counted by offer, not by listing like the rest of the report: "
             "a position opened in several communes represents an "
             "opportunity in each.",
    )


    con.close()

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    template = template.replace("<!-- FONTS_PLACEHOLDER -->", f"<style>\n{fonts_css()}\n</style>")
    rendered = string.Template(template).substitute(
        offer_count=offer_count,
        generation_date=datetime.now(timezone.utc).strftime("%d/%m/%Y at %H:%M UTC"),
        kpi_offers=kpi_offers,
        kpi_exits=kpi_exits,
        kpi_anonymity=kpi_anonymity,
        kpi_transparency=kpi_transparency,
        chart_flow=html_figure(flow_fig, first=True),
        chart_anonymity=html_figure(anonymity_fig),
        chart_salary_by_category=html_figure(salary_by_category_fig),
        chart_salary_by_experience=html_figure(salary_by_experience_fig),
        stat_transparency=transparency_stat,
        chart_transparency_by_category=html_figure(transparency_by_category_fig),
        chart_geo=html_figure(geo_fig),
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")

    print(f"Report generated: {OUTPUT_PATH}")
    print(f"  Scope        : {offer_count} offers")
    print(f"  Flow weeks   : {len(flow)}")
    print(f"  Corpus weeks : {len(weekly)}")

if __name__ == "__main__":
    generate()
