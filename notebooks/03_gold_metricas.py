# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Ouro: tabelas prontas para o dashboard e para o agente
# MAGIC Cada tabela responde a uma pergunta de negócio.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pergunta: como cada marca performa em avaliação e recomendação?
# MAGIC CREATE OR REPLACE TABLE workspace.beauty.gold_kpis_marca AS
# MAGIC SELECT
# MAGIC   brand_name,
# MAGIC   grupo_loreal,
# MAGIC   COUNT(DISTINCT product_id)            AS n_produtos,
# MAGIC   COUNT(*)                              AS n_reviews,
# MAGIC   ROUND(AVG(rating), 2)                 AS nota_media,
# MAGIC   ROUND(AVG(is_recommended) * 100, 1)   AS pct_recomenda,
# MAGIC   ROUND(AVG(price_usd), 2)              AS preco_medio_usd
# MAGIC FROM workspace.beauty.silver_reviews
# MAGIC GROUP BY brand_name, grupo_loreal
# MAGIC HAVING COUNT(*) >= 100;   -- evita marcas com poucas reviews distorcendo o ranking

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pergunta: quais categorias agradam ou desagradam cada tipo de pele?
# MAGIC CREATE OR REPLACE TABLE workspace.beauty.gold_categoria_tipo_pele AS
# MAGIC SELECT
# MAGIC   secondary_category                    AS categoria,
# MAGIC   COALESCE(skin_type, 'não informado')  AS tipo_pele,
# MAGIC   grupo_loreal,
# MAGIC   COUNT(*)                              AS n_reviews,
# MAGIC   ROUND(AVG(rating), 2)                 AS nota_media,
# MAGIC   ROUND(AVG(is_recommended) * 100, 1)   AS pct_recomenda
# MAGIC FROM workspace.beauty.silver_reviews
# MAGIC GROUP BY ALL
# MAGIC HAVING COUNT(*) >= 50;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pergunta: como o volume e a satisfação evoluem no tempo?
# MAGIC CREATE OR REPLACE TABLE workspace.beauty.gold_tendencia_mensal AS
# MAGIC SELECT
# MAGIC   DATE_TRUNC('month', data_review)      AS mes,
# MAGIC   secondary_category                    AS categoria,
# MAGIC   grupo_loreal,
# MAGIC   COUNT(*)                              AS n_reviews,
# MAGIC   ROUND(AVG(rating), 2)                 AS nota_media
# MAGIC FROM workspace.beauty.silver_reviews
# MAGIC WHERE data_review IS NOT NULL
# MAGIC GROUP BY ALL;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Pergunta: preço mais alto significa consumidor mais satisfeito?
# MAGIC CREATE OR REPLACE TABLE workspace.beauty.gold_faixa_preco AS
# MAGIC SELECT
# MAGIC   faixa_preco,
# MAGIC   secondary_category                    AS categoria,
# MAGIC   COUNT(*)                              AS n_reviews,
# MAGIC   ROUND(AVG(rating), 2)                 AS nota_media,
# MAGIC   ROUND(AVG(is_recommended) * 100, 1)   AS pct_recomenda
# MAGIC FROM workspace.beauty.silver_reviews
# MAGIC GROUP BY ALL;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Comentários nas tabelas: ajudam o dashboard, o Genie e o agente a entender os dados
# MAGIC COMMENT ON TABLE workspace.beauty.gold_kpis_marca IS 'KPIs de satisfação por marca (Sephora US, retrato de mar/2023). Só marcas com 100+ reviews.';
# MAGIC COMMENT ON TABLE workspace.beauty.gold_categoria_tipo_pele IS 'Nota e % de recomendação por categoria e tipo de pele.';
# MAGIC COMMENT ON TABLE workspace.beauty.gold_tendencia_mensal IS 'Volume de reviews e nota média por mês e categoria.';
# MAGIC COMMENT ON TABLE workspace.beauty.gold_faixa_preco IS 'Satisfação por faixa de preço e categoria.';
