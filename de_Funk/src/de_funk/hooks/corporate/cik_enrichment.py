"""
Fix company_id FK using CIK from dim_company.

Problem: Bronze financial statement tables only have ticker, not CIK.
dim_company has company_id = HASH('COMPANY_' + cik) but facts have
HASH('COMPANY_' + ticker). These don't match → join failure.

Solution: After build, join facts by ticker to get correct company_id.

Declared in corporate/entity/model.md:
    hooks:
      after_build:
        - {fn: de_funk.hooks.corporate.cik_enrichment.fix_company_ids}
"""
from de_funk.core.hooks import pipeline_hook
from de_funk.config.logging import get_logger

logger = get_logger(__name__)


@pipeline_hook("after_build", model="corporate.entity")
def fix_company_ids(engine=None, config=None, model=None,
                    dims=None, facts=None, **params):
    """Enrich fact tables with CIK-based company_id from dim_company."""
    if dims is None or facts is None:
        return

    dim_company = dims.get("dim_company")
    if dim_company is None:
        logger.warning("dim_company not found — skipping CIK enrichment")
        return

    backend = model.backend if model else "unknown"

    if backend == "spark":
        company_id_map = dim_company.select("ticker", "company_id")

        for fact_name, fact_df in facts.items():
            if "ticker" in fact_df.columns:
                logger.info(f"Enriching {fact_name} with correct company_id")

                if "company_id" in fact_df.columns:
                    fact_df = fact_df.drop("company_id")

                fact_df = fact_df.join(company_id_map, on="ticker", how="left")

                total = fact_df.count()
                matched = fact_df.filter(fact_df.company_id.isNotNull()).count()
                logger.info(f"  {fact_name}: {matched:,}/{total:,} matched "
                            f"({matched / total * 100:.1f}%)")

                fact_df = fact_df.drop("ticker")
                facts[fact_name] = fact_df

    elif engine is not None:
        # Engine path (DuckDB)
        company_pdf = engine.to_pandas(dim_company)
        id_map = company_pdf[["ticker", "company_id"]].dropna()

        for fact_name, fact_df in facts.items():
            fact_pdf = engine.to_pandas(fact_df)
            if "ticker" in fact_pdf.columns:
                if "company_id" in fact_pdf.columns:
                    fact_pdf = fact_pdf.drop(columns=["company_id"])
                fact_pdf = fact_pdf.merge(id_map, on="ticker", how="left")
                fact_pdf = fact_pdf.drop(columns=["ticker"], errors="ignore")
                facts[fact_name] = fact_pdf
                logger.info(f"  {fact_name}: enriched via Engine")
