"""
APP DE INTELIGÊNCIA DE PREÇOS | Roma Pneus
==========================================
Compara a Roma com a Pneu Store e a Achei Pneus nos pneus Goodyear/Kelly
mais vendidos e mais pesquisados.

Como rodar (no terminal do VS Code, dentro da pasta do projeto):
    python -m streamlit run app.py

Arquivos que precisam estar na mesma pasta:
    coletor.py, produtos_monitorados.csv
    (base_concorrencia.xlsx e historico_precos.csv são criados pelo coletor)
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px

ARQUIVO_BASE = "base_concorrencia.xlsx"
ARQUIVO_HISTORICO = "historico_precos.csv"

CORES = {"PneuStore": "#5B2D90", "Achei Pneus": "#EC6708", "Roma": "#1B5E20"}

st.set_page_config(page_title="Inteligência de Preço | Roma", layout="wide")


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


# ============================================================
# 2. CABEÇALHO E BOTÃO DE ATUALIZAR
# ============================================================

st.title("Inteligência de Preços | Pneus Goodyear")
st.caption("Comparativo ROMA x PNEU STORE e ACHEI PNEUS")

st.sidebar.header("Coleta")
if st.sidebar.button("🔄 Atualizar preços", use_container_width=True,
                     help="Busca os preços agora nos sites. Leva cerca de 2 minutos."):
    import coletor
    with st.spinner("Buscando preços na Pneu Store e na Achei Pneus..."):
        coletor.coletar()
    st.cache_data.clear()
    st.sidebar.success("Preços atualizados!")

if not os.path.exists(ARQUIVO_BASE):
    st.info("Ainda não há dados coletados. Clique em **🔄 Atualizar preços** na barra lateral "
            "ou rode o `coletor.py` no VS Code.")
    st.stop()

marca_tempo = os.path.getmtime(ARQUIVO_BASE)
base = carregar_base(marca_tempo)
data_coleta = base["data_coleta"].iloc[0]
st.sidebar.caption(f"Última coleta: **{data_coleta}**")

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
    "Incluir comparações com produto alternativo",
    value=False,
    help="Ex.: o EfficientGrip Performance 195/55R16 é comparado com a versão EV na Pneu Store. "
         "Como são produtos diferentes, fica fora das médias por padrão.",
)

base = base[base["concorrente"].isin(concorrentes)]
if base.empty:
    st.warning("Selecione ao menos um concorrente.")
    st.stop()

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

**Estoque:**
- **Oportunidade**: a Roma tem o pneu e o concorrente não.
- **Risco**: o concorrente tem e a Roma está sem estoque.
- Na Achei Pneus, o painel mostra também a **quantidade** em estoque.

Os preços da Roma são calculados a partir do preço cheio cadastrado em `produtos_monitorados.csv`.
""")


# ============================================================
# 4. PAINEL DE UM GRUPO (Mais vendidos ou Mais pesquisados)
# ============================================================

def painel(dados, chave):
    """Desenha a análise completa para um grupo de pneus."""

    # 4.1 Comparações válidas: concorrente com estoque e com preço
    comparaveis = dados[(dados["conc_disponivel"] == "sim") & dados["dif_pix_pct"].notna()]
    if not incluir_alternativos:
        comparaveis = comparaveis[comparaveis["equivalencia"] == "mesmo produto"]

    # ---------- Indicadores ----------
    total = len(comparaveis)
    if total == 0:
        st.warning("Nenhuma comparação de preço disponível para este grupo.")
    else:
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

    # ---------- Estoque ----------
    st.subheader("Estoque: Roma x concorrentes")

    oportunidades = dados[dados["situacao_estoque"] == "Oportunidade: só a Roma tem"]
    riscos = dados[dados["situacao_estoque"] == "Risco: só o concorrente tem"]
    ninguem = dados[dados["situacao_estoque"] == "Ninguém tem"]

    e1, e2, e3 = st.columns(3)
    with e1:
        st.success(f"**Oportunidades: {len(oportunidades)}**  \nA Roma tem, o concorrente não.")
        for _, l in oportunidades.iterrows():
            st.markdown(f"- {l['pneu']} · sem estoque na **{l['concorrente']}**")
    with e2:
        st.error(f"**Riscos: {len(riscos)}**  \nO concorrente tem, a Roma não.")
        for _, l in riscos.iterrows():
            st.markdown(f"- {l['pneu']} · disponível na **{l['concorrente']}**")
    with e3:
        st.warning(f"**Ninguém tem: {len(ninguem)}**  \nRoma e concorrente sem estoque.")
        for _, l in ninguem.iterrows():
            st.markdown(f"- {l['pneu']} · {l['concorrente']}")

    # Matriz de estoque por pneu
    matriz = dados.pivot_table(index=["item", "pneu"], columns="concorrente",
                               values="conc_disponivel", aggfunc="first")
    roma = dados.groupby(["item", "pneu"])["roma_disponivel"].first()
    matriz.insert(0, "Roma", roma)
    matriz = matriz.replace({"sim": "✅ Tem", "nao": "❌ Sem estoque"})
    if "Achei Pneus" in dados["concorrente"].values:
        qtd = (dados[dados["concorrente"] == "Achei Pneus"]
               .set_index(["item", "pneu"])["conc_estoque_qtd"])
        matriz["Achei Pneus | qtd"] = qtd
    matriz = matriz.reset_index().drop(columns="item").rename(columns={"pneu": "Pneu"})
    st.dataframe(matriz, hide_index=True, use_container_width=True)

    if total == 0:
        return

    # ---------- Gráfico por meio de pagamento ----------
    st.subheader("Preço: análise por meio de pagamento")
    meios = {"PIX": "dif_pix_pct", "Total parcelado": "dif_parcelado_pct",
             "Valor da parcela": "dif_parcela_pct"}
    meio = st.radio("Meio de pagamento", list(meios.keys()), horizontal=True,
                    key=f"meio_{chave}")
    coluna = meios[meio]

    grafico = comparaveis.copy()
    grafico["rotulo"] = grafico[coluna].map(formatar_pct)
    fig = px.bar(grafico, x=coluna, y="pneu", color="concorrente", barmode="group",
                 orientation="h", text="rotulo", color_discrete_map=CORES,
                 labels={coluna: "Diferença Roma", "pneu": " ", "concorrente": "Concorrente"})
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_yaxes(categoryorder="total descending")
    fig.add_vline(x=0, line_width=1, line_color="gray")
    fig.update_xaxes(tickformat=".0%")
    fig.update_layout(height=max(350, 45 * grafico["pneu"].nunique()),
                      legend=dict(orientation="h", y=1.08), margin=dict(l=10, r=40))
    st.plotly_chart(fig, use_container_width=True, key=f"grafico_{chave}")
    st.caption("Barras à esquerda da linha cinza: Roma mais barata. À direita: Roma mais cara.")

    ranking = grafico.groupby("pneu", as_index=False)[coluna].mean().sort_values(coluna)
    a, b = st.columns(2)
    a.success(f"Mais competitivo: **{ranking.iloc[0]['pneu']}** ({formatar_pct(ranking.iloc[0][coluna])})")
    b.error(f"Menos competitivo: **{ranking.iloc[-1]['pneu']}** ({formatar_pct(ranking.iloc[-1][coluna])})")

    # ---------- Conclusão automática ----------
    st.subheader("O que os dados mostram")
    textos = [f"- No PIX, a Roma é competitiva em **{competitivos} de {total}** comparações "
              f"e cara em **{caros}**, com diferença média de **{formatar_pct(dif_pix_media)}**."]
    if dif_parcela_media > 0:
        textos.append(f"- No parcelado, o cliente paga menos na Roma em **{mais_barata_parcelado} de {total}** "
                      f"comparações, mas a parcela da Roma é **{formatar_pct(dif_parcela_media)}** em média, "
                      "porque os concorrentes parcelam em 12x. O preço é vantagem; o número de parcelas é o ponto de atenção.")
    else:
        textos.append(f"- No parcelado, o cliente paga menos na Roma em **{mais_barata_parcelado} de {total}** "
                      "comparações, e a parcela também é menor.")
    if len(oportunidades):
        textos.append(f"- **{len(oportunidades)}** situação(ões) em que só a Roma tem o pneu: "
                      "vale reforçar mídia e destaque desses itens.")
    if len(riscos):
        textos.append(f"- **{len(riscos)}** situação(ões) em que a Roma está sem estoque e o concorrente vende: "
                      "venda perdida, priorizar reposição.")
    alternativos = dados[dados["equivalencia"] != "mesmo produto"]
    if len(alternativos) and not incluir_alternativos:
        textos.append("- Comparações com produto alternativo (ex.: versão EV) ficaram fora das médias.")
    st.markdown("\n".join(textos))

    # ---------- Tabela detalhada ----------
    with st.expander("📋 Dados completos"):
        tabela = dados.copy()
        for c in ["roma_preco_pix", "conc_preco_pix", "roma_preco_parcelado", "conc_preco_parcelado",
                  "roma_valor_parcela", "conc_valor_parcela"]:
            tabela[c] = tabela[c].map(formatar_real)
        for c in ["dif_pix_pct", "dif_parcelado_pct", "dif_parcela_pct"]:
            tabela[c] = tabela[c].map(formatar_pct)
        tabela["conc_n_parcelas"] = tabela["conc_n_parcelas"].map(
            lambda v: "—" if pd.isna(v) else f"{int(v)}x")
        nomes = {
            "medida": "Medida", "modelo": "Modelo", "concorrente": "Concorrente",
            "equivalencia": "Equivalência", "situacao_estoque": "Estoque",
            "roma_preco_pix": "Roma | PIX", "conc_preco_pix": "Conc. | PIX", "dif_pix_pct": "Dif. PIX",
            "roma_preco_parcelado": "Roma | Total parcelado",
            "conc_preco_parcelado": "Conc. | Total parcelado", "dif_parcelado_pct": "Dif. parcelado",
            "roma_valor_parcela": "Roma | Parcela (6x)", "conc_n_parcelas": "Conc. | Nº parcelas",
            "conc_valor_parcela": "Conc. | Parcela", "dif_parcela_pct": "Dif. parcela",
            "classificacao_pix": "Classificação PIX",
        }
        st.dataframe(tabela[list(nomes)].rename(columns=nomes), hide_index=True,
                     use_container_width=True)


# ============================================================
# 5. ABAS
# ============================================================

aba_vendidos, aba_pesquisados, aba_historico = st.tabs(
    ["🏆 Mais vendidos", "🔎 Mais pesquisados", "📈 Histórico de preços"])

with aba_vendidos:
    st.caption("Os 10 pneus que a Roma mais vende.")
    painel(base[base["grupo"] == "Mais vendidos"], "vendidos")

with aba_pesquisados:
    st.caption("Medidas mais visualizadas no site (GA4 e busca do Magento) que não estão entre as mais vendidas: "
               "muita procura e pouca conversão.")
    painel(base[base["grupo"] == "Mais pesquisados"], "pesquisados")

with aba_historico:
    hist = carregar_historico(marca_tempo)
    if hist.empty or hist["data_coleta"].nunique() < 2:
        st.info("O histórico aparece a partir da segunda coleta. Cada vez que o coletor roda, "
                "os preços do dia são acrescentados ao arquivo `historico_precos.csv`.")
    else:
        hist = hist[hist["concorrente"].isin(concorrentes)]
        pneu = st.selectbox("Pneu", sorted(hist["pneu"].unique()))
        h = hist[hist["pneu"] == pneu]
        roma_h = (h.groupby("data_coleta", as_index=False)["roma_preco_pix"].first()
                  .rename(columns={"roma_preco_pix": "preco_pix"}).assign(loja="Roma"))
        conc_h = h[["data_coleta", "concorrente", "conc_preco_pix"]].rename(
            columns={"concorrente": "loja", "conc_preco_pix": "preco_pix"})
        serie = pd.concat([roma_h, conc_h])
        fig = px.line(serie, x="data_coleta", y="preco_pix", color="loja", markers=True,
                      color_discrete_map=CORES,
                      labels={"data_coleta": "Coleta", "preco_pix": "Preço no PIX (R$)", "loja": "Loja"})
        fig.update_layout(legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True, key="grafico_historico")
        st.caption("Pontos faltando = concorrente sem estoque naquela coleta.")
