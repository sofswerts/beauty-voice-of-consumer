# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Bronze: ingestão dos dados brutos
# MAGIC Lê os CSVs do volume e grava como tabelas Delta, sem transformar nada.
# MAGIC Só adicionamos metadados de auditoria (arquivo de origem e data de carga).

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "beauty"
RAW = f"/Volumes/{CATALOG}/{SCHEMA}/raw"

# COMMAND ----------

def ler_csv(caminho):
    # multiLine + escape: o texto das reviews tem quebras de linha e aspas
    return (spark.read
            .option("header", True)
            .option("multiLine", True)
            .option("escape", '"')
            .option("inferSchema", False)   # tudo string na bronze; tipamos na prata
            .csv(caminho))

def com_auditoria(df):
    return (df.withColumn("_arquivo_origem", F.col("_metadata.file_path"))
              .withColumn("_carregado_em", F.current_timestamp()))

def limpar_nomes(df):
    # a coluna de índice exportada pelo pandas vem sem nome (vira "_c0")
    for c in df.columns:
        if c.startswith("_c") or c.strip() == "" or c.startswith("Unnamed"):
            df = df.drop(c)
    return df

# COMMAND ----------

produtos = com_auditoria(limpar_nomes(ler_csv(f"{RAW}/product_info.csv")))
produtos.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{CATALOG}.{SCHEMA}.bronze_produtos")

reviews = com_auditoria(limpar_nomes(ler_csv(f"{RAW}/reviews_*.csv")))
reviews.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(f"{CATALOG}.{SCHEMA}.bronze_reviews")

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'produtos' AS tabela, COUNT(*) AS linhas FROM workspace.beauty.bronze_produtos
# MAGIC UNION ALL
# MAGIC SELECT 'reviews', COUNT(*) FROM workspace.beauty.bronze_reviews
