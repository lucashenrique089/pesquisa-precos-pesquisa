"""
APP DE INTELIGÊNCIA DE PREÇOS | Roma Pneus
==========================================
Compara a Roma com a Pneu Store e a Achei Pneus nos pneus Goodyear/Kelly
mais vendidos e mais pesquisados.

Como rodar (no terminal do VS Code, dentro da pasta do projeto):
    python -m streamlit run app.py

Arquivos que precisam estar na mesma pasta:
    coletor.py, produtos_monitorados.csv, .streamlit/config.toml
    (base_concorrencia.xlsx e historico_precos.csv são criados pelo coletor)
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from coletor import detectar_sinais, ARQUIVO_PROMOCOES

ARQUIVO_BASE = "base_concorrencia.xlsx"
ARQUIVO_HISTORICO = "historico_precos.csv"

LOJAS = ["Roma", "PneuStore", "Achei Pneus"]
CORES = {"Roma": "#1B7F3B", "PneuStore": "#5B2D90", "Achei Pneus": "#EC6708"}

# Meio de pagamento -> (coluna da Roma, coluna do concorrente, coluna da diferença)
MEIOS = {
    "PIX": ("roma_preco_pix", "conc_preco_pix", "dif_pix_pct"),
    "Total parcelado": ("roma_preco_parcelado", "conc_preco_parcelado", "dif_parcelado_pct"),
    "Valor da parcela": ("roma_valor_parcela", "conc_valor_parcela", "dif_parcela_pct"),
}

st.set_page_config(page_title="Inteligência de Preço | Roma", layout="wide")

# Textos em preto, maiores e em negrito
st.markdown("""
<style>
h1, h2, h3 { color: #000 !important; font-weight: 800 !important; }
.stMarkdown p, .stMarkdown li { color: #111; font-size: 1.05rem; }
.stMarkdown strong { color: #000; }
[data-testid="stMetricLabel"] p { color: #000; font-weight: 700; font-size: 1rem; }
[data-testid="stMetricValue"] { color: #000; font-weight: 800; }
[data-testid="stCaptionContainer"] p { color: #333; font-size: 0.95rem; }
.stRadio label p, .stCheckbox label p { color: #000; font-weight: 600; }
button[data-baseweb="tab"] p { font-size: 1.1rem; font-weight: 700; color: #000; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 1. FUNÇÕES DE APOIO
# ============================================================

def formatar_real(valor):
    if pd.isna(valor):
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_pct(valor):
    if pd.isna(valor):
        return "—"
    return f"{valor:+.1%}".replace(".", ",")


def estilo_grafico(fig, altura):
    """Padroniza fontes grandes, em preto, e fundo limpo."""
    fig.update_layout(
        height=altura,
        font=dict(size=15, color="#111"),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title_text="",
                    font=dict(size=15, color="#111")),
        margin=dict(l=10, r=110, t=50, b=40),
        plot_bgcolor="white",
        bargap=0.25,
    )
    fig.update_yaxes(tickfont=dict(size=15, color="#111"), title_text="")
    fig.update_xaxes(tickfont=dict(size=14, color="#111"), gridcolor="#E5E5E5",
                     title_font=dict(size=15, color="#111"))
    fig.update_traces(textfont=dict(size=14, color="#111"), cliponaxis=False)
    return fig


@st.cache_data
def carregar_base(_marca_tempo):
    """Lê a base. O parâmetro muda quando o arquivo é atualizado, o que limpa o cache."""
    base = pd.read_excel(ARQUIVO_BASE, sheet_name="Base_Consolidada")
    base["pneu"] = base["medida"] + " " + base["modelo"]
    return base


@st.cache_data
def carregar_historico(_marca_tempo):
    if not os.path.exists(ARQUIVO_HISTORICO):
        return pd.DataFrame()
    hist = pd.read_csv(ARQUIVO_HISTORICO, sep=";", encoding="utf-8-sig")
    hist["pneu"] = hist["medida"] + " " + hist["modelo"]
    hist["data_coleta"] = pd.to_datetime(hist["data_coleta"])
    return hist


def precos_por_loja(dados, meio):
    """Monta uma tabela longa: uma linha por pneu e loja, com o preço do meio escolhido."""
    col_roma, col_conc, _ = MEIOS[meio]

    roma = (dados.groupby(["item", "pneu"], as_index=False)
            .agg(preco=(col_roma, "first"), parcelas=("roma_n_parcelas", "first")))
    roma["loja"] = "Roma"

    conc = dados[["item", "pneu", "concorrente", col_conc, "conc_n_parcelas"]].rename(
        columns={"concorrente": "loja", col_conc: "preco", "conc_n_parcelas": "parcelas"})

    longa = pd.concat([roma, conc], ignore_index=True)
    longa["rotulo"] = longa["preco"].map(formatar_real)
    if meio == "Valor da parcela":
        longa["rotulo"] = longa.apply(
            lambda l: l["rotulo"] if pd.isna(l["parcelas"]) else f"{l['rotulo']} ({int(l['parcelas'])}x)",
            axis=1)
    return longa


# ============================================================
# 2. CABEÇALHO E BOTÃO DE ATUALIZAR
# ============================================================

st.title("Inteligência de Preços | Pneus Goodyear")
st.markdown("**Comparativo ROMA x PNEU STORE x ACHEI PNEUS**")

st.sidebar.header("Coleta")
if st.sidebar.button("🔄 Atualizar preços", use_container_width=True,
                     help="Busca os preços agora nos sites. Leva cerca de 2 minutos."):
    import coletor
    with st.spinner("Buscando preços na Roma, Pneu Store e Achei Pneus..."):
        _, sinais_novos = coletor.coletar()
    st.cache_data.clear()
    st.sidebar.success("Preços atualizados!")
    if sinais_novos.empty:
        st.toast("Nenhuma promoção ou mudança de preço nos concorrentes.", icon="✅")
    else:
        st.toast(f"{len(sinais_novos)} promoção(ões) ou mudança(s) de preço detectada(s). "
                 "Veja a aba 📣 Promoções.", icon="📣")
        st.sidebar.warning(f"📣 **{len(sinais_novos)} sinal(is) de promoção** nesta coleta.")

if not os.path.exists(ARQUIVO_BASE):
    st.info("Ainda não há dados coletados. Clique em **🔄 Atualizar preços** na barra lateral "
            "ou rode o `coletor.py` no VS Code.")
    st.stop()

marca_tempo = os.path.getmtime(ARQUIVO_BASE)
base = carregar_base(marca_tempo)
st.sidebar.markdown(f"Última coleta: **{base['data_coleta'].iloc[0]}**")

if "roma_fonte_preco" in base.columns and (base["roma_fonte_preco"] == "planilha").any():
    qtd = base.loc[base["roma_fonte_preco"] == "planilha", "item"].nunique()
    st.sidebar.caption(f"{qtd} pneu(s) da Roma com preço da planilha (sem link do site ou site indisponível).")

# ============================================================
# 3. FILTROS
# ============================================================

st.sidebar.header("Filtros")
concorrentes = st.sidebar.multiselect(
    "Concorrente",
    options=sorted(base["concorrente"].unique()),
    default=sorted(base["concorrente"].unique()),
)
incluir_alternativos = st.sidebar.checkbox(
    "Incluir produto alternativo (EV)",
    value=False,
    help="O EfficientGrip Performance 195/55R16 é comparado com a versão EV na Pneu Store. "
         "Como são produtos diferentes, fica fora por padrão.",
)

base = base[base["concorrente"].isin(concorrentes)].copy()
if base.empty:
    st.warning("Selecione ao menos um concorrente.")
    st.stop()

# Comparação com produto alternativo vira "sem preço" quando o filtro está desligado
if not incluir_alternativos:
    alternativo = base["equivalencia"] != "mesmo produto"
    for col in ["conc_preco_pix", "conc_preco_parcelado", "conc_valor_parcela",
                "dif_pix_pct", "dif_parcelado_pct", "dif_parcela_pct"]:
        base.loc[alternativo, col] = float("nan")

with st.expander("ℹ️ Como ler este painel"):
    st.markdown("""
**O que significa a porcentagem?** Quanto o preço da Roma está acima ou abaixo do concorrente.
- **Negativo (ex: -10%)**: a Roma é mais barata. Quanto mais negativo, melhor para nós.
- **Positivo (ex: +5%)**: a Roma é mais cara.

**Classificação (preço no PIX):**
- **Competitivo**: Roma mais de 5% abaixo do concorrente.
- **Na média**: diferença entre -5% e +5%.
- **Caro**: Roma mais de 5% acima.

**Meios de pagamento:**
- **PIX**: preço à vista. A Roma dá 6% de desconto.
- **Total parcelado**: quanto o cliente paga no total no cartão. A Roma mantém os 6% em até 6x.
- **Valor da parcela**: quanto o cliente paga por mês. Os concorrentes parcelam em 12x,
  por isso a parcela deles tende a ser menor mesmo quando o total é maior.

Na tabela de preços, o **menor preço de cada pneu aparece em verde**.
""")


# ============================================================
# 4. PAINEL DE UM GRUPO (Mais vendidos ou Mais pesquisados)
# ============================================================

def painel(dados, chave):
    """Desenha a análise completa para um grupo de pneus."""
    comparaveis = dados[dados["dif_pix_pct"].notna()]

    # ---------- Indicadores (PIX e parcelado) ----------
    total = len(comparaveis)
    if total:
        competitivos = (comparaveis["classificacao_pix"] == "Competitivo").sum()
        caros = (comparaveis["classificacao_pix"] == "Caro").sum()
        dif_pix_media = comparaveis["dif_pix_pct"].mean()
        mais_barata_parcelado = (comparaveis["dif_parcelado_pct"] < 0).sum()
        dif_parcela_media = comparaveis["dif_parcela_pct"].mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Competitivo no PIX", f"{competitivos} de {total}",
                  help="Comparações em que a Roma está mais de 5% abaixo no PIX.")
        c2.metric("Diferença média no PIX", formatar_pct(dif_pix_media),
                  help="Negativo = Roma mais barata.")
        c3.metric("Mais barata no total parcelado", f"{mais_barata_parcelado} de {total}",
                  help="Em quantas comparações o cliente paga menos na Roma ao parcelar.")
        c4.metric("Parcela Roma x concorrentes", formatar_pct(dif_parcela_media),
                  help="Positivo = parcela da Roma maior (parcelamos em até 6x).")

    # ---------- Escolhas do usuário ----------
    st.subheader("Preços por meio de pagamento")
    e1, e2 = st.columns(2)
    meio = e1.radio("Meio de pagamento", list(MEIOS), horizontal=True, key=f"meio_{chave}")
    visao = e2.radio("Visualização", ["Preço (R$)", "Diferença da Roma (%)"], horizontal=True,
                     key=f"visao_{chave}")
    _, _, col_dif = MEIOS[meio]

    ordem_pneus = dados.sort_values("item")["pneu"].unique().tolist()

    # ---------- Gráfico ----------
    if visao == "Preço (R$)":
        longa = precos_por_loja(dados, meio)
        lojas = [l for l in LOJAS if l in longa["loja"].unique()]
        fig = px.bar(longa, x="preco", y="pneu", color="loja", barmode="group",
                     orientation="h", text="rotulo", color_discrete_map=CORES,
                     category_orders={"pneu": ordem_pneus, "loja": lojas},
                     labels={"preco": f"{meio} (R$)", "loja": "Loja"})
        fig.update_traces(texttemplate="<b>%{text}</b>", textposition="outside")
        fig.update_xaxes(tickprefix="R$ ", separatethousands=True)
        altura = max(420, 95 * len(ordem_pneus))
        st.plotly_chart(estilo_grafico(fig, altura), use_container_width=True,
                        key=f"preco_{chave}")
        st.caption("Barras sem valor = concorrente sem estoque (o site não mostra preço).")
    else:
        grafico = dados[dados[col_dif].notna()].copy()
        grafico["rotulo"] = grafico[col_dif].map(formatar_pct)
        fig = px.bar(grafico, x=col_dif, y="pneu", color="concorrente", barmode="group",
                     orientation="h", text="rotulo", color_discrete_map=CORES,
                     category_orders={"pneu": ordem_pneus},
                     labels={col_dif: f"Diferença da Roma no {meio}", "concorrente": "Concorrente"})
        fig.update_traces(texttemplate="<b>%{text}</b>", textposition="outside")
        fig.add_vline(x=0, line_width=2, line_color="#111")
        fig.update_xaxes(tickformat=".0%")
        altura = max(420, 70 * len(ordem_pneus))
        st.plotly_chart(estilo_grafico(fig, altura), use_container_width=True,
                        key=f"dif_{chave}")
        st.caption("À esquerda da linha preta: Roma mais barata. À direita: Roma mais cara.")

    # ---------- Melhor e pior ----------
    ranking = (dados[dados[col_dif].notna()].groupby("pneu", as_index=False)[col_dif]
               .mean().sort_values(col_dif))
    if not ranking.empty:
        a, b = st.columns(2)
        a.success(f"**Mais competitivo no {meio}:** {ranking.iloc[0]['pneu']} "
                  f"(**{formatar_pct(ranking.iloc[0][col_dif])}**)")
        b.error(f"**Menos competitivo no {meio}:** {ranking.iloc[-1]['pneu']} "
                f"(**{formatar_pct(ranking.iloc[-1][col_dif])}**)")

    # ---------- Tabela de preços lado a lado ----------
    st.subheader(f"Tabela de preços | {meio}")
    longa = precos_por_loja(dados, meio)
    lojas = [l for l in LOJAS if l in longa["loja"].unique()]
    # unstack: transforma a coluna "loja" em uma coluna por loja (uma linha por pneu)
    longa = longa.drop_duplicates(["item", "pneu", "loja"]).set_index(["item", "pneu", "loja"])
    numeros = longa["preco"].unstack("loja").reindex(columns=lojas)
    rotulos = longa["rotulo"].unstack("loja").reindex(columns=lojas)
    rotulos = rotulos.where(numeros.notna(), "Sem estoque")

    difs = (dados.drop_duplicates(["item", "pneu", "concorrente"])
            .set_index(["item", "pneu", "concorrente"])[col_dif].unstack("concorrente"))
    for loja in [l for l in lojas if l != "Roma"]:
        valores = difs[loja] if loja in difs.columns else pd.Series(dtype=float)
        rotulos[f"Dif. {loja}"] = valores.reindex(rotulos.index).map(formatar_pct)

    tabela = rotulos.reset_index().drop(columns="item").rename(columns={"pneu": "Pneu"})
    numeros = numeros.reset_index(drop=True).astype(float)

    def destacar(_):
        """Menor preço de cada linha em verde e negrito; diferenças coloridas."""
        css = pd.DataFrame("color: #111;", index=tabela.index, columns=tabela.columns)
        css["Pneu"] = "color: #000; font-weight: 700;"
        menor = numeros.min(axis=1)
        for loja in lojas:
            iguais = numeros[loja].notna() & (numeros[loja] == menor)
            css.loc[iguais, loja] = "background-color: #DFF3E4; color: #0B5D23; font-weight: 800;"
        for coluna in [c for c in tabela.columns if c.startswith("Dif.")]:
            negativo = tabela[coluna].str.startswith("-")
            positivo = tabela[coluna].str.startswith("+")
            css.loc[negativo, coluna] = "color: #0B5D23; font-weight: 800;"
            css.loc[positivo, coluna] = "color: #B00020; font-weight: 800;"
        return css

    st.dataframe(tabela.style.apply(destacar, axis=None), hide_index=True,
                 use_container_width=True)

    # ---------- Conclusão automática ----------
    if total:
        st.subheader("O que os dados mostram")
        textos = [f"- No **PIX**, a Roma é competitiva em **{competitivos} de {total}** comparações "
                  f"e cara em **{caros}**, com diferença média de **{formatar_pct(dif_pix_media)}**."]
        if dif_parcela_media > 0:
            textos.append(f"- No **parcelado**, o cliente paga menos na Roma em **{mais_barata_parcelado} de {total}** "
                          f"comparações, mas a parcela da Roma é **{formatar_pct(dif_parcela_media)}** em média, "
                          "porque os concorrentes parcelam em 12x. **O preço é vantagem; o número de parcelas é o ponto de atenção.**")
        else:
            textos.append(f"- No **parcelado**, o cliente paga menos na Roma em **{mais_barata_parcelado} de {total}** "
                          "comparações, e a parcela também é menor.")
        st.markdown("\n".join(textos))

    # ---------- Tabela detalhada ----------
    with st.expander("📋 Dados completos"):
        detalhe = dados.copy()
        for c in ["roma_preco_pix", "conc_preco_pix", "roma_preco_parcelado", "conc_preco_parcelado",
                  "roma_valor_parcela", "conc_valor_parcela"]:
            detalhe[c] = detalhe[c].map(formatar_real)
        for c in ["dif_pix_pct", "dif_parcelado_pct", "dif_parcela_pct"]:
            detalhe[c] = detalhe[c].map(formatar_pct)
        detalhe["conc_n_parcelas"] = detalhe["conc_n_parcelas"].map(
            lambda v: "—" if pd.isna(v) else f"{int(v)}x")
        nomes = {
            "medida": "Medida", "modelo": "Modelo", "concorrente": "Concorrente",
            "equivalencia": "Equivalência",
            "roma_preco_pix": "Roma | PIX", "conc_preco_pix": "Conc. | PIX", "dif_pix_pct": "Dif. PIX",
            "roma_preco_parcelado": "Roma | Total parcelado",
            "conc_preco_parcelado": "Conc. | Total parcelado", "dif_parcelado_pct": "Dif. parcelado",
            "roma_valor_parcela": "Roma | Parcela (6x)", "conc_n_parcelas": "Conc. | Nº parcelas",
            "conc_valor_parcela": "Conc. | Parcela", "dif_parcela_pct": "Dif. parcela",
            "classificacao_pix": "Classificação PIX",
        }
        st.dataframe(detalhe[list(nomes)].rename(columns=nomes), hide_index=True,
                     use_container_width=True)


# ============================================================
# 5. PROMOÇÕES: sinais detectados automaticamente nos dados
# ============================================================

LINK_APP = "https://mais-vendidos-e-mais-pesquisados.streamlit.app/"


def montar_email(atual, sinais, nome, data):
    """Monta assunto e corpo do e-mail para o coordenador."""
    comparaveis = atual[atual["dif_pix_pct"].notna()]
    total = len(comparaveis)
    competitivos = (comparaveis["classificacao_pix"] == "Competitivo").sum()
    caros = comparaveis[comparaveis["dif_pix_pct"] > 0].sort_values("dif_pix_pct", ascending=False)
    sem_estoque = atual[atual["conc_disponivel"] == "nao"]

    linhas = [f"Olá{', ' + nome if nome else ''},", "",
              f"Segue o resumo do monitoramento de preços da concorrência (coleta de {data}), "
              f"comparando a Roma com a Pneu Store e a Achei Pneus nos {atual['item'].nunique()} pneus "
              "mais vendidos e mais pesquisados.", "",
              "VISÃO GERAL",
              f"- No PIX, a Roma está competitiva (mais de 5% abaixo) em {competitivos} de {total} comparações, "
              f"com diferença média de {formatar_pct(comparaveis['dif_pix_pct'].mean())}.",
              f"- No total parcelado, o cliente paga menos na Roma em "
              f"{(comparaveis['dif_parcelado_pct'] < 0).sum()} de {total} comparações.", "",
              "PROMOÇÕES E MOVIMENTAÇÕES DOS CONCORRENTES"]
    if sinais.empty:
        linhas.append("- Nenhuma promoção ou mudança de preço relevante desde a última coleta.")
    else:
        for _, s in sinais.iterrows():
            linhas.append(f"- {s['concorrente']} | {s['pneu']}: {s['sinal'][2:].strip()}. {s['detalhe']}.")

    linhas += ["", "PONTOS DE ATENÇÃO (Roma mais cara no PIX)"]
    if caros.empty:
        linhas.append("- Nenhum: a Roma está igual ou abaixo dos concorrentes em todos os itens.")
    else:
        for _, l in caros.head(6).iterrows():
            linhas.append(f"- {l['pneu']}: Roma {formatar_real(l['roma_preco_pix'])} x {l['concorrente']} "
                          f"{formatar_real(l['conc_preco_pix'])} ({formatar_pct(l['dif_pix_pct'])})")

    if not sem_estoque.empty:
        linhas += ["", "CONCORRENTE SEM ESTOQUE"]
        for pneu, grupo in sem_estoque.groupby("pneu"):
            linhas.append(f"- {pneu}: sem estoque na {' e na '.join(grupo['concorrente'])}")

    linhas += ["", f"Painel completo: {LINK_APP}", "", "Atenciosamente,", "Lucas"]
    assunto = f"Monitor de preços da concorrência | {data}"
    return assunto, "\n".join(linhas)


# ============================================================
# 6. ABAS
# ============================================================

aba_vendidos, aba_pesquisados, aba_historico, aba_promocoes = st.tabs(
    ["🏆 Mais vendidos", "🔎 Mais pesquisados", "📈 Histórico de preços", "📣 Promoções"])

with aba_vendidos:
    st.markdown("**Os 10 pneus que a Roma mais vende.**")
    painel(base[base["grupo"] == "Mais vendidos"], "vendidos")

with aba_pesquisados:
    st.markdown("**Medidas mais visualizadas no site (GA4 e busca do Magento) que não estão entre as "
                "mais vendidas: muita procura e pouca conversão.**")
    painel(base[base["grupo"] == "Mais pesquisados"], "pesquisados")

with aba_historico:
    hist = carregar_historico(marca_tempo)
    if hist.empty or hist["data_coleta"].nunique() < 2:
        st.info("O histórico aparece a partir da segunda coleta. Cada vez que o coletor roda, "
                "os preços do dia são acrescentados ao arquivo `historico_precos.csv`.")
    else:
        hist = hist[hist["concorrente"].isin(concorrentes)]
        h1, h2 = st.columns(2)
        ordem = hist.sort_values("item")["pneu"].unique().tolist()
        pneu = h1.selectbox("Pneu", ordem)
        meio_h = h2.radio("Meio de pagamento", list(MEIOS), horizontal=True, key="meio_historico")
        col_roma, col_conc, _ = MEIOS[meio_h]

        h = hist[hist["pneu"] == pneu]
        roma_h = (h.groupby("data_coleta", as_index=False)[col_roma].first()
                  .rename(columns={col_roma: "preco"}).assign(loja="Roma"))
        conc_h = h[["data_coleta", "concorrente", col_conc]].rename(
            columns={"concorrente": "loja", col_conc: "preco"})
        serie = pd.concat([roma_h, conc_h])
        serie["rotulo"] = serie["preco"].map(formatar_real)

        fig = px.line(serie, x="data_coleta", y="preco", color="loja", markers=True, text="rotulo",
                      color_discrete_map=CORES, category_orders={"loja": LOJAS},
                      labels={"data_coleta": "Coleta", "preco": f"{meio_h} (R$)", "loja": "Loja"})
        fig.update_traces(line=dict(width=3), marker=dict(size=10),
                          texttemplate="<b>%{text}</b>", textposition="top center")
        fig.update_yaxes(tickprefix="R$ ")
        st.plotly_chart(estilo_grafico(fig, 480), use_container_width=True, key="grafico_historico")
        st.caption("Pontos faltando = concorrente sem estoque naquela coleta.")

with aba_promocoes:
    st.markdown("**Sinais de promoção detectados automaticamente a cada coleta.**")
    st.caption("O app compara o desconto de cada pneu com o desconto normal da loja e os preços de hoje "
               "com os da coleta anterior. Não precisa digitar nada.")

    hist_p = carregar_historico(marca_tempo)
    if not hist_p.empty:
        hist_p = hist_p[hist_p["concorrente"].isin(concorrentes)]
    sinais = detectar_sinais(base, hist_p)

    if hist_p.empty or hist_p["data_coleta"].nunique() < 2:
        st.info("Na primeira coleta, o app só detecta descontos acima do normal. "
                "A partir da segunda, mostra também quem baixou ou subiu preço e mudou o parcelamento.")

    # ---------- Indicadores ----------
    p1, p2, p3, p4 = st.columns(4)
    contar = lambda texto: sinais["sinal"].str.contains(texto).sum()
    p1.metric("Descontos acima do normal", contar("Desconto"))
    p2.metric("Baixaram o preço", contar("Baixou"))
    p3.metric("Subiram o preço", contar("Subiu"))
    p4.metric("Mudaram o parcelamento", contar("parcelamento"))

    # ---------- Lista de sinais ----------
    if sinais.empty:
        st.success("**Nenhuma promoção ou movimentação relevante** nos concorrentes nesta coleta.")
    else:
        for loja in [l for l in LOJAS if l in sinais["concorrente"].unique()]:
            st.subheader(loja)
            tabela_s = (sinais[sinais["concorrente"] == loja][["pneu", "sinal", "detalhe"]]
                        .rename(columns={"pneu": "Pneu", "sinal": "Sinal", "detalhe": "Detalhe"}))
            st.dataframe(tabela_s, hide_index=True, use_container_width=True)

    # ---------- Histórico de promoções (todas as coletas) ----------
    st.subheader("🗂️ Histórico de promoções")
    if os.path.exists(ARQUIVO_PROMOCOES):
        registro = pd.read_csv(ARQUIVO_PROMOCOES, sep=";", encoding="utf-8-sig")
        registro = registro[registro["concorrente"].isin(concorrentes)]
        registro["data_coleta"] = pd.to_datetime(registro["data_coleta"])
        registro = registro.sort_values(["data_coleta", "concorrente", "item"], ascending=[False, True, True])
        registro["data_coleta"] = registro["data_coleta"].dt.strftime("%d/%m/%Y %H:%M")
        st.caption(f"{len(registro)} sinal(is) registrado(s) desde a primeira coleta. "
                   "O coletor grava aqui automaticamente cada promoção que encontra.")
        st.dataframe(registro[["data_coleta", "concorrente", "pneu", "sinal", "detalhe"]].rename(columns={
                         "data_coleta": "Coleta", "concorrente": "Concorrente", "pneu": "Pneu",
                         "sinal": "Sinal", "detalhe": "Detalhe"}),
                     hide_index=True, use_container_width=True)
    else:
        st.info("Ainda não há promoções registradas. A cada coleta, o coletor grava aqui "
                "o que encontrar (arquivo `historico_promocoes.csv`).")

    # ---------- E-mail para o coordenador ----------
    st.subheader("✉️ E-mail para o coordenador")
    m1, m2 = st.columns(2)
    nome = m1.text_input("Nome do coordenador", placeholder="Ex.: Carlos")
    para = m2.text_input("E-mail do coordenador", placeholder="nome@romapneus.com.br")

    data_txt = pd.to_datetime(base["data_coleta"].iloc[0]).strftime("%d/%m/%Y")
    assunto, corpo = montar_email(base, sinais, nome.strip(), data_txt)
    assunto = st.text_input("Assunto", value=assunto)
    corpo = st.text_area("Texto do e-mail (pode editar antes de enviar)", value=corpo, height=420)

    from urllib.parse import quote
    link = f"mailto:{para.strip()}?subject={quote(assunto)}&body={quote(corpo)}"
    b1, b2 = st.columns(2)
    b1.link_button("📧 Abrir no meu e-mail", link, use_container_width=True,
                   help="Abre o Outlook/Gmail do seu computador com o e-mail pronto.")
    b2.download_button("⬇️ Baixar como .txt", data=f"Assunto: {assunto}\n\n{corpo}",
                       file_name=f"monitor_precos_{data_txt.replace('/', '-')}.txt",
                       use_container_width=True)
    st.caption("Se o botão de e-mail não abrir nada, copie o texto acima e cole no seu e-mail.")
