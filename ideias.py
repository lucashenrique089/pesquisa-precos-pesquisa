"""
IDEIAS DE ESTRATÉGIA E BLACK FRIDAY | Roma Pneus
=================================================
Regras que transformam os dados da coleta (preços, parcelas, estoque e campanhas)
em sugestões de ação para a Roma. Tudo é recalculado a cada coleta.

PARA AJUSTAR: edite a lista ALAVANCAS_ROMA com o que a Roma pode usar de verdade.
Ideias que dependem de uma alavanca fora da lista não aparecem no painel.
"""

from datetime import date, timedelta
import pandas as pd

# ============================================================
# CONFIGURAÇÃO (ajuste com a realidade da Roma)
# ============================================================

ALAVANCAS_ROMA = [
    "Cupom de desconto",
    "Frete grátis",
    "Desconto no PIX",
    "Parcelamento",
    "Kit 2/4 pneus",
    "Brinde / montagem",
    "Mídia e destaque no site",
    "Estoque / compras",
]

DESCONTO_PIX_ROMA = 0.06
PARCELAS_ROMA = 6
LIMITE_CARO = 0.05


def formatar_pct(valor):
    return f"{valor:+.1%}".replace(".", ",")


def formatar_real(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nome_pneu(df):
    return df["medida"] + " " + df["modelo"]


# ============================================================
# IDEIAS DE ESTRATÉGIA
# ============================================================

def gerar_ideias(base, campanhas):
    """Devolve uma tabela de ideias: prioridade, alavanca, ideia, motivo (dados) e ação."""
    ideias = []
    base = base.copy()
    base["pneu"] = nome_pneu(base)
    ativas = campanhas[campanhas["status"] == "ativa"] if not campanhas.empty else campanhas

    def ideia(prioridade, alavanca, titulo, motivo, acao):
        ideias.append({"prioridade": prioridade, "alavanca": alavanca, "ideia": titulo,
                       "motivo": motivo, "acao": acao})

    # 1. Roma mais cara no PIX (mais de 5%)
    caros = base[base["dif_pix_pct"] > LIMITE_CARO].sort_values("dif_pix_pct", ascending=False)
    if not caros.empty:
        lista = "; ".join(f"{l['pneu']} ({formatar_pct(l['dif_pix_pct'])} vs {l['concorrente']})"
                          for _, l in caros.drop_duplicates("pneu").head(5).iterrows())
        ideia("Alta", "Cupom de desconto", "Cupom pontual nos pneus em que a Roma está cara",
              f"{caros['pneu'].nunique()} pneu(s) com a Roma mais de 5% acima no PIX: {lista}.",
              "Criar cupom só para essas medidas, cobrindo a diferença, e divulgar no e-mail e nas campanhas pagas.")

    # 2. Mais pesquisados com preço acima: procura alta e conversão baixa
    pesq = caros[caros["grupo"] == "Mais pesquisados"]
    if not pesq.empty:
        ideia("Alta", "Desconto no PIX", "Converter as medidas mais pesquisadas",
              f"{pesq['pneu'].nunique()} medida(s) muito visitada(s) no site estão mais caras que o concorrente: "
              + ", ".join(pesq["pneu"].unique()) + ".",
              "Testar preço de PIX mais agressivo por 15 dias nessas medidas e medir a conversão no GA4.")

    # 3. Diferença de parcelamento
    parc_conc = base["conc_n_parcelas"].dropna()
    if not parc_conc.empty and parc_conc.max() > PARCELAS_ROMA:
        maior = int(parc_conc.max())
        acima_600 = base[base["roma_preco_cheio"] >= 600]["pneu"].nunique()
        ideia("Média", "Parcelamento", f"Concorrentes parcelam em até {maior}x, a Roma em {PARCELAS_ROMA}x",
              f"Mesmo quando a Roma é mais barata no total, a parcela fica maior. "
              f"{acima_600} pneu(s) monitorado(s) custam R$ 600 ou mais, onde a parcela pesa na decisão.",
              f"Avaliar {maior}x sem juros (ou 10x) para pedidos acima de R$ 1.200, típico de kit com 4 pneus.")

    # 4. Só a Roma tem o pneu
    so_roma = base[(base["roma_disponivel"] == "sim") & (base["conc_disponivel"] == "nao")]
    if not so_roma.empty:
        detalhe = "; ".join(f"{p} (sem estoque na {', '.join(g['concorrente'])})"
                            for p, g in so_roma.groupby("pneu"))
        ideia("Alta", "Mídia e destaque no site", "Aproveitar a falta de estoque do concorrente",
              f"Pneus que só a Roma tem agora: {detalhe}.",
              "Aumentar o investimento em mídia dessas medidas e destacá-las na home enquanto o concorrente não repõe.")

    # 5. Roma sem estoque, concorrente vendendo
    falta = base[(base["roma_disponivel"] == "nao") & (base["conc_disponivel"] == "sim")]
    if not falta.empty:
        ideia("Alta", "Estoque / compras", "Repor pneus que o concorrente está vendendo",
              "A Roma está sem estoque de: " + ", ".join(falta["pneu"].unique()) + ".",
              "Priorizar a reposição com compras e pausar a mídia desses itens até chegar estoque.")

    # 6 a 10. Reação às campanhas ativas dos concorrentes
    def campanhas_do_tipo(tipo):
        return ativas[ativas["tipo"] == tipo] if not ativas.empty else ativas

    regras_campanha = [
        ("Frete grátis", "Alta", "Frete grátis", "Responder à campanha de frete grátis",
         "Oferecer frete grátis nos 10 mais vendidos (ou acima de um valor mínimo) e deixar isso visível no topo do site."),
        ("Black Friday", "Alta", "Cupom de desconto", "Concorrente já está em clima de Black Friday",
         "Antecipar o esquenta da Roma: lista de espera por e-mail, cupom exclusivo para a base e banner com contagem regressiva."),
        ("Data comemorativa", "Média", "Cupom de desconto", "Contra-campanha de data comemorativa",
         "Lançar na mesma semana uma campanha da Roma com cupom ou condição especial, com prazo curto para gerar urgência."),
        ("Sorteio / prêmio", "Baixa", "Brinde / montagem", "Concorrente usando sorteio para engajar",
         "Em vez de sorteio, oferecer benefício garantido: montagem, alinhamento ou brinde na compra do kit de 4 pneus."),
        ("Brinde", "Média", "Brinde / montagem", "Concorrente oferecendo brinde",
         "Avaliar brinde de valor percebido semelhante, ou montagem grátis, nos kits de 4 pneus."),
        ("Desconto / PIX", "Média", "Desconto no PIX", "Concorrente anunciando desconto forte no PIX",
         "Comunicar melhor os 6% da Roma (banner e página de produto) e avaliar PIX maior nos itens onde a Roma está na média."),
    ]
    for tipo, prio, alavanca, titulo, acao in regras_campanha:
        achadas = campanhas_do_tipo(tipo)
        if not achadas.empty:
            nomes = "; ".join(f"{c['concorrente']}: {c['titulo']}" for _, c in achadas.head(4).iterrows())
            ideia(prio, alavanca, titulo, f"Campanha(s) ativa(s): {nomes}.", acao)

    # 11. Kit: sempre útil quando a Roma é competitiva
    competitivos = base[base["classificacao_pix"] == "Competitivo"]["pneu"].nunique()
    if competitivos:
        ideia("Baixa", "Kit 2/4 pneus", "Usar a vantagem de preço para vender kit",
              f"A Roma é competitiva no PIX em {competitivos} pneu(s).",
              "Destacar o preço do kit de 4 pneus nesses itens (economia total em R$) em vez do preço unitário.")

    tabela = pd.DataFrame(ideias, columns=["prioridade", "alavanca", "ideia", "motivo", "acao"])
    tabela = tabela[tabela["alavanca"].isin(ALAVANCAS_ROMA)]
    ordem = {"Alta": 0, "Média": 1, "Baixa": 2}
    return tabela.sort_values("prioridade", key=lambda s: s.map(ordem)).reset_index(drop=True)


# ============================================================
# BLACK FRIDAY
# ============================================================

def data_black_friday(ano):
    """Black Friday = sexta-feira seguinte à quarta quinta-feira de novembro."""
    dia = date(ano, 11, 1)
    while dia.weekday() != 3:          # 3 = quinta-feira
        dia += timedelta(days=1)
    return dia + timedelta(days=22)


def proxima_black_friday(hoje=None):
    hoje = hoje or date.today()
    bf = data_black_friday(hoje.year)
    return bf if bf >= hoje - timedelta(days=3) else data_black_friday(hoje.year + 1)


def indice_precos(hist):
    """Preço médio no PIX de cada loja em cada coleta, em índice (1ª coleta = 100).
    Usa só os pneus presentes em todas as coletas da loja, para a comparação ser justa."""
    if hist.empty:
        return pd.DataFrame()
    hist = hist.copy()
    hist["data_coleta"] = pd.to_datetime(hist["data_coleta"])
    linhas = []
    roma = hist.groupby(["data_coleta", "item"], as_index=False)["roma_preco_pix"].first()
    roma = roma.rename(columns={"roma_preco_pix": "preco"}).assign(loja="Roma")
    conc = hist[["data_coleta", "item", "concorrente", "conc_preco_pix"]].rename(
        columns={"concorrente": "loja", "conc_preco_pix": "preco"})
    tudo = pd.concat([roma, conc]).dropna(subset=["preco"])
    for loja, g in tudo.groupby("loja"):
        n_coletas = g["data_coleta"].nunique()
        itens_fixos = g.groupby("item")["data_coleta"].nunique()
        itens_fixos = itens_fixos[itens_fixos == n_coletas].index
        g = g[g["item"].isin(itens_fixos)]
        if g.empty:
            continue
        media = g.groupby("data_coleta")["preco"].mean().sort_index()
        for data_c, valor in (media / media.iloc[0] * 100).items():
            linhas.append({"data_coleta": data_c, "loja": loja, "indice": round(valor, 1),
                           "pneus": len(itens_fixos)})
    return pd.DataFrame(linhas)


def alertas_black_friday(hist, dias=30):
    """Detecta 'preço maquiado': o concorrente sobe o preço antes da Black Friday
    para depois anunciar desconto. Compara o PIX atual com o menor PIX dos últimos 30 dias."""
    if hist.empty or hist["data_coleta"].nunique() < 2:
        return pd.DataFrame(columns=["concorrente", "pneu", "menor_30d", "atual", "variacao"])
    hist = hist.copy()
    hist["data_coleta"] = pd.to_datetime(hist["data_coleta"])
    ultima = hist["data_coleta"].max()
    janela = hist[hist["data_coleta"] >= ultima - timedelta(days=dias)]
    janela["pneu"] = nome_pneu(janela)
    linhas = []
    for (loja, pneu), g in janela.groupby(["concorrente", "pneu"]):
        atual = g.loc[g["data_coleta"] == ultima, "conc_preco_pix"]
        if atual.empty or pd.isna(atual.iloc[0]):
            continue
        menor = g["conc_preco_pix"].min()
        variacao = atual.iloc[0] / menor - 1
        if variacao >= 0.03:
            linhas.append({"concorrente": loja, "pneu": pneu, "menor_30d": menor,
                           "atual": atual.iloc[0], "variacao": variacao})
    return pd.DataFrame(linhas, columns=["concorrente", "pneu", "menor_30d", "atual", "variacao"])
