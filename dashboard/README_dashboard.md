# Dashboard: Voz do Consumidor em Beleza

Montado no **AI/BI Dashboards do Databricks** (gratuito no Free Edition), lendo as tabelas `gold_*`.
Depois de pronto, tire prints e grave um GIF curto para o README e o site.

## Páginas sugeridas

**1. Visão geral**
- Cards: total de reviews, nota média, % que recomenda
- Barras: % que recomenda por categoria, comparando Grupo L'Oréal e demais marcas

**2. Marcas**
- Dispersão: nota média × % recomenda, tamanho = nº de reviews, cor = grupo_loreal
- Tabela: ranking de marcas com filtro de categoria

**3. Tipo de pele**
- Mapa de calor: categoria × tipo de pele, valor = % recomenda

**4. O que o consumidor diz** (vem do modelo de ML)
- Barras horizontais: 15 termos que mais puxam para "não recomenda" e 15 para "recomenda"

## Queries

```sql
-- Visão geral
SELECT COUNT(*) AS reviews, ROUND(AVG(rating),2) AS nota, ROUND(AVG(is_recommended)*100,1) AS pct_recomenda
FROM workspace.beauty.silver_reviews;

-- Grupo vs mercado por categoria
SELECT categoria,
       IF(grupo_loreal, 'Grupo L''Oréal', 'Demais marcas') AS grupo,
       ROUND(SUM(pct_recomenda * n_reviews) / SUM(n_reviews), 1) AS pct_recomenda
FROM workspace.beauty.gold_categoria_tipo_pele
GROUP BY ALL;

-- Marcas
SELECT * FROM workspace.beauty.gold_kpis_marca ORDER BY n_reviews DESC;

-- Tipo de pele
SELECT categoria, tipo_pele, pct_recomenda, n_reviews
FROM workspace.beauty.gold_categoria_tipo_pele
WHERE tipo_pele <> 'não informado';

-- Drivers do modelo
SELECT termo, peso, direcao FROM workspace.beauty.gold_drivers_recomendacao;
```

## Alternativa com link público
Exporte as tabelas `gold_*` para CSV e monte no **Tableau Public**, que gera um link que qualquer recrutador abre.
