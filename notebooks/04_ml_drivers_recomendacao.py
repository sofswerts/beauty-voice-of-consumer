# Databricks notebook source
# MAGIC %md
# MAGIC # 04 · ML: o que faz um consumidor recomendar (ou não) um produto?
# MAGIC
# MAGIC **Objetivo de negócio:** descobrir, a partir do texto das reviews, quais temas mais pesam
# MAGIC para o consumidor **não recomendar** um produto de skincare. Isso orienta P&D, marketing e
# MAGIC atendimento (ex.: "ressecamento" e "irritação" pesam mais em hidratantes para pele seca?).
# MAGIC
# MAGIC **Modelo:** TF-IDF + Regressão Logística. É simples, rápido e **interpretável**: os pesos
# MAGIC mostram quais palavras puxam para "recomenda" ou "não recomenda".
# MAGIC Tudo registrado no **MLflow** (parâmetros, métricas e modelo).

# COMMAND ----------

import mlflow
import pandas as pd
from pyspark.sql import functions as F
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, f1_score, classification_report

CATALOG, SCHEMA = "workspace", "beauty"
CATEGORIA = None        # ex.: "Moisturizers" para focar numa categoria; None = todas
AMOSTRA = 150_000       # reviews usadas no treino (cabe na memória do serverless)
SEED = 42

# COMMAND ----------

df = spark.table(f"{CATALOG}.{SCHEMA}.silver_reviews").filter("is_recommended IS NOT NULL")
if CATEGORIA:
    df = df.filter(df.secondary_category == CATEGORIA)

pdf = (df.select("review_text", "review_title", "is_recommended", "skin_type", "secondary_category")
         .orderBy(F.rand(SEED))
         .limit(AMOSTRA)
         .toPandas())

pdf["texto"] = (pdf["review_title"].fillna("") + ". " + pdf["review_text"].fillna("")).str.lower()
print(pdf["is_recommended"].value_counts(normalize=True))   # classes desbalanceadas: a maioria recomenda

# COMMAND ----------

X_treino, X_teste, y_treino, y_teste = train_test_split(
    pdf["texto"], pdf["is_recommended"], test_size=0.2, stratify=pdf["is_recommended"], random_state=SEED)

params = dict(ngram_range=(1, 2), min_df=5, max_features=50_000, C=1.0)

mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/beauty-drivers-recomendacao")

with mlflow.start_run(run_name="tfidf_logreg") as run:
    modelo = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=params["ngram_range"], min_df=params["min_df"],
                                  max_features=params["max_features"], stop_words="english")),
        ("clf", LogisticRegression(C=params["C"], class_weight="balanced", max_iter=1000)),
    ])
    modelo.fit(X_treino, y_treino)

    proba = modelo.predict_proba(X_teste)[:, 1]
    pred = (proba >= 0.5).astype(int)
    metricas = {
        "auc": roc_auc_score(y_teste, proba),
        "f1_nao_recomenda": f1_score(y_teste, pred, pos_label=0),
    }
    mlflow.log_params({**params, "amostra": len(pdf), "categoria": CATEGORIA or "todas"})
    mlflow.log_metrics(metricas)
    mlflow.sklearn.log_model(modelo, "modelo", input_example=X_teste.head(3).to_frame())

print(metricas)
print(classification_report(y_teste, pred, target_names=["não recomenda", "recomenda"]))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Drivers: termos que mais puxam para "não recomenda" e para "recomenda"

# COMMAND ----------

vocab = modelo.named_steps["tfidf"].get_feature_names_out()
pesos = modelo.named_steps["clf"].coef_[0]
drivers = pd.DataFrame({"termo": vocab, "peso": pesos}).sort_values("peso")

top_negativos = drivers.head(25).assign(direcao="não recomenda")
top_positivos = drivers.tail(25).assign(direcao="recomenda")
tabela_drivers = pd.concat([top_negativos, top_positivos])
display(tabela_drivers)

# Salva para o dashboard e para o agente
(spark.createDataFrame(tabela_drivers)
      .write.mode("overwrite").saveAsTable(f"{CATALOG}.{SCHEMA}.gold_drivers_recomendacao"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Para escrever no README depois de rodar
# MAGIC - AUC e F1 da classe "não recomenda" (a mais importante para o negócio)
# MAGIC - Os 5 termos negativos mais fortes e o que eles sugerem para a marca
# MAGIC - Uma limitação: o texto está em inglês (Sephora US) e o modelo não entende ironia
