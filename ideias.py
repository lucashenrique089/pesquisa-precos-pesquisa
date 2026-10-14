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
CUPOM_ROMA5 = 0.05            # cupom de primeira compra (em cascata sobre os 6%)
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

def gerar_ideias(base, campanhas, parcelas=None):
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

    # 3. Parcelamento: jogo de 4 pneus, parcela da Roma (6x) x melhor parcela sem juros do concorrente
    if parcelas is not None and not parcelas.empty:
        sem_juros = parcelas[(parcelas["juros"] == False) & (parcelas["loja"] != "Roma")]
        maior_conc = sem_juros.groupby(["item", "loja"])["parcelas"].max()
        conc = sem_juros.merge(maior_conc.rename("max_sem_juros").reset_index(), on=["item", "loja"])
        conc = conc[conc["parcelas"] == conc["max_sem_juros"]]
        melhor = conc.sort_values("valor_parcela").drop_duplicates("item")
        roma6 = parcelas[(parcelas["loja"] == "Roma") & (parcelas["parcelas"] == PARCELAS_ROMA)]
        comp = roma6.merge(melhor[["item", "loja", "parcelas", "valor_parcela"]], on="item",
                           suffixes=("_roma", "_conc"))
        if not comp.empty:
            comp["dif_jogo"] = (comp["valor_parcela_roma"] - comp["valor_parcela_conc"]) * 4
            media = comp["dif_jogo"].mean()
            exemplo = comp.sort_values("dif_jogo", ascending=False).iloc[0]
            ideia("Média", "Parcelamento",
                  f"Parcela do jogo de 4 pneus fica {formatar_real(media)[:-3]} maior na Roma",
                  f"Na média dos pneus monitorados, o jogo de 4 na Roma (6x) tem parcela {formatar_real(media)} "
                  f"maior que a menor parcela sem juros dos concorrentes. Exemplo: {exemplo['medida']} {exemplo['modelo']}, "
                  f"Roma 6x de {formatar_real(exemplo['valor_parcela_roma'] * 4)} contra {exemplo['loja_conc']} "
                  f"{int(exemplo['parcelas_conc'])}x de {formatar_real(exemplo['valor_parcela_conc'] * 4)}.",
                  "Avaliar 10x sem juros para compras de 4 pneus (ou acima de R$ 1.200) e destacar o valor da parcela "
                  "do jogo completo na página do produto.")
    else:
        parc_conc = base["conc_n_parcelas"].dropna()
        if not parc_conc.empty and parc_conc.max() > PARCELAS_ROMA:
            maior = int(parc_conc.max())
            ideia("Média", "Parcelamento", f"Concorrentes parcelam em até {maior}x, a Roma em {PARCELAS_ROMA}x",
                  "Mesmo quando a Roma é mais barata no total, a parcela fica maior.",
                  f"Avaliar {maior}x sem juros para pedidos acima de R$ 1.200, típico de kit com 4 pneus.")

    # 3b. Cupom ROMA5 na recompra
    pix_conc = base.dropna(subset=["conc_preco_pix"]).groupby("item")["conc_preco_pix"].min()
    roma_pix = base.groupby("item")["roma_preco_pix"].first()
    comuns = pix_conc.index.intersection(roma_pix.index)
    if len(comuns):
        com_cupom = roma_pix[comuns] * (1 - CUPOM_ROMA5)
        hoje = (roma_pix[comuns] <= pix_conc[comuns]).sum()
        com = (com_cupom <= pix_conc[comuns]).sum()
        ideia("Média", "Cupom de desconto", "Liberar o ROMA5 também na recompra",
              f"Hoje o ROMA5 (5% em cascata sobre os 6%) vale só na primeira compra. No mercado de pneus o cliente "
              f"costuma comprar 2 pneus e voltar meses depois para os outros 2. Com o cupom, a Roma fica abaixo do "
              f"menor PIX dos concorrentes em {com} de {len(comuns)} pneus monitorados (sem o cupom, em {hoje}).",
              "Testar o ROMA5 (ou um cupom de recompra) enviado por e-mail na Brevo 3 a 6 meses depois da compra "
              "de 2 pneus, para fechar o jogo completo na Roma.")

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

    # 10b. Retirada grátis na loja: argumento para os pneus em que a Roma está empatada ou um pouco acima
    empatados = base[(base["dif_pix_pct"] > -LIMITE_CARO) & (base["dif_pix_pct"] <= 0.10)]
    if not empatados.empty:
        ideia("Média", "Mídia e destaque no site", "Usar a retirada grátis em loja como argumento",
              f"Em {empatados['pneu'].nunique()} pneu(s) a Roma está empatada ou até 10% acima no PIX. "
              "Nesses casos, retirar grátis em 3 dias úteis pode compensar a diferença sem mexer no preço.",
              "Colocar o selo 'Retire grátis em 3 dias úteis' na página desses pneus e nos anúncios.")

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
# BIBLIOTECA DE IDEIAS DO MERCADO
# ============================================================
# Ações comuns no e-commerce de pneus, cada uma já no formato de PILOTO:
# pequena, com prazo, custo limitado e forma de medir. Proposta pequena e
# mensurável é mais fácil de aprovar do que mudança de política.

IDEIAS_MERCADO = [
    {"titulo": "Cupom de recompra (fechar o jogo de 4)",
     "como_funciona": "Cupom enviado a quem comprou 2 pneus, para comprar os outros 2 depois.",
     "no_mercado": "Comum em lojas que trabalham com base de clientes e régua de e-mail.",
     "piloto": "ROMA5 liberado para recompra só para quem comprou 2 pneus nos últimos 6 meses, por 60 dias, via Brevo.",
     "custo": "Até 5% sobre o pedido de recompra, só em vendas que acontecerem.",
     "medir": "Taxa de recompra e receita dos clientes que receberam o cupom x período anterior."},
    {"titulo": "Frete grátis em campanha específica",
     "como_funciona": "Frete grátis só para um recorte: categoria, kit, região ou período.",
     "no_mercado": "A Pneu Store usa frete grátis por categoria (moto, carga) e em itens selecionados.",
     "piloto": "Frete grátis só para kit de 4 pneus dos 10 mais vendidos, por 15 dias.",
     "custo": "Frete médio x número de kits vendidos (limitado ao prazo do teste).",
     "medir": "Vendas de kits de 4 durante o teste x mesmo período anterior."},
    {"titulo": "Retirada grátis na loja em destaque",
     "como_funciona": "Transformar a retirada grátis em 3 dias úteis em argumento de venda.",
     "no_mercado": "Lojas com ponto físico destacam retirada e montagem no próprio local.",
     "piloto": "Selo 'Retire grátis em 3 dias úteis' na página dos 14 pneus monitorados e nos anúncios, por 30 dias.",
     "custo": "Praticamente zero (só ajuste de layout e anúncio).",
     "medir": "Conversão das páginas com selo x antes (GA4) e % de pedidos com retirada."},
    {"titulo": "Desconto extra no PIX em itens selecionados",
     "como_funciona": "PIX acima dos 6% padrão só em algumas medidas.",
     "no_mercado": "A Pneu Store anuncia 'PIX até 18%' na página de ofertas da semana.",
     "piloto": "PIX de 8% (2 pontos a mais) em 3 medidas muito pesquisadas e pouco vendidas, por 15 dias.",
     "custo": "2% do valor das vendas dessas 3 medidas no período.",
     "medir": "Conversão dessas medidas no GA4 durante o teste x antes."},
    {"titulo": "Condição especial para o jogo de 4 pneus",
     "como_funciona": "Desconto ou parcelamento maior quando o cliente leva 4 pneus.",
     "no_mercado": "Kits de 2 e 4 pneus com preço por unidade menor são padrão nos marketplaces.",
     "piloto": "Na compra de 4 pneus, 10x sem juros (em vez de 6x), por 30 dias.",
     "custo": "Taxa da operadora nas parcelas 7 a 10, só nos pedidos de 4 pneus.",
     "medir": "Participação de pedidos com 4 pneus e ticket médio."},
    {"titulo": "Montagem ou alinhamento grátis",
     "como_funciona": "Serviço incluso na compra, em loja própria ou oficina parceira.",
     "no_mercado": "Concorrentes oferecem montagem em parceiros e brindes na compra.",
     "piloto": "Alinhamento grátis na compra de 4 pneus com retirada na loja, por 30 dias.",
     "custo": "Custo do serviço por kit vendido.",
     "medir": "Vendas de kits com retirada e avaliação do cliente."},
    {"titulo": "Cupom de carrinho abandonado",
     "como_funciona": "Cupom pequeno enviado só para quem colocou o pneu no carrinho e não comprou.",
     "no_mercado": "Prática comum em réguas de e-mail de e-commerce.",
     "piloto": "E-mail automático na Brevo após 24 horas, com 3% de desconto válido por 48 horas.",
     "custo": "3% só nos carrinhos recuperados.",
     "medir": "Taxa de recuperação de carrinhos antes x depois."},
    {"titulo": "Campanha em data comemorativa",
     "como_funciona": "Ação com prazo curto ligada a uma data (aniversário da loja, Black Friday, Dia dos Pais).",
     "no_mercado": "A Pneu Store roda campanha de aniversário com 'até 2000 OFF'.",
     "piloto": "Esquenta da Black Friday só para a base de e-mail, com 1 condição especial por 7 dias.",
     "custo": "Definido pela condição escolhida, com prazo fechado.",
     "medir": "Vendas da base de e-mail no período e cadastros novos."},
    {"titulo": "Sorteio ou prêmio na compra",
     "como_funciona": "Cada compra vira participação em um sorteio.",
     "no_mercado": "A Pneu Store faz a 'Rota Premiada' (números da sorte a cada compra).",
     "piloto": "Sorteio de 1 jogo de pneus entre quem comprar em novembro.",
     "custo": "Valor do prêmio (fixo e conhecido antes), mais a regularização legal do sorteio.",
     "medir": "Vendas no período e cadastros na base."},
]

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


def montar_email_ideias(ideias, nome, data, link_app, biblioteca=None):
    """Monta assunto e corpo do e-mail com o resumo das ideias."""
    linhas = [f"Olá{', ' + nome if nome else ''},", "",
              f"Segue o resumo das ideias de ação geradas pelo monitor de concorrência (coleta de {data}).", ""]
    if ideias.empty:
        linhas.append("Nesta coleta não há ações urgentes: a Roma está competitiva e não há campanhas "
                      "relevantes dos concorrentes.")
    for prioridade in ["Alta", "Média", "Baixa"]:
        bloco = ideias[ideias["prioridade"] == prioridade]
        if bloco.empty:
            continue
        linhas += [f"PRIORIDADE {prioridade.upper()}"]
        for _, i in bloco.iterrows():
            linhas += [f"- {i['ideia']} ({i['alavanca']})",
                       f"  Por quê: {i['motivo']}",
                       f"  O que fazer: {i['acao']}", ""]
    if biblioteca:
        linhas += ["PROPOSTAS DE PILOTO (pequenas, com prazo e custo limitado)"]
        for b in biblioteca:
            linhas += [f"- {b['titulo']}", f"  Piloto: {b['piloto']}", f"  Custo: {b['custo']}",
                       f"  Como medir: {b['medir']}", ""]
    bf = proxima_black_friday()
    linhas += [f"Faltam {(bf - date.today()).days} dias para a Black Friday ({bf.strftime('%d/%m/%Y')}).", "",
               f"Painel completo: {link_app}", "", "Atenciosamente,", "Lucas"]
    return f"Ideias de ação | Monitor de concorrência | {data}", "\n".join(linhas)
