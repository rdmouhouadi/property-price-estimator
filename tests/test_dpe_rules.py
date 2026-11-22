import duckdb

from property_price.dpe_rules import CLASSES, class_index, harmonised_sql

con = duckdb.connect()


def scalar(query: str):
    row = con.execute(query).fetchone()
    assert row is not None, f"no row returned by: {query}"
    return row[0]


def label(sql: str, table: str = "") -> str:
    return CLASSES[scalar(f"SELECT {sql} {table}") - 1]


def test_worst_of_energy_and_emissions():
    assert label(class_index("150", "20")) == "C"   # EP C, GES C
    assert label(class_index("50", "60")) == "E"    # EP A, GES E -> worst wins


def test_unchanged_at_base_coefficient():
    assert "CASE" not in harmonised_sql(1.9, [1, 2])[0]


def test_electric_home_relabelled_at_1_7():
    con.execute("""CREATE OR REPLACE TABLE t AS SELECT
        1 AS energie_id, 190.0 AS ep_m2, NULL::DOUBLE AS ep_m2_pef19,
        'D' AS classe_dpe, NULL::VARCHAR AS classe_dpe_pef19, 5.0 AS ges_m2""")
    cls_sql, ep_sql = harmonised_sql(1.7, [1])
    assert label(cls_sql, "FROM t") == "C"          # 190 * 1.7/1.9 = 170 -> C
    assert round(scalar(f"SELECT {ep_sql} FROM t")) == 170