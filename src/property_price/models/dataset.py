"""Feature lists and data loading for modelling."""
import pandas as pd
import polars as pl

from property_price.logging_config import get_logger, log_metric

from property_price.params import params

log = get_logger(__name__)

FEATURES_PATH = "data/processed/features.parquet"
SEED = params("model")["seed"]  # random seed for reproducibility

CAT = ["type_bien", "code_departement"]

#Was used before feature selection (importance)
#BASE = CAT + ["surface_bati", "pieces", "surface_terrain", "n_dependances", "lat", "lon",
#              "mkt_dept_12m", "mkt_commune_12m", "mkt_section_12m",
#              "mkt_commune_n", "mkt_section_n", "t_months", "month"]

BASE = CAT + ["surface_bati", "pieces", "surface_terrain", "n_dependances", "lat", "lon",
              "mkt_dept_12m", "mkt_commune_12m", "mkt_section_12m",
              "mkt_commune_n", "mkt_section_n"]

DPE_CAT = ["dpe_energie"]

#Was used before feature selection (importance)
#DPE = BASE + DPE_CAT + ["dpe_class", "ges_class", "dpe_ep_m2", "dpe_periode",
#                        "annee_construction", "etage", "nb_niveaux", "dpe_genere_immeuble"]

DPE = BASE + DPE_CAT + ["dpe_class", "ges_class", "dpe_ep_m2", "dpe_periode",
                        "annee_construction", "etage", "nb_niveaux"]

CATEGORICAL = CAT + DPE_CAT
EXTRA = ["y", "valeur", "date", "split", "has_dpe"]


def load(include_test: bool = False) -> pd.DataFrame:
    """
    Load features as pandas, with proper dtypes. Test split excluded by default.
    Args:
        include_test: whether to include the test split in the returned DataFrame
        Returns:
            pd.DataFrame: The loaded features as a pandas DataFrame
    """

    nums = [c for c in DPE if c not in CATEGORICAL]
    lf = pl.scan_parquet(FEATURES_PATH).select(list(dict.fromkeys(DPE + EXTRA)))
    if not include_test:
        lf = lf.filter(pl.col("split") != "test")
    df = (lf.with_columns(pl.col(nums).cast(pl.Float64), pl.col(CATEGORICAL).cast(pl.String))
            .collect().to_pandas())
    for c in CATEGORICAL:
        df[c] = df[c].astype("category")
    df["has_dpe"] = df["has_dpe"].fillna(False).astype(bool)
    log_metric(log, "loaded", rows=len(df),
               **{s: int((df.split == s).sum()) for s in df.split.unique()})
    return df


def sample(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """
    Sample n rows from the DataFrame, with a fixed random seed for reproducibility.
    Args:
        df: The input DataFrame to sample from
        n: The number of rows to sample 
        Returns:
            pd.DataFrame: The sampled DataFrame
    """
    return df.sample(n=min(n, len(df)), random_state=SEED)


def dpe_subset(df: pd.DataFrame, since: str = "2022-01-01") -> pd.DataFrame:
    """
    Filter the DataFrame to include only sales with a matched DPE, from the specified date.
    Args:
        df: The input DataFrame
        since: The date from which to include sales (default: "2022-01-01")
        Returns:
            pd.DataFrame: The filtered DataFrame
    """
    return df[df.has_dpe & (pd.to_datetime(df.date) >= pd.Timestamp(since))]