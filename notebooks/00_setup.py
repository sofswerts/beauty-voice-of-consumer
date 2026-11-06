# Databricks notebook source
# MAGIC %md
# MAGIC # 00 · Setup
# MAGIC Cria o schema e o volume onde os arquivos brutos ficam guardados.
# MAGIC
# MAGIC **Depois de rodar:** vá em *Catalog > workspace > beauty > raw* e faça upload dos CSVs do dataset
# MAGIC [Sephora Products and Skincare Reviews (Kaggle)](https://www.kaggle.com/datasets/nadyinky/sephora-products-and-skincare-reviews):
# MAGIC `product_info.csv` e todos os `reviews_*.csv`.

# COMMAND ----------

CATALOG = "workspace"   # catálogo padrão do Databricks Free Edition
SCHEMA = "beauty"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.raw")

print(f"Pronto. Faça upload dos CSVs em /Volumes/{CATALOG}/{SCHEMA}/raw/")

# COMMAND ----------

display(dbutils.fs.ls(f"/Volumes/{CATALOG}/{SCHEMA}/raw/"))
