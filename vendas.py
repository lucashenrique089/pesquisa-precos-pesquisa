"""
VENDAS FATURADAS | Roma Pneus
==============================
Lê o seu controle de vendas do e-commerce (o Excel que você atualiza no Y:) e prepara
os dados para a aba 💰 Vendas do painel.

O que faz (chamado automaticamente pelo coletor.py a cada coleta):
  1. Abre o Excel no caminho CAMINHO_EXCEL abaixo
  2. JOGA FORA o nome do cliente (e qualquer coluna de CPF, e-mail ou telefone, se um dia existir)
  3. Padroniza as colunas, separa a medida do pneu e calcula o tamanho do pedido (1, 2, 4 pneus...)
  4. Salva vendas.csv na pasta do projeto. É ESTE arquivo que sobe para o GitHub, sem dado pessoal.

Também dá para rodar sozinho, quando só as vendas mudaram:
    python vendas.py

IMPORTANTE (LGPD): o Excel original tem nome de cliente. Ele fica só no Y:, nunca na pasta do
projeto nem no GitHub. O painel só enxerga o vendas.csv, que já sai sem nomes.
"""

import os
import re
import unicodedata
import pandas as pd

# Onde está o seu Excel de vendas. Para pegar o caminho: botão direito no arquivo > "Copiar como caminho"
CAMINHO_EXCEL = r"Y:\MARKETING 2026\E-COMMERCE\Controle de pedidos Ecommerce e estoque\Vendas E-commerce Dash.xlsx"

ARQ_VENDAS = "vendas.csv"
NOME_PADRAO = "vendas e-commerce"      # se o caminho acima falhar, procura um Excel que comece assim

# Nome da coluna no Excel (sem acento e minúsculo) -> nome usado no painel
COLUNAS = {
    "data de movimento": "data",
    "numero nota": "nota",
    "pedido ecommerce": "pedido",
    "codigo item / servico": "codigo",
    "descricao item / servico": "descricao",
    "descricao grupo pecas/servicos": "grupo",
    "descricao sub-grupo": "aro",
    "descricao marca": "marca",
    "quantidade": "qtd",
    "valor liquido": "valor",
}

# Qualquer coluna com uma destas palavras é descartada (dado pessoal)
DADOS_PESSOAIS = ("cliente", "cpf", "cnpj", "email", "e-mail", "telefone", "celular", "endereco", "nome")


def sem_acento(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", texto).strip().lower()


def extrair_medida(descricao):
    """'225/75R16C CARGO MARATHON 2...' -> '225/75R16'. A mesma regra da lista de pneus monitorados."""
    texto = str(descricao).upper()
    achou = re.search(r"(\d{3})/(\d{2})\s*Z?R\s*(\d{2})", texto)
    if achou:
        return f"{achou.group(1)}/{achou.group(2)}R{achou.group(3)}"
    achou = re.search(r"(\d{3})R(\d{2})", texto)              # medidas sem perfil, ex.: 185R14C
    return f"{achou.group(1)}R{achou.group(2)}" if achou else None


def tamanho_pedido(qtd):
    return {1: "1 pneu", 2: "2 pneus", 4: "4 pneus"}.get(int(qtd), "Outras quantidades")


def ler_excel(caminho=CAMINHO_EXCEL):
    """Lê o Excel, remove dados pessoais e devolve a tabela limpa (uma linha por item vendido)."""
    bruto = pd.read_excel(caminho)

    # 1. Remove as colunas de dado pessoal ANTES de qualquer outra coisa
    pessoais = [c for c in bruto.columns if any(p in sem_acento(c) for p in DADOS_PESSOAIS)]
    bruto = bruto.drop(columns=pessoais)

    # 2. Renomeia as colunas conhecidas; as que não estão no mapa são ignoradas
    nomes = {c: COLUNAS[sem_acento(c)] for c in bruto.columns if sem_acento(c) in COLUNAS}
    faltando = set(COLUNAS.values()) - set(nomes.values()) - {"nota"}
    if faltando:
        raise ValueError(f"Colunas não encontradas no Excel: {sorted(faltando)}. "
                         "Algum cabeçalho mudou de nome?")
    vendas = bruto.rename(columns=nomes)[list(nomes.values())]

    # 3. Tipos e limpeza
    vendas["data"] = pd.to_datetime(vendas["data"], errors="coerce", dayfirst=True)
    vendas = vendas.dropna(subset=["data", "pedido"])
    vendas["pedido"] = vendas["pedido"].astype("int64").astype(str)
    vendas["codigo"] = vendas["codigo"].astype(str).str.replace(r"\.0$", "", regex=True)
    vendas["qtd"] = pd.to_numeric(vendas["qtd"], errors="coerce").fillna(0).astype(int)
    vendas["valor"] = pd.to_numeric(vendas["valor"], errors="coerce").fillna(0.0)
    for col in ("descricao", "grupo", "aro", "marca"):
        vendas[col] = vendas[col].astype(str).str.strip()

    # 4. Colunas calculadas
    vendas["medida"] = vendas["descricao"].map(extrair_medida)
    pneus_no_pedido = vendas.groupby("pedido")["qtd"].transform("sum")
    vendas["tamanho_pedido"] = pneus_no_pedido.map(tamanho_pedido)
    vendas["grupo"] = (vendas["grupo"].str.replace("PNEUS ", "", regex=False)
                       .str.replace(" GOODYEAR", "", regex=False)
                       .str.replace("PERFORMACE", "PERFORMANCE", regex=False).str.title()
                       .str.replace("Suv", "SUV", regex=False))
    return vendas.sort_values(["data", "pedido"]).reset_index(drop=True)


def procurar_excel():
    """Reserva: procura o Excel de vendas na pasta do projeto e nas 3 pastas acima dela."""
    pasta = os.path.abspath(os.getcwd())
    for _ in range(4):
        try:
            # aceita espaço ou "_" no nome, maiúsculas ou minúsculas, .xlsx ou .xlsm
            achados = sorted(f for f in os.listdir(pasta)
                             if f.lower().replace("_", " ").startswith(NOME_PADRAO)
                             and f.lower().endswith((".xlsx", ".xlsm")) and not f.startswith("~$"))
        except OSError:
            achados = []
        if achados:
            return os.path.join(pasta, achados[0])
        pasta = os.path.dirname(pasta)
    return None


def coletar_vendas(caminho=CAMINHO_EXCEL):
    """Chamado pelo coletor.py: lê o Excel e salva o vendas.csv (sem dados pessoais)."""
    if not os.path.exists(caminho):
        achado = procurar_excel()
        print()
        if achado is None:
            print(f"Vendas: Excel NÃO encontrado em {caminho}")
            print("   Abra o vendas.py e troque o CAMINHO_EXCEL pelo caminho certo "
                  "(botão direito no Excel > 'Copiar como caminho'). O painel segue com o último vendas.csv.")
            return None
        print(f"Vendas: o caminho do CAMINHO_EXCEL não existe; usei o Excel encontrado em {achado}")
        print("   Para não depender da busca, coloque este caminho no CAMINHO_EXCEL do vendas.py.")
        caminho = achado
    vendas = ler_excel(caminho)
    vendas.to_csv(ARQ_VENDAS, sep=";", index=False, encoding="utf-8-sig")

    def real(v):
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    ultima = vendas["data"].max()
    do_dia = vendas[vendas["data"] == ultima]
    mes = vendas[vendas["data"].dt.to_period("M") == ultima.to_period("M")]
    print()
    print(f"Vendas: {vendas['pedido'].nunique()} pedidos faturados salvos em {ARQ_VENDAS} (sem nomes de clientes).")
    print(f"   Última data na planilha: {ultima:%d/%m/%Y} · {do_dia['pedido'].nunique()} pedido(s), "
          f"{real(do_dia['valor'].sum())}")
    print(f"   No mês: {mes['pedido'].nunique()} pedido(s), {real(mes['valor'].sum())}")
    return vendas


def ler_vendas():
    """Usado pelo painel: lê o vendas.csv salvo pela última coleta."""
    if not os.path.exists(ARQ_VENDAS):
        return None
    vendas = pd.read_csv(ARQ_VENDAS, sep=";", encoding="utf-8-sig",
                         dtype={"pedido": str, "codigo": str, "nota": str})
    vendas["data"] = pd.to_datetime(vendas["data"])
    return vendas


if __name__ == "__main__":
    coletar_vendas()
