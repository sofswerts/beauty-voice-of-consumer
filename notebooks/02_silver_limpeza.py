# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Prata: limpeza e padronização
# MAGIC - Tipagem das colunas
# MAGIC - Remoção de duplicadas e linhas inválidas
# MAGIC - Flag `grupo_loreal` para comparar o portfólio do grupo com o restante do mercado
# MAGIC - Testes simples de qualidade no final

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG, SCHEMA = "workspace", "beauty"
T = lambda nome: f"{CATALOG}.{SCHEMA}.{nome}"

# COMMAND ----------

# MAGIC %md
# MAGIC ### Marcas do Grupo L'Oréal
# MAGIC Lista montada a partir de informações públicas. **Confira com `SELECT DISTINCT brand_name`**
# MAGIC antes de publicar resultados: os nomes no dataset podem estar escritos de outro jeito,
# MAGIC e o dataset é um retrato de março de 2023.

# COMMAND ----------

MARCAS_GRUPO_LOREAL = [
    "Lancôme", "Kiehl's Since 1851", "Yves Saint Laurent", "Armani Beauty",
    "Urban Decay", "IT Cosmetics", "Valentino", "Prada", "Biotherm", "Mugler",
    "Azzaro", "Ralph Lauren", "Viktor&Rolf", "Maison Margiela", "Youth To The People",
    "Takami", "Aesop", "Kérastase", "Shu Uemura", "SkinCeuticals",
]
marcas_norm = [m.lower() for m in MARCAS_GRUPO_LOREAL]

# COMMAND ----------

def num(c):   return F.col(c).cast("double")
def inteiro(c): return F.col(c).cast("double").cast("int")
def flag(c):  return F.col(c).cast("double").cast("int") == 1

produtos = (spark.table(T("bronze_produtos"))
    .select(
        "product_id", "product_name", "brand_name",
        inteiro("loves_count").alias("loves_count"),
        num("rating").alias("rating"),
        inteiro("reviews").alias("n_reviews"),
        num("price_usd").alias("price_usd"),
        flag("limited_edition").alias("limited_edition"),
        flag("new").alias("new"),
        flag("online_only").alias("online_only"),
        flag("sephora_exclusive").alias("sephora_exclusive"),
        "ingredients", "highlights",
        "primary_category", "secondary_category", "tertiary_category",
    )
    .dropDuplicates(["product_id"])
    .filter(F.col("product_id").isNotNull())
    .withColumn("grupo_loreal", F.lower(F.trim("brand_name")).isin(marcas_norm))
    .withColumn("faixa_preco",
        F.when(F.col("price_usd") < 25, "até US$25")
         .when(F.col("price_usd") < 50, "US$25–50")
         .when(F.col("price_usd") < 100, "US$50–100")
         .otherwise("US$100+"))
)
produtos.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(T("silver_produtos"))

# COMMAND ----------

reviews = (spark.table(T("bronze_reviews"))
    .select(
        "author_id", "product_id",
        inteiro("rating").alias("rating"),
        inteiro("is_recommended").alias("is_recommended"),
        inteiro("total_feedback_count").alias("total_feedback"),
        inteiro("total_pos_feedback_count").alias("feedback_positivo"),
        F.to_date("submission_time").alias("data_review"),
        F.trim("review_title").alias("review_title"),
        F.trim("review_text").alias("review_text"),
        F.lower("skin_type").alias("skin_type"),
        F.lower("skin_tone").alias("skin_tone"),
    )
    .filter(F.col("rating").between(1, 5))
    .filter(F.length("review_text") > 10)
    .dropDuplicates(["author_id", "product_id", "review_text"])
    .join(spark.table(T("silver_produtos"))
             .select("product_id", "brand_name", "secondary_category", "tertiary_category",
                     "price_usd", "faixa_preco", "grupo_loreal"),
          "product_id", "inner")
)
reviews.write.mode("overwrite").option("overwriteSchema", True).saveAsTable(T("silver_reviews"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Testes de qualidade
# MAGIC Falham o notebook se algo estiver errado. Num pipeline (Jobs), isso impede que dados ruins cheguem ao dashboard.

# COMMAND ----------

p = spark.table(T("silver_produtos"))
r = spark.table(T("silver_reviews"))

assert p.count() > 0, "silver_produtos vazia"
assert p.groupBy("product_id").count().filter("count > 1").count() == 0, "product_id duplicado"
assert r.filter(~F.col("rating").between(1, 5)).count() == 0, "rating fora de 1–5"
assert p.filter("grupo_loreal").count() > 0, "nenhuma marca do grupo encontrada: revise MARCAS_GRUPO_LOREAL"

print("Todos os testes passaram.")
display(p.filter("grupo_loreal").groupBy("brand_name").count().orderBy(F.desc("count")))
