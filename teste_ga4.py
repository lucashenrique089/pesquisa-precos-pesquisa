"""
TESTE DO GA4 | Monitor de concorrência
=======================================
Confere se o Python consegue ler o GA4 da Roma Pneus.
Mostra as 15 páginas mais vistas de 01/01/2026 até hoje.

Como rodar (no terminal do VS Code, dentro da pasta do projeto):
    python -m pip install google-analytics-data
    python teste_ga4.py
"""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
import pandas as pd

# Onde está a chave do robô (fica FORA da pasta do projeto, nunca vai para o GitHub)
CHAVE = r"C:\chaves\master-plane-455118-d2-9f2029a6c60f.json"

# ID da propriedade "Roma Pneus" no GA4
PROPRIEDADE = "291387205"


# 1. Entra no GA4 com a chave do robô
cliente = BetaAnalyticsDataClient.from_service_account_file(CHAVE)

# 2. Monta o relatório: páginas mais vistas de janeiro até hoje
pedido = RunReportRequest(
    property=f"properties/{PROPRIEDADE}",
    date_ranges=[DateRange(start_date="2026-01-01", end_date="today")],
    dimensions=[Dimension(name="pagePath")],          # linhas: cada página do site
    metrics=[Metric(name="screenPageViews")],         # coluna: número de visualizações
    limit=15,
)
resposta = cliente.run_report(pedido)

# 3. Transforma a resposta em tabela
tabela = pd.DataFrame([
    {"pagina": linha.dimension_values[0].value,
     "visualizacoes": int(linha.metric_values[0].value)}
    for linha in resposta.rows
]).sort_values("visualizacoes", ascending=False)

print("Conexão com o GA4 funcionando! Páginas mais vistas em 2026:\n")
print(tabela.to_string(index=False))
