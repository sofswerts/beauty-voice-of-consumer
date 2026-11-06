# Databricks notebook source
# MAGIC %md
# MAGIC # 05 · Agente de Insights de Beleza
# MAGIC
# MAGIC Um agente que recebe perguntas em português, decide quais consultas SQL fazer nas tabelas
# MAGIC ouro, executa e responde com os números e a tabela de origem.
# MAGIC
# MAGIC **Como funciona**
# MAGIC 1. O LLM recebe a pergunta e três ferramentas: `listar_tabelas`, `descrever_tabela` e `consultar_sql`.
# MAGIC 2. Ele chama as ferramentas quantas vezes precisar (loop de *tool calling*).
# MAGIC 3. Toda consulta passa por uma trava de segurança: só `SELECT`, só tabelas do schema `beauty`, com limite de linhas.
# MAGIC 4. As execuções ficam registradas no MLflow (traces), para mostrar o raciocínio do agente.
# MAGIC
# MAGIC **Antes de rodar:** abra *Serving* no menu lateral e confira o nome de um endpoint de chat
# MAGIC disponível na sua conta (ex.: `databricks-meta-llama-3-3-70b-instruct`). Ajuste `ENDPOINT` abaixo.

# COMMAND ----------

# MAGIC %pip install --quiet --upgrade openai databricks-sdk mlflow
# MAGIC %restart_python

# COMMAND ----------

import json
import re
import mlflow
from databricks.sdk import WorkspaceClient

ENDPOINT = "databricks-meta-llama-3-3-70b-instruct"
CATALOG, SCHEMA = "workspace", "beauty"
MAX_LINHAS = 50
MAX_PASSOS = 6

client = WorkspaceClient().serving_endpoints.get_open_ai_client()
mlflow.set_experiment(f"/Users/{spark.sql('SELECT current_user()').first()[0]}/beauty-agente-insights")
mlflow.openai.autolog()   # registra cada chamada ao LLM como trace no MLflow

# COMMAND ----------

# MAGIC %md
# MAGIC ### Ferramentas

# COMMAND ----------

def listar_tabelas() -> str:
    linhas = spark.sql(f"SHOW TABLES IN {CATALOG}.{SCHEMA}").collect()
    tabelas = [r.tableName for r in linhas if r.tableName.startswith("gold_")]
    saida = []
    for t in tabelas:
        comentario = spark.sql(f"DESCRIBE TABLE EXTENDED {CATALOG}.{SCHEMA}.{t}") \
                          .filter("col_name = 'Comment'").collect()
        saida.append({"tabela": f"{CATALOG}.{SCHEMA}.{t}",
                      "descricao": comentario[0].data_type if comentario else ""})
    return json.dumps(saida, ensure_ascii=False)


def descrever_tabela(tabela: str) -> str:
    nome = tabela.split(".")[-1]
    if not re.fullmatch(r"gold_\w+", nome):
        return "Erro: só é permitido descrever tabelas gold_*."
    df = spark.table(f"{CATALOG}.{SCHEMA}.{nome}")
    exemplo = [r.asDict() for r in df.limit(3).collect()]
    return json.dumps({"colunas": dict(df.dtypes), "exemplo": exemplo}, ensure_ascii=False, default=str)


PROIBIDO = re.compile(r"\b(insert|update|delete|merge|drop|create|alter|truncate|grant|revoke|copy|optimize|vacuum)\b", re.I)

def consultar_sql(sql: str) -> str:
    sql_limpo = sql.strip().rstrip(";")
    if not re.match(r"^\s*(select|with)\b", sql_limpo, re.I) or PROIBIDO.search(sql_limpo) or ";" in sql_limpo:
        return "Erro: só consultas SELECT de uma instrução são permitidas."
    tabelas_citadas = re.findall(r"\b(?:from|join)\s+([\w.`]+)", sql_limpo, re.I)
    for t in tabelas_citadas:
        if not t.replace("`", "").startswith(f"{CATALOG}.{SCHEMA}."):
            return f"Erro: use o nome completo das tabelas, ex.: {CATALOG}.{SCHEMA}.gold_kpis_marca"
    try:
        linhas = spark.sql(f"SELECT * FROM ({sql_limpo}) LIMIT {MAX_LINHAS}").collect()
    except Exception as e:
        return f"Erro na consulta: {str(e)[:300]}"
    return json.dumps([r.asDict() for r in linhas], ensure_ascii=False, default=str)


FERRAMENTAS_PY = {"listar_tabelas": listar_tabelas, "descrever_tabela": descrever_tabela, "consultar_sql": consultar_sql}

FERRAMENTAS = [
    {"type": "function", "function": {
        "name": "listar_tabelas",
        "description": "Lista as tabelas analíticas disponíveis e o que cada uma contém.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "descrever_tabela",
        "description": "Mostra as colunas, tipos e 3 linhas de exemplo de uma tabela.",
        "parameters": {"type": "object",
                       "properties": {"tabela": {"type": "string", "description": "Nome completo da tabela"}},
                       "required": ["tabela"]}}},
    {"type": "function", "function": {
        "name": "consultar_sql",
        "description": f"Executa uma consulta SELECT em Databricks SQL e devolve até {MAX_LINHAS} linhas.",
        "parameters": {"type": "object",
                       "properties": {"sql": {"type": "string"}},
                       "required": ["sql"]}}},
]

# COMMAND ----------

# MAGIC %md
# MAGIC ### O agente

# COMMAND ----------

INSTRUCOES = f"""Você é um analista de insights do consumidor de beleza.
Responda sempre em português, de forma curta e objetiva.

Regras:
- Use apenas dados obtidos pelas ferramentas. Nunca invente números.
- Antes de consultar, use listar_tabelas e descrever_tabela para entender as colunas.
- Use sempre o nome completo das tabelas ({CATALOG}.{SCHEMA}.<tabela>).
- Ao final, cite a tabela usada e o número de reviews por trás de cada número.
- Se os dados não respondem à pergunta, diga isso claramente e sugira o que seria necessário.
- Contexto: reviews da Sephora US, retrato de março de 2023. A coluna grupo_loreal indica marcas do Grupo L'Oréal.
"""

@mlflow.trace(name="agente_insights")
def perguntar(pergunta: str, verbose: bool = True) -> str:
    mensagens = [{"role": "system", "content": INSTRUCOES},
                 {"role": "user", "content": pergunta}]
    for _ in range(MAX_PASSOS):
        resposta = client.chat.completions.create(
            model=ENDPOINT, messages=mensagens, tools=FERRAMENTAS, temperature=0)
        msg = resposta.choices[0].message
        if not msg.tool_calls:
            return msg.content
        mensagens.append(msg.model_dump(exclude_none=True))
        for chamada in msg.tool_calls:
            args = json.loads(chamada.function.arguments or "{}")
            if verbose:
                print(f"→ {chamada.function.name}({args})")
            resultado = FERRAMENTAS_PY[chamada.function.name](**args)
            mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": resultado})
    return "Não consegui chegar a uma resposta dentro do limite de passos."

# COMMAND ----------

print(perguntar("Quais 5 marcas do Grupo L'Oréal têm a maior taxa de recomendação?"))

# COMMAND ----------

print(perguntar("Em quais categorias o Grupo L'Oréal fica abaixo das demais marcas para pele oleosa?"))

# COMMAND ----------

# MAGIC %md
# MAGIC ### Avaliação simples
# MAGIC Perguntas com resposta conhecida: comparamos a resposta do agente com uma consulta SQL feita à mão.
# MAGIC Anote o acerto no README (ex.: "acertou 8 de 10"). Isso mostra cuidado com a confiabilidade do agente.

# COMMAND ----------

casos = [
    ("Qual marca tem mais reviews?",
     f"SELECT brand_name FROM {CATALOG}.{SCHEMA}.gold_kpis_marca ORDER BY n_reviews DESC LIMIT 1"),
    ("Qual faixa de preço tem a maior nota média em Moisturizers?",
     f"SELECT faixa_preco FROM {CATALOG}.{SCHEMA}.gold_faixa_preco WHERE categoria = 'Moisturizers' ORDER BY nota_media DESC LIMIT 1"),
    ("Quantas marcas do Grupo L'Oréal aparecem na tabela de KPIs por marca?",
     f"SELECT COUNT(*) FROM {CATALOG}.{SCHEMA}.gold_kpis_marca WHERE grupo_loreal"),
]

acertos = 0
for pergunta, sql_gabarito in casos:
    esperado = str(spark.sql(sql_gabarito).first()[0])
    resposta = perguntar(pergunta, verbose=False)
    ok = esperado.lower() in resposta.lower()
    acertos += ok
    print(f"{'✔' if ok else '✘'} {pergunta}\n   esperado: {esperado}\n   agente: {resposta[:200]}\n")

print(f"Acertos: {acertos}/{len(casos)}")
mlflow.log_metric("acuracia_agente", acertos / len(casos))
