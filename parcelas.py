"""
PARCELAMENTO 1x A 12x | Roma Pneus
===================================
O que faz (chamado automaticamente pelo coletor.py a cada coleta):
  - Pneu Store: pede ao servidor deles a tabela real de pagamento (a mesma da janela
    "Veja mais formas de pagamento"). Se falhar, usa a fórmula.
  - Achei Pneus: pede a tabela à API do site. Se falhar, usa a fórmula.
  - Roma: 6% de desconto em qualquer forma de pagamento, até 6x sem juros.
  - Salva parcelas_atuais.csv (foto de hoje) e historico_parcelas.csv (todas as coletas).

A FÓRMULA (regra que as duas concorrentes usam hoje, conferida nos sites):
  - N = número de parcelas sem juros da loja (Pneu Store 10x, Achei Pneus 12x)
  - Em 1x o desconto é de 8% e cai em partes iguais até 0% em Nx:
        desconto(n) = 8% x (N - n) / (N - 1), arredondado em 2 casas
  - Acima de Nx, juros de 1% por parcela a mais (Pneu Store: 11x = 1%, 12x = 2%)

QUANDO A PNEU STORE ATUALIZAR O SITE, o código NEXT_ACTION abaixo muda. O coletor avisa
e passa a usar a fórmula. Para atualizar: F12 > Network > Fetch/XHR > clicar em
"Veja mais formas de pagamento" > botão direito na requisição > Copy as cURL >
copiar o valor de 'next-action' para cá.
"""

from curl_cffi import requests
import pandas as pd
import json
import os
import re
import time

ARQUIVO_PARCELAS = "parcelas_atuais.csv"
ARQUIVO_HIST_PARCELAS = "historico_parcelas.csv"

NEXT_ACTION_PNEUSTORE = "44084b4f994b09c6084888b392596fb057af875f"
API_ACHEI = "https://www.acheipneus.com.br/graphql"

MAX_PARCELAS = 12
DESCONTO_1X = 8.0             # % de desconto em 1x nas concorrentes
JUROS_POR_PARCELA = 1.0       # % de juros por parcela acima do limite sem juros
DESCONTO_ROMA = 0.06
PARCELAS_ROMA = 6


# ============================================================
# FÓRMULA (reserva quando o site não responde)
# ============================================================

def tabela_por_formula(total_sem_juros, parcelas_sem_juros):
    """Reconstrói a tabela de 1x a 12x a partir do total sem juros e do limite de parcelas."""
    if pd.isna(total_sem_juros) or pd.isna(parcelas_sem_juros):
        return []
    N = int(parcelas_sem_juros)
    tabela = []
    for n in range(1, MAX_PARCELAS + 1):
        if n < N:                                         # antes do limite: desconto progressivo
            pct = round(DESCONTO_1X * (N - n) / (N - 1), 2)
            total = total_sem_juros * (1 - pct / 100)
            juros = False
        elif n == N:                                      # no limite: sem juros e sem desconto
            total, juros = total_sem_juros, False
        else:                                             # depois do limite: juros
            total = total_sem_juros * (1 + JUROS_POR_PARCELA * (n - N) / 100)
            juros = True
        tabela.append({"parcelas": n, "total": round(total, 2),
                       "valor_parcela": round(total / n, 2), "juros": juros})
    return tabela


# ============================================================
# PNEU STORE: tabela real pela "server action" do site
# ============================================================

def tabela_pneustore(url, mostrar_resposta=False):
    """Devolve a tabela de cartão (1x a 12x) da Pneu Store, ou [] se não conseguir.
    mostrar_resposta=True imprime o começo da resposta do site (usado pelo diagnostico.py)."""
    url = url.split("?")[0]
    id_produto = re.search(r"-(\d+)$", url)
    if not id_produto:
        return []
    corpo = json.dumps([f"Environment|Front:PDP:pneustore:Payments:{id_produto.group(1)}"])
    try:
        resposta = requests.post(url, data=corpo, impersonate="chrome", timeout=20, headers={
            "accept": "text/x-component",
            "content-type": "text/plain;charset=UTF-8",
            "next-action": NEXT_ACTION_PNEUSTORE,
            "origin": "https://www.pneustore.com.br",
        })
    except Exception:
        return []
    if mostrar_resposta:
        print(f"   Resposta da Pneu Store (código {resposta.status_code}): {resposta.text[:300]!r}")
    if resposta.status_code != 200:
        return []

    # A resposta vem em linhas "0:..." e "1:...". Os meios de pagamento estão na linha "1:"
    for linha in resposta.text.splitlines():
        if not linha.startswith("1:"):
            continue
        try:
            meios = json.loads(linha[2:])
        except json.JSONDecodeError:
            return []
        if not isinstance(meios, list):                   # resposta vazia (null): usa a fórmula
            return []
        for meio in meios:
            if not isinstance(meio, dict):
                continue
            if str(meio.get("code")) == "20":             # 20 = cartão de crédito
                return [{"parcelas": int(p["installmentAmount"]),
                         "total": round(float(p["totalValue"]), 2),
                         "valor_parcela": round(float(p["installmentValue"]), 2),
                         "juros": bool(p.get("withInterest"))}
                        for p in meio.get("installmentValues") or []]
    return []


# ============================================================
# ACHEI PNEUS: tabela pela API (campo price_installments)
# ============================================================

def tabela_achei(sku):
    if sku is None or pd.isna(sku) or str(sku).strip() == "":
        return []
    sku = str(sku).split(".")[0]
    consulta = ('{products(filter:{sku:{eq:"%s"}}){items{price_with_schema{'
                'price_installments{installment_number per_installment price}}}}}' % sku)
    try:
        resposta = requests.get(API_ACHEI, params={"query": consulta}, impersonate="chrome", timeout=20)
        itens = resposta.json()["data"]["products"]["items"]
        lista = itens[0]["price_with_schema"]["price_installments"] or []
    except Exception:
        return []
    tabela = []
    for p in lista:
        n = int(p["installment_number"])
        parcela = float(p["per_installment"])
        total = float(p["price"]) if float(p["price"]) > parcela * 1.5 or n == 1 else parcela * n
        tabela.append({"parcelas": n, "total": round(total, 2), "valor_parcela": round(parcela, 2),
                       "juros": False})
    return tabela


# ============================================================
# COLETA DE TODAS AS LOJAS
# ============================================================

def diferenca_maxima(tabela_a, tabela_b):
    a = {l["parcelas"]: l["total"] for l in tabela_a}
    b = {l["parcelas"]: l["total"] for l in tabela_b}
    comuns = set(a) & set(b)
    return max((abs(a[n] - b[n]) for n in comuns), default=0)


def coletar_parcelas(base, produtos, pausa=2):
    """Monta a tabela de 1x a 12x de cada pneu nas três lojas e salva."""
    data_coleta = base["data_coleta"].iloc[0]
    produtos = produtos.set_index(produtos["item"].astype(int))
    linhas, avisos = [], []

    for item in sorted(base["item"].unique()):
        dados = base[base["item"] == item]
        p = produtos.loc[int(item)]
        info = {"data_coleta": data_coleta, "item": item, "grupo": dados["grupo"].iloc[0],
                "medida": dados["medida"].iloc[0], "modelo": dados["modelo"].iloc[0]}

        # ---- Roma: 6% em tudo, até 6x sem juros ----
        roma_total = dados["roma_preco_pix"].iloc[0]
        for n in range(1, PARCELAS_ROMA + 1):
            linhas.append({**info, "loja": "Roma", "parcelas": n, "total": roma_total,
                           "valor_parcela": round(roma_total / n, 2), "juros": False, "fonte": "regra Roma"})

        # ---- Concorrentes ----
        for _, c in dados.iterrows():
            loja = c["concorrente"]
            if c["conc_disponivel"] != "sim":
                continue
            try:
                formula = tabela_por_formula(c["conc_preco_parcelado"], c["conc_n_parcelas"])
            except Exception:
                formula = []
            try:
                if loja == "PneuStore":
                    real = tabela_pneustore(p["url_pneustore"])
                    time.sleep(pausa)
                else:
                    real = tabela_achei(p.get("sku_acheipneus"))
            except Exception as erro:
                avisos.append(f"{loja} · {info['medida']} {info['modelo']}: erro ao ler a tabela do site ({erro})")
                real = []

            if real:
                tabela, fonte = real, "site"
                if formula and diferenca_maxima(real, formula) > 1.0:
                    avisos.append(f"{loja} · {info['medida']} {info['modelo']}: a tabela do site não segue a "
                                  "fórmula padrão (pode ser promoção de parcelamento)")
            else:
                tabela, fonte = formula, "fórmula"

            for linha in tabela:
                linhas.append({**info, "loja": loja, **linha, "fonte": fonte})

    tabela = pd.DataFrame(linhas)
    if tabela.empty:
        return tabela
    tabela.to_csv(ARQUIVO_PARCELAS, sep=";", index=False, encoding="utf-8-sig")
    ja_existe = os.path.exists(ARQUIVO_HIST_PARCELAS)
    tabela.to_csv(ARQUIVO_HIST_PARCELAS, sep=";", index=False, mode="a",
                  header=not ja_existe, encoding="utf-8-sig")

    fontes = tabela[tabela["loja"] != "Roma"].drop_duplicates(["item", "loja"]).groupby(["loja", "fonte"]).size()
    print()
    print("Parcelamento: tabela de 1x a 12x salva em", ARQUIVO_PARCELAS)
    for (loja, fonte), qtd in fontes.items():
        print(f"   {loja:<12}| {qtd} pneu(s) pela {'tabela real do site' if fonte == 'site' else 'fórmula'}")
    if (fontes.get(("PneuStore", "fórmula"), 0) > 0) and fontes.get(("PneuStore", "site"), 0) == 0:
        print("   Atenção: a tabela real da Pneu Store não respondeu. O código NEXT_ACTION_PNEUSTORE "
              "em parcelas.py pode ter mudado (veja as instruções no topo do arquivo).")
    for aviso in avisos:
        print("   Aviso:", aviso)
    return tabela
