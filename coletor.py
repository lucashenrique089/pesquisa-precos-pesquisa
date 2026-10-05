"""
COLETOR DE PREÇOS DA CONCORRÊNCIA | Roma Pneus
================================================
O que faz:
  1. Lê a lista de produtos em produtos_monitorados.csv
  2. Busca preço e estoque na Pneu Store (lendo o HTML da página)
  3. Busca preço e estoque na Achei Pneus (pela API GraphQL do site)
  4. Calcula os preços da Roma a partir do preço cheio (6% de desconto, até 6x)
  5. Compara Roma x concorrente e classifica cada item
  6. Salva:
       - base_concorrencia.xlsx  -> a "foto" atual, que o app do Streamlit lê
       - historico_precos.csv    -> acumula todas as coletas (para ver a evolução)

Como usar:
  No VS Code, clique em ▶️ com este arquivo aberto, ou use o botão
  "Atualizar preços" dentro do app do Streamlit.

Bibliotecas necessárias (uma vez só, no terminal):
  python -m pip install curl_cffi beautifulsoup4 pandas openpyxl
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import re
import os
import time


# ============================================================
# CONFIGURAÇÕES (mude aqui se a política de preço mudar)
# ============================================================

ARQUIVO_PRODUTOS = "produtos_monitorados.csv"
ARQUIVO_BASE = "base_concorrencia.xlsx"
ARQUIVO_HISTORICO = "historico_precos.csv"

DESCONTO_ROMA = 0.06      # 6% em qualquer forma de pagamento
PARCELAS_ROMA = 6         # até 6x sem juros
PARCELAS_ACHEI = 12       # Achei Pneus parcela o preço cheio em até 12x
LIMITE = 0.05             # faixa de +-5% para "Na média"
PAUSA_SEGUNDOS = 3        # pausa entre páginas, para não sobrecarregar os sites

API_ACHEI = "https://www.acheipneus.com.br/graphql"


# ============================================================
# FUNÇÕES DE APOIO
# ============================================================

def para_numero(texto):
    """Converte '1.383,10' (texto) em 1383.10 (número)."""
    return float(texto.replace(".", "").replace(",", "."))


def resultado_vazio():
    """Dicionário padrão de um concorrente. Tudo começa vazio."""
    return {
        "nome_anuncio_concorrente": None,
        "conc_disponivel": None,
        "conc_estoque_qtd": None,
        "conc_preco_cheio": None,
        "conc_preco_pix": None,
        "conc_preco_parcelado": None,
        "conc_n_parcelas": None,
        "conc_valor_parcela": None,
    }


# ============================================================
# PNEU STORE: lê o HTML da página do produto
# ============================================================

def extrair_pneustore(url):
    """Recebe a URL de um produto da Pneu Store e devolve disponibilidade e preços."""
    resultado = resultado_vazio()

    # 1. Baixa a página imitando o Chrome (se falhar, pula este pneu)
    try:
        resposta = requests.get(url, impersonate="chrome", timeout=20)
    except Exception as erro:
        print("   Falha ao acessar a Pneu Store:", erro)
        return resultado

    if resposta.status_code != 200:
        print("   Pneu Store bloqueou ou deu erro:", resposta.status_code)
        return resultado

    soup = BeautifulSoup(resposta.text, "html.parser")

    # 2. Nome do anúncio (o título principal da página)
    titulo = soup.select_one("h1")
    if titulo:
        resultado["nome_anuncio_concorrente"] = titulo.get_text(" ", strip=True)

    # 3. Preço PIX (os centavos ficam em outra tag, por isso tiramos os espaços)
    pix = soup.select_one("div[class*='product_in_cash'] h2")
    if pix:
        texto_pix = re.sub(r"\s+", "", pix.get_text("", strip=True))
        achou = re.search(r"[\d.]+,\d{2}", texto_pix)
        if achou:
            resultado["conc_preco_pix"] = para_numero(achou.group())

    # 4. Disponibilidade: com preço = tem estoque. Sem preço, procura o aviso.
    if resultado["conc_preco_pix"] is not None:
        resultado["conc_disponivel"] = "sim"
    else:
        texto_pagina = soup.get_text(" ", strip=True).lower()
        if "sem estoque" in texto_pagina:
            resultado["conc_disponivel"] = "nao"
        else:
            print("   Preço não encontrado e sem aviso de estoque (o layout pode ter mudado)")
        return resultado

    # 5. Preço "de" (o riscado)
    cheio = soup.select_one("div[class*='product_prices'] p:first-of-type")
    if cheio:
        texto_cheio = re.sub(r"\s+", "", cheio.get_text("", strip=True))
        achou = re.search(r"[\d.]+,\d{2}", texto_cheio)
        if achou:
            resultado["conc_preco_cheio"] = para_numero(achou.group())

    # 6. Parcelado: "ou R$ 383,10 em até 12x de R$ 31,92 sem juros"
    parcelado = soup.select_one("div[class*='product_in_installments']")
    if parcelado:
        texto = parcelado.get_text(" ", strip=True)
        achou = re.search(r"R\$\s*([\d.]+,\d{2}).*?(\d+)x de R\$\s*([\d.]+,\d{2})", texto)
        if achou:
            resultado["conc_preco_parcelado"] = para_numero(achou.group(1))
            resultado["conc_n_parcelas"] = int(achou.group(2))
            resultado["conc_valor_parcela"] = para_numero(achou.group(3))

    # 7. Sem preço riscado na página, o preço cheio é o total parcelado
    if resultado["conc_preco_cheio"] is None:
        resultado["conc_preco_cheio"] = resultado["conc_preco_parcelado"]

    return resultado


# ============================================================
# ACHEI PNEUS: consulta a API GraphQL do site
# ============================================================
# O site da Achei Pneus só carrega com JavaScript, então o HTML vem vazio.
# Em vez de ler a página, perguntamos direto à API que o próprio site usa.
# Cada pergunta é pequena (um campo por vez), porque a API recusa
# algumas combinações de campos numa mesma consulta.

def consultar_achei(sku, campos):
    """Faz uma consulta à API da Achei Pneus para um SKU e devolve o produto (ou None)."""
    consulta = '{products(filter:{sku:{eq:"%s"}}){items{%s}}}' % (sku, campos)
    try:
        resposta = requests.get(API_ACHEI, params={"query": consulta},
                                impersonate="chrome", timeout=20)
        dados = resposta.json()
    except Exception as erro:
        print("   Falha ao consultar a Achei Pneus:", erro)
        return None

    itens = (dados.get("data") or {}).get("products", {}) or {}
    itens = itens.get("items") or []
    return itens[0] if itens else None


def extrair_acheipneus(sku):
    """Recebe o SKU da Achei Pneus e devolve disponibilidade, estoque e preços."""
    resultado = resultado_vazio()

    # Sem SKU = produto não encontrado no catálogo deles (indisponível)
    if pd.isna(sku) or str(sku).strip() == "":
        resultado["conc_disponivel"] = "nao"
        return resultado
    sku = str(int(float(sku)))

    # 1. Nome e preço cheio
    produto = consultar_achei(sku, "name price_with_schema{original_price}")
    if produto is None:
        resultado["conc_disponivel"] = "nao"
        return resultado
    resultado["nome_anuncio_concorrente"] = produto.get("name")
    cheio = (produto.get("price_with_schema") or {}).get("original_price")

    # 2. Preço PIX (preço com desconto)
    produto = consultar_achei(sku, "price_with_schema{price_discount{price percent}}")
    desconto = ((produto or {}).get("price_with_schema") or {}).get("price_discount") or {}
    pix = desconto.get("price")

    # 3. Quantidade em estoque
    produto = consultar_achei(sku, "salableQty")
    qtd = (produto or {}).get("salableQty")

    # 4. Monta o resultado
    resultado["conc_estoque_qtd"] = qtd
    if qtd is not None and qtd <= 0:
        resultado["conc_disponivel"] = "nao"
        return resultado
    resultado["conc_disponivel"] = "sim"

    if cheio:
        resultado["conc_preco_cheio"] = round(float(cheio), 2)
        resultado["conc_preco_parcelado"] = round(float(cheio), 2)
        resultado["conc_n_parcelas"] = PARCELAS_ACHEI
        resultado["conc_valor_parcela"] = round(float(cheio) / PARCELAS_ACHEI, 2)
    if pix:
        resultado["conc_preco_pix"] = round(float(pix), 2)

    return resultado


# ============================================================
# MONTA A BASE NO ESQUEMA DA Base_Consolidada
# ============================================================

def classificar(linha):
    """Classificação pelo PIX. Negativo = Roma mais barata."""
    if linha["conc_disponivel"] == "nao":
        return "Concorrente sem estoque"
    if pd.isna(linha["dif_pix_pct"]):
        return "Sem dado"
    if linha["dif_pix_pct"] < -LIMITE:
        return "Competitivo"
    if linha["dif_pix_pct"] > LIMITE:
        return "Caro"
    return "Na média"


def situacao_estoque(linha):
    """Cruza o estoque da Roma com o do concorrente."""
    roma = linha["roma_disponivel"] == "sim"
    conc = linha["conc_disponivel"] == "sim"
    if roma and not conc:
        return "Oportunidade: só a Roma tem"
    if conc and not roma:
        return "Risco: só o concorrente tem"
    if not roma and not conc:
        return "Ninguém tem"
    return "Ambos têm"


def montar_base(coletado, produtos):
    """Junta a coleta com os dados da Roma e calcula as comparações."""
    dados_roma = produtos[["item", "sku_roma", "roma_preco_cheio", "roma_disponivel",
                           "equivalencia_pneustore"]]
    base = coletado.merge(dados_roma, on="item", how="left")

    # Equivalência: na Achei Pneus todos são o mesmo produto
    base["equivalencia"] = base["equivalencia_pneustore"].where(
        base["concorrente"] == "PneuStore", "mesmo produto")
    base = base.drop(columns="equivalencia_pneustore")

    # Preços da Roma a partir do preço cheio
    base["roma_preco_pix"] = (base["roma_preco_cheio"] * (1 - DESCONTO_ROMA)).round(2)
    base["roma_preco_parcelado"] = base["roma_preco_pix"]
    base["roma_n_parcelas"] = PARCELAS_ROMA
    base["roma_valor_parcela"] = (base["roma_preco_parcelado"] / PARCELAS_ROMA).round(2)

    # Desconto que o concorrente dá sobre o preço cheio dele
    base["conc_desconto_pix_pct"] = 1 - base["conc_preco_pix"] / base["conc_preco_cheio"]
    base["conc_desconto_parcelado_pct"] = 1 - base["conc_preco_parcelado"] / base["conc_preco_cheio"]

    # Diferença da Roma contra o concorrente (negativo = Roma mais barata)
    base["dif_pix_pct"] = base["roma_preco_pix"] / base["conc_preco_pix"] - 1
    base["dif_parcelado_pct"] = base["roma_preco_parcelado"] / base["conc_preco_parcelado"] - 1
    base["dif_parcela_pct"] = base["roma_valor_parcela"] / base["conc_valor_parcela"] - 1

    base["classificacao_pix"] = base.apply(classificar, axis=1)
    base["situacao_estoque"] = base.apply(situacao_estoque, axis=1)
    base["data_coleta"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Inteiros que aceitam vazio (sem o ".0")
    for coluna in ["conc_n_parcelas", "conc_estoque_qtd"]:
        base[coluna] = pd.to_numeric(base[coluna], errors="coerce").astype("Int64")

    ordem = ["item", "grupo", "medida", "modelo", "sku_roma", "data_coleta", "concorrente",
             "equivalencia", "roma_disponivel", "conc_disponivel", "conc_estoque_qtd",
             "situacao_estoque",
             "roma_preco_cheio", "roma_preco_pix", "roma_preco_parcelado",
             "roma_n_parcelas", "roma_valor_parcela",
             "nome_anuncio_concorrente", "conc_preco_cheio", "conc_preco_pix",
             "conc_preco_parcelado", "conc_n_parcelas", "conc_valor_parcela",
             "conc_desconto_pix_pct", "conc_desconto_parcelado_pct",
             "dif_pix_pct", "dif_parcelado_pct", "dif_parcela_pct", "classificacao_pix"]
    return base[ordem].sort_values(["concorrente", "item"]).reset_index(drop=True)


def salvar(base):
    """Salva a foto atual (sobrescreve) e acrescenta ao histórico (não apaga)."""
    base.to_excel(ARQUIVO_BASE, sheet_name="Base_Consolidada", index=False)

    ja_existe = os.path.exists(ARQUIVO_HISTORICO)
    base.to_csv(ARQUIVO_HISTORICO, sep=";", index=False, mode="a",
                header=not ja_existe, encoding="utf-8-sig")


# ============================================================
# EXECUÇÃO
# ============================================================

def coletar():
    produtos = pd.read_csv(ARQUIVO_PRODUTOS, sep=";", dtype={"sku_acheipneus": str})
    linhas = []

    for _, produto in produtos.iterrows():
        nome = f'{produto["item"]:>2}. {produto["medida"]} {produto["modelo"]}'
        info = {"item": produto["item"], "grupo": produto["grupo"],
                "medida": produto["medida"], "modelo": produto["modelo"]}

        print("Pneu Store |", nome)
        linhas.append({**info, "concorrente": "PneuStore",
                       **extrair_pneustore(produto["url_pneustore"])})
        time.sleep(PAUSA_SEGUNDOS)

        print("Achei Pneus|", nome)
        linhas.append({**info, "concorrente": "Achei Pneus",
                       **extrair_acheipneus(produto["sku_acheipneus"])})
        time.sleep(1)

    base = montar_base(pd.DataFrame(linhas), produtos)
    salvar(base)

    sem_preco = base[(base["conc_disponivel"] == "sim") & base["conc_preco_pix"].isna()]
    print()
    print(f"Pronto! {len(base)} comparações salvas em {ARQUIVO_BASE}")
    if not sem_preco.empty:
        print("Atenção, disponível mas sem preço (conferir o site):")
        print(sem_preco[["item", "concorrente", "medida", "modelo"]].to_string(index=False))
    return base


if __name__ == "__main__":
    coletar()
