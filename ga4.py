"""
GA4 | Dados do site da Roma Pneus
==================================
Busca no Google Analytics 4 os principais números do site:
  - Resumo dos últimos 7 e 30 dias x período anterior
  - Visão diária (90 dias) e por hora (hoje, ontem e anteontem)
  - Aquisição: grupo de canais, origem e campanha (últimos 7 e 30 dias x período anterior)
  - Páginas mais vistas, termos pesquisados no site e funil de cada produto
  - Tempo real: usuários ativos nos últimos 30 minutos
  - Google Ads (custo, cliques, impressões por campanha), se a conta estiver vinculada ao GA4
  - Usuários e sessões por mês (para a conversão real com as vendas faturadas)

OBS.: compras e receita do GA4 NÃO são usadas no painel. O número oficial de vendas é o
seu controle de faturados (vendas.py).

Usado de dois jeitos:
  1. Pelo coletor.py, que salva tudo em arquivos ga4_*.csv (o painel na nuvem lê esses arquivos)
  2. Pelo app.py, no botão "Atualizar GA4 agora" (consulta ao vivo)

CREDENCIAL (a "senha" do robô):
  - No computador: o arquivo .json no caminho CHAVE abaixo (fora da pasta do projeto)
  - No Streamlit Cloud: em Settings > Secrets, na seção [gcp_service_account] (veja o LEIA-ME)
  NUNCA coloque o arquivo .json na pasta do projeto nem no GitHub.
"""

import os
import re
from urllib.parse import urlparse, parse_qs
import pandas as pd

CHAVE = r"C:\chaves\master-plane-455118-d2-9f2029a6c60f.json"
PROPRIEDADE = "291387205"

ARQ_DIARIO = "ga4_diario.csv"
ARQ_HORARIO = "ga4_horario.csv"
ARQ_AQUISICAO = "ga4_aquisicao.csv"
ARQ_PAGINAS = "ga4_paginas.csv"
ARQ_BUSCAS = "ga4_buscas.csv"
ARQ_ITENS = "ga4_itens.csv"
ARQ_RESUMO = "ga4_resumo.csv"
ARQ_MENSAL = "ga4_mensal.csv"
ARQ_ADS = "ga4_ads.csv"
ARQ_AQUISICAO_DIARIA = "ga4_aquisicao_diaria.csv"


# ============================================================
# CONEXÃO
# ============================================================

def conectar(credencial=None):
    """Abre a conexão com o GA4. credencial = dicionário do Streamlit Secrets (opcional)."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    if credencial:
        return BetaAnalyticsDataClient.from_service_account_info(dict(credencial))
    if os.path.exists(CHAVE):
        return BetaAnalyticsDataClient.from_service_account_file(CHAVE)
    raise FileNotFoundError(f"Chave do GA4 não encontrada em {CHAVE}")


def relatorio(cliente, dimensoes, metricas, periodos, limite=10000, filtro=None):
    """Roda um relatório e devolve um DataFrame com uma coluna por dimensão e por métrica.
    periodos: lista de (inicio, fim, nome). Com mais de um período, o GA4 acrescenta a coluna 'dateRange'."""
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
    opcoes = dict(
        property=f"properties/{PROPRIEDADE}",
        dimensions=[Dimension(name=d) for d in dimensoes],
        metrics=[Metric(name=m) for m in metricas],
        date_ranges=[DateRange(start_date=i, end_date=f, name=n) for i, f, n in periodos],
        limit=limite,
    )
    if filtro is not None:
        opcoes["dimension_filter"] = filtro
    pedido = RunReportRequest(**opcoes)
    resposta = cliente.run_report(pedido)
    nomes_dim = [h.name for h in resposta.dimension_headers]
    nomes_met = [h.name for h in resposta.metric_headers]
    linhas = []
    for r in resposta.rows:
        linha = {n: v.value for n, v in zip(nomes_dim, r.dimension_values)}
        linha.update({n: float(v.value or 0) for n, v in zip(nomes_met, r.metric_values)})
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=nomes_dim + nomes_met)


def filtro_igual(campo, valor):
    from google.analytics.data_v1beta.types import FilterExpression, Filter
    return FilterExpression(filter=Filter(field_name=campo,
                                          string_filter=Filter.StringFilter(value=valor)))


def filtro_contem(campo, valor):
    from google.analytics.data_v1beta.types import FilterExpression, Filter
    return FilterExpression(filter=Filter(field_name=campo, string_filter=Filter.StringFilter(
        value=valor, match_type=Filter.StringFilter.MatchType.CONTAINS)))


# ============================================================
# CONSULTAS
# ============================================================

METRICAS_GERAIS = ["activeUsers", "newUsers", "sessions", "screenPageViews",
                   "ecommercePurchases", "purchaseRevenue"]


def diario(cliente, dias=90):
    tab = relatorio(cliente, ["date"], METRICAS_GERAIS, [(f"{dias}daysAgo", "today", "periodo")])
    tab["data"] = pd.to_datetime(tab["date"], format="%Y%m%d")
    return tab.drop(columns="date").sort_values("data")


def resumo(cliente):
    """Totais dos últimos 7 e 30 dias (até ontem) e do período anterior de mesmo tamanho.
    Usuários não podem ser somados dia a dia (a mesma pessoa volta), por isso a consulta própria."""
    partes = []
    for dias in (7, 30):
        tab = relatorio(cliente, [], METRICAS_GERAIS,
                        [(f"{dias}daysAgo", "yesterday", "atual"),
                         (f"{2 * dias}daysAgo", f"{dias + 1}daysAgo", "anterior")])
        partes.append(tab.assign(dias=dias))
    return pd.concat(partes, ignore_index=True)


def horario(cliente):
    tab = relatorio(cliente, ["date", "hour"], ["activeUsers", "sessions"],
                    [("35daysAgo", "today", "periodo")])
    tab["data"] = pd.to_datetime(tab["date"], format="%Y%m%d")
    tab["hora"] = tab["hour"].astype(int)
    return tab.drop(columns=["date", "hour"]).sort_values(["data", "hora"])


def aquisicao(cliente):
    """Canal, origem e campanha: últimos 7 e 30 dias contra o período anterior de mesmo tamanho."""
    partes = []
    for dias in (7, 30):
        periodos = [(f"{dias}daysAgo", "yesterday", "atual"),
                    (f"{2 * dias}daysAgo", f"{dias + 1}daysAgo", "anterior")]
        for tipo, dimensao in [("Grupo de canais", "sessionPrimaryChannelGroup"),
                               ("Origem", "sessionSource"),
                               ("Campanha", "sessionCampaignName")]:
            try:
                tab = relatorio(cliente, [dimensao], ["sessions", "newUsers", "ecommercePurchases",
                                                      "purchaseRevenue"], periodos, limite=200)
            except Exception:
                if dimensao != "sessionPrimaryChannelGroup":
                    raise
                tab = relatorio(cliente, ["sessionDefaultChannelGroup"], ["sessions", "newUsers",
                                "ecommercePurchases", "purchaseRevenue"], periodos, limite=200)
                dimensao = "sessionDefaultChannelGroup"
            if tab.empty:
                continue
            tab = tab.rename(columns={dimensao: "nome"})
            largo = tab.pivot_table(index="nome", columns="dateRange", aggfunc="sum", fill_value=0)
            largo.columns = [f"{periodo}_{met}" for met, periodo in largo.columns]
            largo = largo.reset_index().assign(tipo=tipo, dias=dias)
            partes.append(largo)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def aquisicao_diaria(cliente, dias=35):
    """Canal, origem e campanha DIA A DIA (últimos 35 dias), para analisar um dia específico no painel."""
    partes = []
    for tipo, dimensao in [("Grupo de canais", "sessionPrimaryChannelGroup"),
                           ("Origem", "sessionSource"),
                           ("Campanha", "sessionCampaignName")]:
        periodo = [(f"{dias}daysAgo", "today", "periodo")]
        try:
            tab = relatorio(cliente, ["date", dimensao], ["sessions", "newUsers"], periodo, limite=50000)
        except Exception:
            if dimensao != "sessionPrimaryChannelGroup":
                raise
            dimensao = "sessionDefaultChannelGroup"
            tab = relatorio(cliente, ["date", dimensao], ["sessions", "newUsers"], periodo, limite=50000)
        if tab.empty:
            continue
        tab["data"] = pd.to_datetime(tab["date"], format="%Y%m%d")
        partes.append(tab.rename(columns={dimensao: "nome"}).drop(columns="date").assign(tipo=tipo))
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(
        columns=["nome", "sessions", "newUsers", "data", "tipo"])


def paginas(cliente, dias=30):
    tab = relatorio(cliente, ["pagePath"], ["screenPageViews", "activeUsers", "sessions"],
                    [(f"{dias}daysAgo", "today", "periodo")], limite=300)
    return tab.sort_values("screenPageViews", ascending=False)


def buscas(cliente, dias=30):
    """Termos pesquisados no site. Primeiro pelo evento de busca do GA4; se vier vazio,
    lê o termo direto do endereço das páginas de busca (?q=...)."""
    try:
        tab = relatorio(cliente, ["searchTerm"], ["eventCount"], [(f"{dias}daysAgo", "today", "periodo")],
                        limite=500, filtro=filtro_igual("eventName", "view_search_results"))
        tab = tab[~tab["searchTerm"].isin(["", "(not set)"])]
    except Exception:
        tab = pd.DataFrame()
    if not tab.empty:
        tab = tab.rename(columns={"searchTerm": "termo", "eventCount": "buscas"})
    else:
        bruto = relatorio(cliente, ["pagePathPlusQueryString"], ["screenPageViews"],
                          [(f"{dias}daysAgo", "today", "periodo")], limite=2000,
                          filtro=filtro_contem("pagePathPlusQueryString", "q="))
        termos = []
        for _, l in bruto.iterrows():
            q = parse_qs(urlparse(l["pagePathPlusQueryString"]).query).get("q")
            if q:
                termos.append({"termo": q[0], "buscas": l["screenPageViews"]})
        tab = pd.DataFrame(termos, columns=["termo", "buscas"])
    if tab.empty:
        return pd.DataFrame(columns=["termo", "buscas", "medida"])
    tab["termo"] = tab["termo"].str.strip().str.lower()
    tab = tab.groupby("termo", as_index=False)["buscas"].sum().sort_values("buscas", ascending=False)
    tab["medida"] = tab["termo"].map(extrair_medida)
    return tab


def extrair_medida(texto):
    """Reconhece medidas de pneu no texto buscado: '175/65r14', '175 65 14', '1756514'..."""
    achou = re.search(r"(\d{3})\s*[/ -]?\s*(\d{2})\s*[/ r-]?\s*r?\s*(\d{2})", str(texto).lower())
    return f"{achou.group(1)}/{achou.group(2)}R{achou.group(3)}" if achou else None


def itens(cliente, dias=30):
    tab = relatorio(cliente, ["itemId", "itemName"],
                    ["itemsViewed", "itemsAddedToCart", "itemsPurchased", "itemRevenue"],
                    [(f"{dias}daysAgo", "today", "periodo")], limite=500)
    return tab.sort_values("itemsViewed", ascending=False)


def mensal(cliente):
    """Usuários e sessões por mês desde janeiro do ano passado (para a conversão real na aba Vendas)."""
    inicio = f"{pd.Timestamp.today().year - 1}-01-01"
    tab = relatorio(cliente, ["yearMonth"], ["activeUsers", "sessions"], [(inicio, "today", "periodo")])
    tab["mes"] = pd.to_datetime(tab["yearMonth"], format="%Y%m")
    return tab.drop(columns="yearMonth").sort_values("mes")


def google_ads(cliente, dias=400):
    """Custo, cliques e impressões do Google Ads por dia e campanha.
    Só funciona se a conta do Google Ads estiver VINCULADA ao GA4
    (GA4 > Administrador > Vinculações de produtos > Vinculações do Google Ads).
    Sem vínculo, volta uma tabela vazia e o painel avisa."""
    periodo = [(f"{dias}daysAgo", "yesterday", "periodo")]
    metricas = ["advertiserAdCost", "advertiserAdClicks", "advertiserAdImpressions"]
    tentativas = [["date", "sessionGoogleAdsCampaignName", "sessionGoogleAdsCampaignType"],
                  ["date", "sessionGoogleAdsCampaignName"],
                  ["date"]]
    tab = pd.DataFrame()
    for dims in tentativas:                      # se o GA4 recusar uma combinação, tenta uma mais simples
        try:
            tab = relatorio(cliente, dims, metricas, periodo)
            break
        except Exception:
            continue
    colunas = ["data", "campanha", "tipo_campanha", "custo", "cliques", "impressoes"]
    if tab.empty or tab["advertiserAdCost"].sum() == 0:
        return pd.DataFrame(columns=colunas)
    tab = tab.rename(columns={"sessionGoogleAdsCampaignName": "campanha",
                              "sessionGoogleAdsCampaignType": "tipo_campanha",
                              "advertiserAdCost": "custo", "advertiserAdClicks": "cliques",
                              "advertiserAdImpressions": "impressoes"})
    for col in ("campanha", "tipo_campanha"):
        if col not in tab:
            tab[col] = "(todas)"
    tab["data"] = pd.to_datetime(tab["date"], format="%Y%m%d")
    tab = tab[tab["custo"] + tab["cliques"] + tab["impressoes"] > 0]
    return tab[colunas].sort_values(["data", "campanha"])


def tempo_real(cliente):
    """Usuários ativos nos últimos 30 minutos e as páginas que estão vendo agora."""
    from google.analytics.data_v1beta.types import RunRealtimeReportRequest, Dimension, Metric
    total = cliente.run_realtime_report(RunRealtimeReportRequest(
        property=f"properties/{PROPRIEDADE}", metrics=[Metric(name="activeUsers")]))
    ativos = int(total.rows[0].metric_values[0].value) if total.rows else 0
    por_pagina = cliente.run_realtime_report(RunRealtimeReportRequest(
        property=f"properties/{PROPRIEDADE}", dimensions=[Dimension(name="unifiedScreenName")],
        metrics=[Metric(name="activeUsers")], limit=10))
    paginas_agora = pd.DataFrame([{"pagina": r.dimension_values[0].value,
                                   "usuarios": int(r.metric_values[0].value)} for r in por_pagina.rows],
                                 columns=["pagina", "usuarios"])
    return ativos, paginas_agora


# ============================================================
# TUDO DE UMA VEZ
# ============================================================

def buscar_tudo(credencial=None):
    """Roda todas as consultas e devolve um dicionário de tabelas."""
    cliente = conectar(credencial)
    dados = {"resumo": resumo(cliente), "diario": diario(cliente), "horario": horario(cliente),
             "aquisicao": aquisicao(cliente),
             "paginas": paginas(cliente), "buscas": buscas(cliente), "itens": itens(cliente)}
    for chave, funcao in (("mensal", mensal), ("ads", google_ads), ("aquisicao_diaria", aquisicao_diaria)):     # opcionais: não travam o resto
        try:
            dados[chave] = funcao(cliente)
        except Exception as erro:
            print(f"GA4: não consegui ler '{chave}' |", erro)
            dados[chave] = pd.DataFrame()
    try:
        dados["ativos_agora"], dados["paginas_agora"] = tempo_real(cliente)
    except Exception:
        dados["ativos_agora"], dados["paginas_agora"] = None, pd.DataFrame()
    return dados


ARQUIVOS = {"resumo": ARQ_RESUMO, "diario": ARQ_DIARIO, "horario": ARQ_HORARIO, "aquisicao": ARQ_AQUISICAO,
            "paginas": ARQ_PAGINAS, "buscas": ARQ_BUSCAS, "itens": ARQ_ITENS,
            "mensal": ARQ_MENSAL, "ads": ARQ_ADS, "aquisicao_diaria": ARQ_AQUISICAO_DIARIA}
OPCIONAIS = {"mensal", "ads", "aquisicao_diaria"}      # o painel funciona mesmo sem estes


def coletar_ga4():
    """Chamado pelo coletor.py: busca no GA4 e salva os arquivos ga4_*.csv."""
    dados = buscar_tudo()
    for chave, arquivo in ARQUIVOS.items():
        dados[chave].to_csv(arquivo, sep=";", index=False, encoding="utf-8-sig")
    d = dados["diario"]
    ontem = d.iloc[-2] if len(d) > 1 else d.iloc[-1]
    print()
    print(f"GA4: dados salvos ({len(ARQUIVOS)} arquivos). Ontem: {int(ontem['activeUsers'])} usuários, "
          f"{int(ontem['sessions'])} sessões.")
    ads = dados["ads"]
    if ads.empty:
        print("   Google Ads: sem dados de custo. Confira se o Google Ads está vinculado ao GA4 (veja o LEIA-ME).")
    else:
        ads_ontem = ads[ads["data"] == ads["data"].max()]
        print(f"   Google Ads ({ads['data'].max():%d/%m}): R$ {ads_ontem['custo'].sum():.2f} investidos, "
              f"{int(ads_ontem['cliques'].sum())} cliques.".replace(".", ",", 1))
    if dados["ativos_agora"] is not None:
        print(f"   Usuários no site agora (últimos 30 min): {dados['ativos_agora']}")
    return dados


def ler_arquivos():
    """Lê os arquivos salvos pela última coleta (usado pelo painel)."""
    dados = {}
    for chave, arquivo in ARQUIVOS.items():
        if not os.path.exists(arquivo):
            if chave in OPCIONAIS:
                dados[chave] = pd.DataFrame()
                continue
            return None
        dados[chave] = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig")
    for chave, coluna in (("diario", "data"), ("horario", "data"), ("mensal", "mes"), ("ads", "data"),
                          ("aquisicao_diaria", "data")):
        if coluna in dados[chave]:
            dados[chave][coluna] = pd.to_datetime(dados[chave][coluna])
    dados["ativos_agora"], dados["paginas_agora"] = None, pd.DataFrame()
    return dados


if __name__ == "__main__":
    coletar_ga4()
