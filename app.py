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
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
from coletor import detectar_sinais, ARQUIVO_PROMOCOES
from campanhas import ARQUIVO_CAMPANHAS, ARQUIVO_HIST_CAMPANHAS
from parcelas import ARQUIVO_PARCELAS
import ga4
import vendas as vendas_mod
from ideias import (gerar_ideias, proxima_black_friday, indice_precos, alertas_black_friday,
                    ALAVANCAS_ROMA, montar_email_ideias, IDEIAS_MERCADO)
from datetime import date

ARQUIVO_BASE = "base_concorrencia.xlsx"
ARQUIVO_HISTORICO = "historico_precos.csv"

LOJAS = ["Roma", "PneuStore", "Achei Pneus"]
# ---------- Identidade visual ----------
COR_ROMA = "#C40000"        # vermelho da logo da Roma
COR_GOODYEAR = "#004EA8"    # azul da Goodyear: cor dos gráficos de uma série só
COR_GOODYEAR_CLARO = "#A9C4E8"
COR_CINZA = "#9AA0A6"
COR_LARANJA = "#F39200"
CORES = {"Roma": COR_ROMA, "PneuStore": "#5B2D90", "Achei Pneus": COR_LARANJA}
PASTA_APP = os.path.dirname(os.path.abspath(__file__))


def achar_imagem(palavra):
    """Procura a imagem pela palavra no nome (ex.: 'roma'), na pasta imagens/ ou na pasta do app.
    Assim funciona mesmo que o download tenha mudado o nome (ex.: 'logo_roma (1).png')."""
    for pasta in (os.path.join(PASTA_APP, "imagens"), PASTA_APP):
        if os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):
                if palavra in nome.lower() and nome.lower().endswith((".png", ".jpg", ".jpeg", ".svg")):
                    return os.path.join(pasta, nome)
    return os.path.join(PASTA_APP, "imagens", f"{palavra}.png")      # não achou: o painel mostra o texto


LOGO_ROMA = achar_imagem("roma")
SELO_GOODYEAR = achar_imagem("goodyear")

# Meio de pagamento -> (coluna da Roma, coluna do concorrente, coluna da diferença)
MEIOS = {
    "PIX": ("roma_preco_pix", "conc_preco_pix", "dif_pix_pct"),
    "Total parcelado": ("roma_preco_parcelado", "conc_preco_parcelado", "dif_parcelado_pct"),
    "Valor da parcela": ("roma_valor_parcela", "conc_valor_parcela", "dif_parcela_pct"),
}

st.set_page_config(page_title="Inteligência de Preços | Roma Pneus", layout="wide",
                   page_icon=LOGO_ROMA if os.path.exists(LOGO_ROMA) else None)

# Estilo da página: cores da Roma, textos menores e números em cartões
st.markdown(f"""
<style>
/* Títulos e textos */
h2 {{ color: #1A1A1A !important; font-weight: 800 !important; font-size: 1.35rem !important; }}
h3 {{ color: #1A1A1A !important; font-weight: 800 !important; font-size: 1.12rem !important;
      border-left: 4px solid {COR_ROMA}; padding-left: .55rem !important; margin-top: .6rem; }}
.stMarkdown p, .stMarkdown li {{ color: #1A1A1A; font-size: .95rem; }}
.stMarkdown strong {{ color: #000; }}
[data-testid="stCaptionContainer"] p {{ color: #5F6368; font-size: .84rem; }}
.stRadio label p, .stCheckbox label p {{ color: #1A1A1A; font-weight: 600; font-size: .9rem; }}

/* Abas */
button[data-baseweb="tab"] p {{ font-size: .93rem; font-weight: 700; color: #1A1A1A; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {COR_ROMA}; }}

/* Números (cartões) */
[data-testid="stMetric"] {{ background: #FFFFFF; border: 1px solid #E6E8EB; border-top: 3px solid {COR_ROMA};
                           border-radius: 10px; padding: .55rem .8rem .5rem; }}
[data-testid="stMetricLabel"] p {{ color: #3C4043; font-weight: 700; font-size: .8rem;
                                  white-space: normal !important; line-height: 1.15; }}
[data-testid="stMetricLabel"] > div {{ overflow: visible !important; }}
[data-testid="stMetricValue"] {{ color: #111; font-weight: 800; font-size: 1.45rem !important; line-height: 1.25; }}
[data-testid="stMetricValue"] > div {{ overflow: visible !important; text-overflow: clip !important; }}
[data-testid="stMetricDelta"] {{ font-size: .78rem !important; }}
[data-testid="stMetricValue"] > div {{ white-space: normal !important; word-break: break-word; }}
.cartao-multi {{ background: #FFFFFF; border: 1px solid #E6E8EB; border-top: 3px solid {COR_ROMA};
                border-radius: 10px; padding: .55rem .8rem .6rem; height: 100%; }}
.cartao-rotulo {{ color: #3C4043; font-weight: 700; font-size: .8rem; margin-bottom: .25rem; }}
.cartao-valor {{ color: #111; font-weight: 700; font-size: 1.02rem; line-height: 1.45; }}
.cartao-valor b {{ font-weight: 800; }}

/* Cabeçalho com as logos */
.cabecalho {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;
             padding: .4rem 0 .9rem; margin-bottom: .6rem; border-bottom: 3px solid {COR_ROMA}; }}
.cab-esq {{ display: flex; align-items: center; gap: 1.1rem; flex-wrap: wrap; }}
.cab-esq img {{ height: 52px; }}
.cab-titulo {{ font-size: 1.55rem; font-weight: 800; color: #1A1A1A; line-height: 1.15; }}
.cab-sub {{ font-size: .88rem; color: #5F6368; margin-top: .15rem; }}
.cab-dir img {{ height: 40px; }}
[data-testid="stSidebar"] [data-testid="stImage"] img {{ max-height: 60px; object-fit: contain; }}
</style>
""", unsafe_allow_html=True)


# ============================================================
# 1. FUNÇÕES DE APOIO
# ============================================================

def imagem_base64(caminho):
    """Lê uma imagem e devolve no formato que o HTML entende (para pôr as logos no cabeçalho)."""
    if not os.path.exists(caminho):
        return None
    with open(caminho, "rb") as arquivo:
        dados = base64.b64encode(arquivo.read()).decode()
    tipo = {"jpg": "jpeg", "jpeg": "jpeg", "svg": "svg+xml"}.get(caminho.rsplit(".", 1)[-1].lower(), "png")
    return f"data:image/{tipo};base64,{dados}"


def cartao_html(coluna, rotulo, linhas):
    """Cartão com várias linhas (um valor por linha), no mesmo visual dos números do painel.
    Usado quando um st.metric não cabe: o texto quebra a linha em vez de sair da caixa."""
    corpo = "<br>".join(str(l).replace("$", "&#36;") for l in linhas) or "—"
    coluna.markdown(f'<div class="cartao-multi"><div class="cartao-rotulo">{rotulo}</div>'
                    f'<div class="cartao-valor">{corpo}</div></div>', unsafe_allow_html=True)


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
        font=dict(size=13, color="#1A1A1A"),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title_text="",
                    font=dict(size=13, color="#1A1A1A")),
        margin=dict(l=10, r=110, t=50, b=40),
        plot_bgcolor="white",
        bargap=0.25,
    )
    fig.update_yaxes(tickfont=dict(size=13, color="#1A1A1A"), title_text="")
    fig.update_xaxes(tickfont=dict(size=12, color="#1A1A1A"), gridcolor="#E5E5E5",
                     title_font=dict(size=13, color="#1A1A1A"))
    fig.update_traces(textfont=dict(size=12, color="#1A1A1A"), cliponaxis=False)
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


@st.cache_data
def carregar_campanhas(_marca):
    atuais = (pd.read_csv(ARQUIVO_CAMPANHAS, sep=";", encoding="utf-8-sig")
              if os.path.exists(ARQUIVO_CAMPANHAS) else pd.DataFrame())
    hist = (pd.read_csv(ARQUIVO_HIST_CAMPANHAS, sep=";", encoding="utf-8-sig")
            if os.path.exists(ARQUIVO_HIST_CAMPANHAS) else pd.DataFrame())
    if atuais.empty:
        atuais = pd.DataFrame(columns=["concorrente", "titulo", "tipo", "forca", "status", "link",
                                       "imagem", "novidade", "qtd_produtos", "pneus_monitorados",
                                       "fonte", "maior_pct"])
    for col in ["novidade", "imagem", "pneus_monitorados"]:
        atuais[col] = atuais[col].fillna("")
    return atuais, hist


def precos_por_loja(dados, meio):
    """Monta uma tabela longa: uma linha por pneu e loja, com o preço do meio escolhido."""
    col_roma, col_conc, _ = MEIOS[meio]

    roma = (dados.groupby(["item", "pneu"], as_index=False)
            .agg(preco=(col_roma, "first"), parcelas=("roma_n_parcelas", "first"),
                 disponivel=("roma_disponivel", "first")))
    roma["loja"] = "Roma"

    conc = dados[["item", "pneu", "concorrente", col_conc, "conc_n_parcelas", "conc_disponivel"]].rename(
        columns={"concorrente": "loja", col_conc: "preco", "conc_n_parcelas": "parcelas",
                 "conc_disponivel": "disponivel"})

    longa = pd.concat([roma, conc], ignore_index=True)
    longa["rotulo"] = longa["preco"].map(formatar_real)
    # Sem preço: "Sem estoque" só quando o site disse isso; senão a coleta falhou
    sem_preco = longa["preco"].isna()
    longa.loc[sem_preco, "rotulo"] = longa.loc[sem_preco, "disponivel"].map(
        lambda d: {"nao": "Sem estoque", "alternativo": "Produto diferente"}.get(d, "Não coletado"))
    if meio == "Valor da parcela":
        longa["rotulo"] = longa.apply(
            lambda l: l["rotulo"] if pd.isna(l["parcelas"]) or pd.isna(l["preco"])
            else f"{l['rotulo']} ({int(l['parcelas'])}x)",
            axis=1)
    return longa


# ============================================================
# 2. CABEÇALHO E BOTÃO DE ATUALIZAR
# ============================================================

_logo, _selo = imagem_base64(LOGO_ROMA), imagem_base64(SELO_GOODYEAR)
st.markdown(f"""
<div class="cabecalho">
  <div class="cab-esq">
    {f'<img src="{_logo}" alt="Roma Pneus">' if _logo else '<b style="color:#C40000;font-size:2rem">ROMA PNEUS</b>'}
    <div>
      <div class="cab-titulo">Inteligência de Preços e Vendas</div>
      <div class="cab-sub">Roma x Pneu Store x Achei Pneus · site (GA4) · Google Ads · vendas faturadas</div>
    </div>
  </div>
  <div class="cab-dir">{f'<img src="{_selo}" alt="Goodyear">' if _selo else ''}</div>
</div>
""", unsafe_allow_html=True)

if os.path.exists(LOGO_ROMA):
    st.sidebar.image(LOGO_ROMA, width="stretch")
st.sidebar.header("Coleta")
if st.sidebar.button("🔄 Atualizar tudo", width="stretch",
                     help="Atualiza preços, parcelas, promoções, campanhas, GA4, Google Ads e vendas. Leva cerca de 2 minutos."):
    import coletor
    with st.spinner("Atualizando preços, promoções e campanhas da Roma, Pneu Store e Achei Pneus..."):
        _, sinais_novos, mudancas_camp = coletor.coletar()
    st.cache_data.clear()
    st.sidebar.success("Preços atualizados!")
    if sinais_novos.empty:
        st.toast("Nenhuma promoção ou mudança de preço nos concorrentes.", icon="✅")
    else:
        st.toast(f"{len(sinais_novos)} promoção(ões) ou mudança(s) de preço detectada(s). "
                 "Veja a aba 📣 Promoções.", icon="📣")
        st.sidebar.warning(f"📣 **{len(sinais_novos)} sinal(is) de promoção** nesta coleta.")
    if not mudancas_camp.empty:
        st.sidebar.warning(f"📢 **{len(mudancas_camp)} mudança(s) de campanha** (nova ou encerrada).")

if not os.path.exists(ARQUIVO_BASE):
    st.info("Ainda não há dados coletados. Clique em **🔄 Atualizar tudo** na barra lateral "
            "ou rode o `coletor.py` no VS Code.")
    st.stop()

marca_tempo = os.path.getmtime(ARQUIVO_BASE)
base = carregar_base(marca_tempo)
st.sidebar.markdown(f"Última coleta: **{base['data_coleta'].iloc[0]}**")
falhas = base[base["conc_disponivel"].isna()]
if not falhas.empty:
    st.sidebar.error(f"⚠️ {len(falhas)} preço(s) não coletado(s) na última coleta: "
                     + "; ".join(f"{l['concorrente']} · {l['medida']} {l['modelo']}" for _, l in falhas.iterrows())
                     + ". Rode a coleta de novo.")

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
    "Incluir produto alternativo",
    value=False,
    help="Quando o concorrente não vende o mesmo pneu da Roma, comparamos com o modelo equivalente "
         "(ex.: Cargo Marathon 3 no lugar do Cargo Marathon 2 na Achei Pneus). "
         "Como são produtos diferentes, fica fora das médias por padrão.",
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
    base.loc[alternativo, "conc_disponivel"] = "alternativo"

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
        st.plotly_chart(estilo_grafico(fig, altura), width="stretch",
                        key=f"preco_{chave}")
        st.caption("Barra faltando = sem preço nesta coleta. A tabela abaixo mostra o motivo: "
                   "**Sem estoque** (o site avisou) ou **Não coletado** (o site não respondeu; rode a coleta de novo).")
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
        st.plotly_chart(estilo_grafico(fig, altura), width="stretch",
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
    rotulos = rotulos.fillna("Não coletado")

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
                 width="stretch")

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
                     width="stretch")


# ============================================================
# 5. PROMOÇÕES: sinais detectados automaticamente nos dados
# ============================================================

LINK_APP = "https://mais-vendidos-e-mais-pesquisados.streamlit.app/"


def montar_email(atual, sinais, nome, data, campanhas=None):
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

    if campanhas is not None and not campanhas.empty:
        ativas = campanhas[campanhas["status"] == "ativa"].sort_values("forca", ascending=False)
        ativas = ativas[ativas["tipo"] != "Institucional / marca"]
        if not ativas.empty:
            linhas += ["", "CAMPANHAS ATIVAS DOS CONCORRENTES (mais fortes)"]
            for _, c in ativas.head(6).iterrows():
                selo = " [NOVA]" if c.get("novidade") == "NOVA" else ""
                linhas.append(f"- {c['concorrente']} | {c['tipo']}: {c['titulo']}{selo}")

    bf = proxima_black_friday()
    linhas += ["", f"Faltam {(bf - date.today()).days} dias para a Black Friday ({bf.strftime('%d/%m/%Y')})."]
    linhas += ["", f"Painel completo: {LINK_APP}", "", "Atenciosamente,", "Lucas"]
    assunto = f"Monitor de preços da concorrência | {data}"
    return assunto, "\n".join(linhas)


# ============================================================
# 6. ABAS
# ============================================================

(aba_vendidos, aba_pesquisados, aba_parcelas, aba_site, aba_vendas, aba_historico, aba_promocoes,
 aba_campanhas, aba_bf, aba_ideias) = st.tabs(
    ["🏆 Mais vendidos", "🔎 Mais pesquisados", "💳 Simulador de parcelas", "📊 Site (GA4)",
     "💰 Vendas", "📈 Histórico de preços", "📣 Promoções", "📢 Radar de campanhas", "🖤 Black Friday", "💡 Ideias"])

# Tabela de parcelas (1x a 12x) da última coleta
marca_parcelas = os.path.getmtime(ARQUIVO_PARCELAS) if os.path.exists(ARQUIVO_PARCELAS) else 0


@st.cache_data
def carregar_parcelas(_marca):
    if not os.path.exists(ARQUIVO_PARCELAS):
        return pd.DataFrame()
    tab = pd.read_csv(ARQUIVO_PARCELAS, sep=";", encoding="utf-8-sig")
    tab["pneu"] = tab["medida"] + " " + tab["modelo"]
    return tab


parcelas_todas = carregar_parcelas(marca_parcelas)
if not parcelas_todas.empty:
    parcelas_todas = parcelas_todas[parcelas_todas["loja"].isin(["Roma"] + concorrentes)]
    if not incluir_alternativos:
        alternativos = base.loc[base["conc_disponivel"] == "alternativo", ["item", "concorrente"]]
        pares = set(zip(alternativos["item"], alternativos["concorrente"]))
        parcelas_todas = parcelas_todas[[(i, l) not in pares for i, l in
                                         zip(parcelas_todas["item"], parcelas_todas["loja"])]]

marca_campanhas = os.path.getmtime(ARQUIVO_CAMPANHAS) if os.path.exists(ARQUIVO_CAMPANHAS) else 0
campanhas_atuais, hist_campanhas = carregar_campanhas(marca_campanhas)
campanhas_atuais = campanhas_atuais[campanhas_atuais["concorrente"].isin(concorrentes)]

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
        st.plotly_chart(estilo_grafico(fig, 480), width="stretch", key="grafico_historico")
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
            st.dataframe(tabela_s, hide_index=True, width="stretch")

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
                     hide_index=True, width="stretch")
    else:
        st.info("Ainda não há promoções registradas. A cada coleta, o coletor grava aqui "
                "o que encontrar (arquivo `historico_promocoes.csv`).")

    # ---------- E-mail para o coordenador ----------
    st.subheader("✉️ E-mail para o coordenador")
    m1, m2 = st.columns(2)
    nome = m1.text_input("Nome do coordenador", placeholder="Ex.: Carlos")
    para = m2.text_input("E-mail do coordenador", placeholder="nome@romapneus.com.br")

    data_txt = pd.to_datetime(base["data_coleta"].iloc[0]).strftime("%d/%m/%Y")
    assunto, corpo = montar_email(base, sinais, nome.strip(), data_txt, campanhas_atuais)
    assunto = st.text_input("Assunto", value=assunto)
    corpo = st.text_area("Texto do e-mail (pode editar antes de enviar)", value=corpo, height=420)

    from urllib.parse import quote
    link = f"mailto:{para.strip()}?subject={quote(assunto)}&body={quote(corpo)}"
    b1, b2 = st.columns(2)
    b1.link_button("📧 Abrir no meu e-mail", link, width="stretch",
                   help="Abre o Outlook/Gmail do seu computador com o e-mail pronto.")
    b2.download_button("⬇️ Baixar como .txt", data=f"Assunto: {assunto}\n\n{corpo}",
                       file_name=f"monitor_precos_{data_txt.replace('/', '-')}.txt",
                       width="stretch")
    st.caption("Se o botão de e-mail não abrir nada, copie o texto acima e cole no seu e-mail.")


# ============================================================
# 7. RADAR DE CAMPANHAS
# ============================================================

def encerradas_ultima_coleta(hist):
    """Campanhas ativas na penúltima coleta que não estão ativas na última."""
    if hist.empty or hist["data_coleta"].nunique() < 2:
        return pd.DataFrame()
    datas = sorted(hist["data_coleta"].unique())
    chave = lambda d: d["concorrente"] + "|" + d["titulo"].str.lower() + "|" + d["link"].astype(str)
    antes = hist[(hist["data_coleta"] == datas[-2]) & (hist["status"] == "ativa")]
    agora = hist[(hist["data_coleta"] == datas[-1]) & (hist["status"] == "ativa")]
    return antes[~chave(antes).isin(set(chave(agora)))]


def cartao_campanha(c, mostrar_imagem=True):
    with st.container(border=True):
        if mostrar_imagem and isinstance(c["imagem"], str) and c["imagem"].startswith("http"):
            st.image(c["imagem"], width="stretch")
        selo = " 🆕 **NOVA**" if c["novidade"] == "NOVA" else ""
        st.markdown(f"**{c['titulo']}**{selo}")
        detalhe = f"{c['concorrente']} · {c['tipo']}"
        if pd.notna(c.get("maior_pct")) and str(c.get("maior_pct")) not in ("", "nan"):
            detalhe += f" · até {int(float(c['maior_pct']))}%"
        st.caption(detalhe)
        if isinstance(c["link"], str) and c["link"].startswith("http"):
            st.markdown(f"[Abrir página da campanha]({c['link']})")


with aba_campanhas:
    st.markdown("**Banners e campanhas que os concorrentes estão divulgando, atualizados a cada coleta.**")
    st.caption("Pneu Store: banners da página inicial. Achei Pneus: categorias de campanha do site "
               "(ativa = com produtos; pausada = criada, mas vazia no momento).")

    if campanhas_atuais.empty:
        st.info("Ainda não há campanhas coletadas. Elas aparecem na próxima vez que o coletor rodar.")
    else:
        ativas = campanhas_atuais[campanhas_atuais["status"] == "ativa"]
        encerradas = encerradas_ultima_coleta(hist_campanhas)
        if not encerradas.empty:
            encerradas = encerradas[encerradas["concorrente"].isin(concorrentes)]

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Campanhas ativas", len(ativas))
        r2.metric("Novas nesta coleta", (campanhas_atuais["novidade"] == "NOVA").sum())
        r3.metric("Encerradas nesta coleta", len(encerradas))
        r4.metric("Black Friday detectada", "Sim" if (ativas["tipo"] == "Black Friday").any() else "Não")

        # ---------- As mais fortes ----------
        st.subheader("🔥 As campanhas mais fortes agora")
        fortes = ativas[ativas["tipo"] != "Institucional / marca"].sort_values("forca", ascending=False).head(6)
        if fortes.empty:
            st.markdown("Nenhuma campanha promocional ativa nesta coleta.")
        else:
            colunas = st.columns(3)
            for i, (_, c) in enumerate(fortes.iterrows()):
                with colunas[i % 3]:
                    cartao_campanha(c)

        # ---------- Por tipo ----------
        st.subheader("📊 O que cada concorrente está usando")
        por_tipo = (ativas.groupby(["tipo", "concorrente"]).size().reset_index(name="campanhas"))
        if not por_tipo.empty:
            fig = px.bar(por_tipo, x="campanhas", y="tipo", color="concorrente", orientation="h",
                         barmode="group", text="campanhas", color_discrete_map=CORES,
                         labels={"campanhas": "Nº de campanhas", "tipo": " ", "concorrente": "Concorrente"})
            fig.update_traces(texttemplate="<b>%{text}</b>", textposition="outside")
            st.plotly_chart(estilo_grafico(fig, max(320, 55 * por_tipo["tipo"].nunique())),
                            width="stretch", key="grafico_tipos_campanha")

        # ---------- Mudanças ----------
        if (campanhas_atuais["novidade"] == "NOVA").any() or not encerradas.empty:
            st.subheader("🔄 Mudanças desde a última coleta")
            for _, c in campanhas_atuais[campanhas_atuais["novidade"] == "NOVA"].iterrows():
                st.markdown(f"- 🆕 **Nova** · {c['concorrente']}: {c['titulo']} ({c['tipo']})")
            for _, c in encerradas.iterrows():
                st.markdown(f"- 🛑 **Encerrada** · {c['concorrente']}: {c['titulo']} ({c['tipo']})")

        # ---------- Lista completa por concorrente ----------
        for loja in [l for l in ["PneuStore", "Achei Pneus"] if l in campanhas_atuais["concorrente"].values]:
            dados_loja = campanhas_atuais[campanhas_atuais["concorrente"] == loja]
            with st.expander(f"📋 Todas as campanhas · {loja} ({len(dados_loja)})"):
                tabela_c = dados_loja.copy()
                tabela_c["status"] = tabela_c["status"].map({"ativa": "🟢 Ativa", "pausada": "⚪ Pausada"})
                colunas_c = {"titulo": "Campanha", "tipo": "Tipo", "status": "Status", "link": "Link"}
                if loja == "Achei Pneus":
                    colunas_c.update({"qtd_produtos": "Produtos", "pneus_monitorados": "Nossos pneus na campanha"})
                st.dataframe(tabela_c[list(colunas_c)].rename(columns=colunas_c), hide_index=True,
                             width="stretch",
                             column_config={"Link": st.column_config.LinkColumn("Link")})

        # ---------- Duração das campanhas ----------
        if not hist_campanhas.empty and hist_campanhas["data_coleta"].nunique() >= 2:
            with st.expander("🗂️ Histórico: quando cada campanha começou e terminou"):
                h = hist_campanhas[(hist_campanhas["status"] == "ativa") &
                                   hist_campanhas["concorrente"].isin(concorrentes)].copy()
                h["data_coleta"] = pd.to_datetime(h["data_coleta"])
                ultima = h["data_coleta"].max()
                duracao = (h.groupby(["concorrente", "titulo", "tipo"])["data_coleta"]
                           .agg(["min", "max", "nunique"]).reset_index())
                duracao["situacao"] = duracao["max"].map(lambda d: "🟢 No ar" if d == ultima else "🛑 Encerrada")
                duracao = duracao.sort_values("min", ascending=False)
                duracao["min"] = duracao["min"].dt.strftime("%d/%m/%Y")
                duracao["max"] = duracao["max"].dt.strftime("%d/%m/%Y")
                st.dataframe(duracao.rename(columns={
                    "concorrente": "Concorrente", "titulo": "Campanha", "tipo": "Tipo",
                    "min": "Vista pela 1ª vez", "max": "Vista pela última vez",
                    "nunique": "Nº de coletas", "situacao": "Situação"}),
                    hide_index=True, width="stretch")


# ============================================================
# 8. BLACK FRIDAY
# ============================================================

with aba_bf:
    bf = proxima_black_friday()
    dias_bf = (bf - date.today()).days
    st.markdown(f"**Como os concorrentes estão se movimentando até a Black Friday "
                f"({bf.strftime('%d/%m/%Y')}).**")

    hist_bf = carregar_historico(marca_tempo)
    if not hist_bf.empty:
        hist_bf = hist_bf[hist_bf["concorrente"].isin(concorrentes)]

    campanhas_bf = campanhas_atuais[(campanhas_atuais["tipo"] == "Black Friday") &
                                    (campanhas_atuais["status"] == "ativa")]
    maquiados = alertas_black_friday(hist_bf)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Dias para a Black Friday", max(dias_bf, 0))
    k2.metric("Campanhas de Black Friday no ar", len(campanhas_bf))
    k3.metric("Possíveis preços maquiados", len(maquiados),
              help="PIX atual 3% ou mais acima do menor preço dos últimos 30 dias.")
    if not hist_bf.empty:
        desc = hist_bf[hist_bf["data_coleta"] == hist_bf["data_coleta"].max()]["conc_desconto_pix_pct"].mean()
        k4.metric("Desconto médio no PIX (concorrentes)", "—" if pd.isna(desc) else f"{desc:.1%}".replace(".", ","))

    # ---------- Campanhas de Black Friday ----------
    st.subheader("🖤 Campanhas de Black Friday dos concorrentes")
    if campanhas_bf.empty:
        st.markdown("Nenhum concorrente com campanha de Black Friday no ar ainda. "
                    "Quando aparecer um banner ou categoria com *Black*, *Esquenta* ou *Cyber*, ele surge aqui.")
    else:
        colunas = st.columns(3)
        for i, (_, c) in enumerate(campanhas_bf.iterrows()):
            with colunas[i % 3]:
                cartao_campanha(c)
        if not hist_campanhas.empty:
            primeiras = (hist_campanhas[(hist_campanhas["tipo"] == "Black Friday") &
                                        (hist_campanhas["status"] == "ativa")]
                         .groupby("concorrente")["data_coleta"].min())
            for loja, quando in primeiras.items():
                inicio = pd.to_datetime(quando)
                st.markdown(f"- **{loja}** começou a falar de Black Friday em **{inicio.strftime('%d/%m/%Y')}** "
                            f"({(pd.Timestamp(bf) - inicio).days} dias antes).")

    # ---------- Índice de preços ----------
    st.subheader("📉 Movimento de preços até a Black Friday")
    indice = indice_precos(hist_bf if not hist_bf.empty else pd.DataFrame())
    if indice.empty or indice["data_coleta"].nunique() < 2:
        st.info("O movimento de preços aparece a partir da segunda coleta. Coletando todos os dias até a "
                "Black Friday, este gráfico mostra quem está subindo preço antes do evento e quem já está baixando.")
    else:
        fig = px.line(indice, x="data_coleta", y="indice", color="loja", markers=True,
                      color_discrete_map=CORES, category_orders={"loja": LOJAS},
                      labels={"data_coleta": "Coleta", "indice": "Índice de preço (1ª coleta = 100)", "loja": "Loja"})
        fig.add_hline(y=100, line_dash="dot", line_color="#555")
        fig.update_traces(line=dict(width=3), marker=dict(size=9))
        st.plotly_chart(estilo_grafico(fig, 420), width="stretch", key="grafico_indice_bf")
        st.caption("Acima de 100: a loja está mais cara do que no início do monitoramento. "
                   "Abaixo de 100: está mais barata. Calculado com o PIX médio dos pneus monitorados.")

        descontos = (hist_bf.groupby(["data_coleta", "concorrente"])["conc_desconto_pix_pct"].mean()
                     .reset_index())
        fig = px.line(descontos, x="data_coleta", y="conc_desconto_pix_pct", color="concorrente",
                      markers=True, color_discrete_map=CORES,
                      labels={"data_coleta": "Coleta", "conc_desconto_pix_pct": "Desconto médio no PIX",
                              "concorrente": "Concorrente"})
        fig.update_yaxes(tickformat=".0%")
        fig.update_traces(line=dict(width=3), marker=dict(size=9))
        st.plotly_chart(estilo_grafico(fig, 380), width="stretch", key="grafico_desconto_bf")

    # ---------- Preço maquiado ----------
    st.subheader("⚠️ Alerta de preço maquiado")
    st.caption("Tática comum antes da Black Friday: subir o preço para depois anunciar um desconto maior.")
    if maquiados.empty:
        st.markdown("Nenhum pneu com o PIX 3% ou mais acima do menor preço dos últimos 30 dias.")
    else:
        tabela_m = maquiados.copy()
        tabela_m["menor_30d"] = tabela_m["menor_30d"].map(formatar_real)
        tabela_m["atual"] = tabela_m["atual"].map(formatar_real)
        tabela_m["variacao"] = tabela_m["variacao"].map(formatar_pct)
        st.dataframe(tabela_m.rename(columns={"concorrente": "Concorrente", "pneu": "Pneu",
                                              "menor_30d": "Menor PIX em 30 dias", "atual": "PIX atual",
                                              "variacao": "Alta"}),
                     hide_index=True, width="stretch")

    # ---------- Plano da Roma ----------
    st.subheader("🗓️ Plano da Roma até a Black Friday")
    fases = [
        (45, "Planejamento", "Definir os pneus da campanha (usar os mais vendidos e os mais pesquisados deste painel), "
                             "negociar estoque com o fornecedor e travar a margem mínima."),
        (30, "Lista de espera", "Abrir cadastro de interesse por e-mail e WhatsApp e aquecer a base na Brevo."),
        (15, "Esquenta", "Primeiras ofertas para a base cadastrada e banner com contagem regressiva no site."),
        (7, "Semana Black", "Ofertas diárias, reforço de mídia e monitoramento de preço dos concorrentes duas vezes por dia."),
        (0, "Black Friday e Cyber Monday", "Ofertas principais, acompanhamento de estoque em tempo real e ajuste rápido de preço."),
    ]
    for dias_antes, fase, acao in fases:
        quando = bf - pd.Timedelta(days=dias_antes)
        status = "✅" if date.today() > quando + pd.Timedelta(days=3 if dias_antes == 0 else 0) else (
            "👉" if dias_bf <= dias_antes + 15 else "⏳")
        st.markdown(f"{status} **{fase}** · a partir de {quando.strftime('%d/%m')}: {acao}")


# ============================================================
# 9. IDEIAS DE ESTRATÉGIA
# ============================================================

with aba_ideias:
    st.markdown("**Sugestões de ação para a Roma, geradas a partir dos preços, do estoque e das campanhas "
                "dos concorrentes desta coleta.**")
    st.caption("Geradas automaticamente a cada coleta. Mais abaixo, a biblioteca com ações que o mercado "
               "usa, já no formato de piloto para levar à aprovação.")

    ideias = gerar_ideias(base, campanhas_atuais, parcelas_todas)
    if ideias.empty:
        st.success("Nenhuma ação urgente: a Roma está competitiva e não há campanhas relevantes dos concorrentes.")
    else:
        i1, i2, i3 = st.columns(3)
        i1.metric("Prioridade alta", (ideias["prioridade"] == "Alta").sum())
        i2.metric("Prioridade média", (ideias["prioridade"] == "Média").sum())
        i3.metric("Prioridade baixa", (ideias["prioridade"] == "Baixa").sum())

        icones = {"Alta": "🔴", "Média": "🟠", "Baixa": "🟢"}
        for _, ideia in ideias.iterrows():
            with st.container(border=True):
                st.markdown(f"### {icones[ideia['prioridade']]} {ideia['ideia']}")
                st.markdown(f"**Prioridade:** {ideia['prioridade']} · **Alavanca:** {ideia['alavanca']}")
                st.markdown(f"**Por quê:** {ideia['motivo']}")
                st.markdown(f"**O que fazer:** {ideia['acao']}")

    # ---------- Biblioteca de ideias do mercado ----------
    st.subheader("📚 Biblioteca de ideias do mercado")
    st.markdown("**O que o mercado de pneus costuma fazer, já no formato de piloto:** pequeno, com prazo, "
                "custo limitado e forma de medir. Proposta pequena e mensurável é mais fácil de aprovar.")
    escolhidas = []
    for i, b in enumerate(IDEIAS_MERCADO):
        with st.expander(f"💡 {b['titulo']}"):
            st.markdown(f"**Como funciona:** {b['como_funciona']}")
            st.markdown(f"**No mercado:** {b['no_mercado']}")
            st.markdown(f"**Proposta de piloto:** {b['piloto']}")
            st.markdown(f"**Custo:** {b['custo']}")
            st.markdown(f"**Como medir:** {b['medir']}")
            if st.checkbox("Incluir no e-mail", key=f"biblio_{i}"):
                escolhidas.append(b)

    # ---------- E-mail das ideias ----------
    st.subheader("✉️ Enviar o resumo das ideias por e-mail")
    e1, e2 = st.columns(2)
    nome_i = e1.text_input("Nome do coordenador", placeholder="Ex.: Carlos", key="nome_ideias")
    para_i = e2.text_input("E-mail do coordenador", placeholder="nome@romapneus.com.br", key="email_ideias")
    data_i = pd.to_datetime(base["data_coleta"].iloc[0]).strftime("%d/%m/%Y")
    assunto_i, corpo_i = montar_email_ideias(ideias, nome_i.strip(), data_i, LINK_APP, escolhidas)
    assunto_i = st.text_input("Assunto", value=assunto_i, key="assunto_ideias")
    corpo_i = st.text_area("Texto do e-mail (pode editar antes de enviar)", value=corpo_i, height=420,
                           key="corpo_ideias")
    from urllib.parse import quote as _quote
    b1, b2 = st.columns(2)
    b1.link_button("📧 Abrir no meu e-mail",
                   f"mailto:{para_i.strip()}?subject={_quote(assunto_i)}&body={_quote(corpo_i)}",
                   width="stretch")
    b2.download_button("⬇️ Baixar como .txt", data=f"Assunto: {assunto_i}\n\n{corpo_i}",
                       file_name=f"ideias_{data_i.replace('/', '-')}.txt", width="stretch",
                       key="baixar_ideias")
    st.caption("Se o e-mail abrir cortado (textos longos), use o botão de baixar ou copie o texto acima.")


# ============================================================
# 10. SIMULADOR DE PARCELAS
# ============================================================

with aba_parcelas:
    st.markdown("**Quanto o cliente paga em cada loja, de 1x a 12x no cartão.**")
    st.caption("Roma: 6% de desconto em qualquer forma de pagamento, até 6x sem juros. "
               "Pneu Store e Achei Pneus: desconto progressivo (8% em 1x, caindo até o limite sem juros). "
               "Pneu Store cobra juros acima de 10x.")

    if parcelas_todas.empty:
        st.info("A tabela de parcelas aparece depois da próxima coleta (botão 🔄 Atualizar tudo).")
    else:
        s1, s2, s3 = st.columns([1.2, 2, 1])
        grupo_p = s1.selectbox("Grupo", ["Todos", "Mais vendidos", "Mais pesquisados"], key="grupo_parcelas")
        n_parc = s2.select_slider("Número de parcelas", options=list(range(1, 13)), value=10,
                                  key="n_parcelas")
        qtd = s3.radio("Quantidade de pneus", [1, 2, 4], horizontal=True, key="qtd_pneus",
                       help="O padrão do mercado: 2 pneus, depois mais 2, ou o jogo de 4 de uma vez.")

        tab_p = parcelas_todas if grupo_p == "Todos" else parcelas_todas[parcelas_todas["grupo"] == grupo_p]
        tab_p = tab_p.assign(total=tab_p["total"] * qtd, valor_parcela=tab_p["valor_parcela"] * qtd)
        lojas_p = [l for l in LOJAS if l in tab_p["loja"].unique()]
        ordem_p = tab_p.sort_values("item")["pneu"].unique().tolist()

        # ---------- Comparativo no número de parcelas escolhido ----------
        escolha = tab_p[tab_p["parcelas"] == n_parc]
        totais = escolha.pivot_table(index="pneu", columns="loja", values="total", aggfunc="first")
        totais = totais.reindex(index=ordem_p, columns=lojas_p)
        parcelas_v = escolha.pivot_table(index="pneu", columns="loja", values="valor_parcela", aggfunc="first")
        parcelas_v = parcelas_v.reindex(index=ordem_p, columns=lojas_p)
        juros = escolha.pivot_table(index="pneu", columns="loja", values="juros", aggfunc="first")
        juros = juros.reindex(index=ordem_p, columns=lojas_p)

        concs_p = [l for l in lojas_p if l != "Roma"]
        menor_conc = totais[concs_p].min(axis=1) if concs_p else pd.Series(dtype=float)
        roma_oferece = n_parc <= 6

        m1, m2, m3 = st.columns(3)
        if roma_oferece and "Roma" in totais:
            comparaveis_p = totais["Roma"].notna() & menor_conc.notna()
            roma_ganha = (totais.loc[comparaveis_p, "Roma"] <= menor_conc[comparaveis_p]).sum()
            dif_media = (totais.loc[comparaveis_p, "Roma"] / menor_conc[comparaveis_p] - 1).mean()
            m1.metric(f"Roma mais barata em {n_parc}x", f"{roma_ganha} de {comparaveis_p.sum()}")
            m2.metric("Total Roma x menor concorrente", formatar_pct(dif_media),
                      help="Negativo = o cliente paga menos na Roma no total.")
        else:
            m1.metric(f"Roma em {n_parc}x", "Não oferece", help="A Roma parcela em até 6x.")
            cartao_html(m2, "Lojas que oferecem", [l for l in concs_p if totais[l].notna().any()])
        parcela_media = parcelas_v.mean()
        cartao_html(m3, f"Parcela média ({qtd} pneu{'s' if qtd > 1 else ''})",
                    [f"<b>{l}:</b> {formatar_real(parcela_media[l])}" for l in lojas_p
                     if pd.notna(parcela_media.get(l))])

        st.subheader(f"Comparativo em {n_parc}x · {qtd} pneu{'s' if qtd > 1 else ''}")
        tabela_p = pd.DataFrame({"Pneu": ordem_p})
        for loja in lojas_p:
            textos = []
            for pneu in ordem_p:
                total, parcela = totais.at[pneu, loja], parcelas_v.at[pneu, loja]
                if pd.isna(total):
                    textos.append("Não oferece" if loja == "Roma" and not roma_oferece else "—")
                else:
                    extra = " · com juros" if juros.at[pneu, loja] == True else ""
                    textos.append(f"{formatar_real(total)} ({n_parc}x de {formatar_real(parcela)}){extra}")
            tabela_p[loja] = textos
        numeros_p = totais.reset_index(drop=True)

        def destacar_parcelas(_):
            css = pd.DataFrame("color: #111;", index=tabela_p.index, columns=tabela_p.columns)
            css["Pneu"] = "color: #000; font-weight: 700;"
            menor = numeros_p.min(axis=1)
            for loja in lojas_p:
                iguais = numeros_p[loja].notna() & (numeros_p[loja] == menor)
                css.loc[iguais, loja] = "background-color: #DFF3E4; color: #0B5D23; font-weight: 800;"
                css.loc[tabela_p[loja].str.contains("juros|Não oferece"), loja] = "color: #B00020; font-weight: 700;"
            return css

        st.dataframe(tabela_p.style.apply(destacar_parcelas, axis=None), hide_index=True,
                     width="stretch")
        st.caption("Em verde, o menor total de cada pneu. Em vermelho, parcelamento com juros ou não oferecido.")

        # ---------- Curva de 1x a 12x de um pneu ----------
        st.subheader("📈 Total a pagar de 1x a 12x")
        pneu_p = st.selectbox("Pneu", ordem_p, key="pneu_curva")
        curva = tab_p[tab_p["pneu"] == pneu_p].copy()
        fig = px.line(curva, x="parcelas", y="total", color="loja", markers=True,
                      color_discrete_map=CORES, category_orders={"loja": LOJAS},
                      labels={"parcelas": "Número de parcelas", "total": "Total a pagar (R$)", "loja": "Loja"})
        fig.update_traces(line=dict(width=3), marker=dict(size=9))
        fig.add_vline(x=n_parc, line_dash="dot", line_color="#555")
        fig.update_xaxes(dtick=1)
        fig.update_yaxes(tickprefix="R$ ", separatethousands=True)
        st.plotly_chart(estilo_grafico(fig, 430), width="stretch", key="grafico_curva_parcelas")
        st.caption("A linha da Roma termina em 6x porque a Roma parcela em até 6x. "
                   "A linha pontilhada marca o número de parcelas escolhido acima.")

        grade = curva.pivot_table(index="parcelas", columns="loja", values="valor_parcela", aggfunc="first")
        grade = grade.reindex(index=range(1, 13), columns=lojas_p)
        grade_txt = grade.apply(lambda col: col.map(formatar_real))
        if "Roma" in grade_txt:
            grade_txt.loc[grade_txt.index > 6, "Roma"] = "Não oferece"
        grade_txt.index = [f"{n}x" for n in grade_txt.index]
        with st.expander(f"📋 Valor da parcela de 1x a 12x · {pneu_p}"):
            st.dataframe(grade_txt, width="stretch")

        fontes_p = curva[curva["loja"] != "Roma"].drop_duplicates("loja")[["loja", "fonte"]]
        if not fontes_p.empty:
            st.caption("Origem dos dados: " + " · ".join(
                f"{l['loja']}: {'tabela do site' if l['fonte'] == 'site' else 'fórmula do desconto progressivo'}"
                for _, l in fontes_p.iterrows()))


# ============================================================
# 11. SITE (GA4)
# ============================================================

def credencial_ga4():
    """No Streamlit Cloud a chave fica em Settings > Secrets. No computador, usa o arquivo em C:\\chaves."""
    try:
        if "gcp_service_account" in st.secrets:
            return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def ga4_ao_vivo(_momento):
    """Consulta o GA4 na hora. Fica guardado até 1 hora (ou até clicar em Atualizar)."""
    dados = ga4.buscar_tudo(credencial_ga4())
    dados["consultado_em"] = pd.Timestamp.now(tz="America/Sao_Paulo")
    return dados


@st.cache_data(show_spinner=False)
def ga4_arquivos(_marca):
    return ga4.ler_arquivos()


# Há acesso direto ao GA4? Na nuvem: chave no Secrets. No computador: arquivo em C:\chaves
TEM_ACESSO_GA4 = credencial_ga4() is not None or os.path.exists(ga4.CHAVE)


def carregar_ga4():
    """Devolve (dados, texto da origem, aviso).
    Com acesso ao GA4: consulta AO VIVO e renova sozinho a cada hora, sem precisar rodar o coletor.
    Sem acesso: usa os arquivos ga4_*.csv da última coleta."""
    aviso = None
    if TEM_ACESSO_GA4:
        momento = st.session_state.get("ga4_vivo") or pd.Timestamp.now().floor("1h")
        try:
            with st.spinner("Consultando o GA4..."):
                dados = ga4_ao_vivo(momento)
            return dados, f"Ao vivo pelo GA4 · consultado às {dados['consultado_em']:%H:%M} (renova a cada hora)", None
        except Exception as erro:
            aviso = f"Não foi possível consultar o GA4 agora ({str(erro)[:150]}). Mostrando os dados da última coleta."
    marca = os.path.getmtime(ga4.ARQ_DIARIO) if os.path.exists(ga4.ARQ_DIARIO) else 0
    dados = ga4_arquivos(marca)
    origem = ""
    if dados is not None:
        origem = ("Dados da última coleta · " + pd.Timestamp(marca, unit="s", tz="UTC")
                  .tz_convert("America/Sao_Paulo").strftime("%d/%m/%Y %H:%M"))
    return dados, origem, aviso


def variacao(atual, anterior):
    if pd.isna(anterior) or anterior == 0:
        return None
    return f"{(atual / anterior - 1):+.1%}".replace(".", ",")


def numero(valor):
    return f"{valor:,.0f}".replace(",", ".")


def porcento(valor, casas=1):
    return "—" if valor is None or pd.isna(valor) else f"{valor:.{casas}%}".replace(".", ",")


# ---------- Vendas faturadas (seu controle) ----------
@st.cache_data(show_spinner=False)
def carregar_vendas(_marca):
    return vendas_mod.ler_vendas()


marca_vendas = os.path.getmtime(vendas_mod.ARQ_VENDAS) if os.path.exists(vendas_mod.ARQ_VENDAS) else 0
vendas_df = carregar_vendas(marca_vendas)

# "Hoje" no horário de Brasília (o Streamlit Cloud roda em outro fuso)
HOJE = pd.Timestamp.now(tz="America/Sao_Paulo").normalize().tz_localize(None)
ONTEM = HOJE - pd.Timedelta(days=1)


SEMANA = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def nome_dia(d):
    return f"{d:%d/%m} ({SEMANA[d.weekday()]})"


def escolher_dia(chave, minimo, padrao=None):
    """Seletor de um dia + com o que comparar. Devolve (dia escolhido, dia de comparação)."""
    c_d, c_c = st.columns([1, 2])
    padrao = padrao if padrao is not None else ONTEM
    escolhido = c_d.date_input("Dia", value=padrao.date(), min_value=minimo.date(), max_value=HOJE.date(),
                               format="DD/MM/YYYY", key=f"{chave}_dia")
    escolhido = pd.Timestamp(escolhido)
    comparar = c_c.radio("Comparar com", ["Mesmo dia da semana passada", "Dia anterior"], horizontal=True,
                         key=f"{chave}_comparar")
    return escolhido, escolhido - pd.Timedelta(days=7 if comparar.startswith("Mesmo") else 1)


def janela(dias):
    """Últimos N dias até ontem e os N dias anteriores (as mesmas janelas do GA4)."""
    atual = (HOJE - pd.Timedelta(days=dias), ONTEM)
    anterior = (HOJE - pd.Timedelta(days=2 * dias), HOJE - pd.Timedelta(days=dias + 1))
    return atual, anterior


def recorte(tabela, inicio, fim, coluna="data"):
    if tabela is None or tabela.empty:
        return tabela
    return tabela[(tabela[coluna] >= inicio) & (tabela[coluna] <= fim)]


def pedidos_no_periodo(inicio, fim):
    if vendas_df is None:
        return None
    return recorte(vendas_df, inicio, fim)["pedido"].nunique()


# ---------- Pneus monitorados: código da Roma e posição de preço de hoje ----------
produtos_m = pd.read_csv("produtos_monitorados.csv", sep=";", dtype=str)
produtos_m["pneu"] = produtos_m["medida"] + " " + produtos_m["modelo"]
produtos_m["sku_roma"] = produtos_m["sku_roma"].fillna("").str.replace(r"\.0$", "", regex=True)
MAPA_SKU = dict(zip(produtos_m["sku_roma"], produtos_m["pneu"]))
_precos = base[base["conc_preco_pix"].notna()]
POSICAO_PRECO = (_precos.groupby("pneu").agg(roma=("roma_preco_pix", "first"), menor=("conc_preco_pix", "min"))
                 .eval("roma / menor - 1").rename("dif_preco"))


with aba_site:
    st.markdown("**Como o site da Roma está performando: usuários, origem do tráfego, páginas, buscas e "
                "funil de cada pneu, cruzado com a posição de preço.**")

    c_botao, c_info = st.columns([1, 3])
    if TEM_ACESSO_GA4:
        if c_botao.button("🔄 Atualizar GA4 agora", key="ga4_agora",
                          help="Busca os números do GA4 e do Google Ads neste minuto."):
            st.session_state["ga4_vivo"] = pd.Timestamp.now()
    dados_ga4, origem_ga4, aviso_ga4 = carregar_ga4()
    if aviso_ga4:
        st.warning(aviso_ga4)
    c_info.caption(origem_ga4)

    if dados_ga4 is None:
        st.info("Ainda não há dados do GA4. Rode o coletor no computador (com a chave em C:\\chaves) "
                "ou clique em **🔄 Atualizar GA4 agora**.")
    else:
        # ---------- Tempo real ----------
        if dados_ga4.get("ativos_agora") is not None:
            t1, t2 = st.columns([1, 3])
            t1.metric("🟢 Usuários no site agora", dados_ga4["ativos_agora"],
                      help="Usuários ativos nos últimos 30 minutos (tempo real do GA4).")
            if not dados_ga4["paginas_agora"].empty:
                t2.dataframe(dados_ga4["paginas_agora"].rename(columns={"pagina": "Página agora",
                                                                       "usuarios": "Usuários"}),
                             hide_index=True, width="stretch", height=180)

        # ---------- Resumo do período ----------
        modo = st.radio("Período", ["Um dia", "Últimos 7 dias", "Últimos 30 dias"], horizontal=True,
                        key="ga4_periodo")
        diario_g = dados_ga4["diario"]
        if modo == "Um dia":
            dias_sel = 1
            dia_sel, dia_comp = escolher_dia("ga4", diario_g["data"].min())
            ini_a = fim_a = dia_sel
            ini_b = fim_b = dia_comp
            rotulo_periodo = nome_dia(dia_sel)
            texto_periodo = f"{nome_dia(dia_sel)}, comparado com {nome_dia(dia_comp)}"
            if dia_sel == HOJE:
                texto_periodo += ". Hoje ainda está em andamento"
            # Para um dia, os totais saem da tabela diária
            colunas_k = ["activeUsers", "newUsers", "sessions"]
            a = diario_g.loc[diario_g["data"] == dia_sel, colunas_k].sum()
            b = diario_g.loc[diario_g["data"] == dia_comp, colunas_k].sum()
            tem_resumo = True
        else:
            dias_sel = 7 if "7" in modo else 30
            (ini_a, fim_a), (ini_b, fim_b) = janela(dias_sel)
            rotulo_periodo = f"últimos {dias_sel} dias"
            texto_periodo = f"{ini_a:%d/%m} a {fim_a:%d/%m}, comparado com {ini_b:%d/%m} a {fim_b:%d/%m}"
            # Para 7 ou 30 dias, o resumo do GA4 (usuários não se somam dia a dia: a mesma pessoa volta)
            res = dados_ga4["resumo"]
            res = res[res["dias"] == dias_sel].set_index("dateRange")
            tem_resumo = {"atual", "anterior"} <= set(res.index)
            if tem_resumo:
                a, b = res.loc["atual"], res.loc["anterior"]
        if tem_resumo:
            k = st.columns(5)
            k[0].metric("Usuários ativos", numero(a["activeUsers"]), variacao(a["activeUsers"], b["activeUsers"]))
            k[1].metric("Novos usuários", numero(a["newUsers"]), variacao(a["newUsers"], b["newUsers"]))
            k[2].metric("Sessões", numero(a["sessions"]), variacao(a["sessions"], b["sessions"]))
            # Compras e conversão vêm do SEU controle de faturados, não do GA4
            ped_a, ped_b = pedidos_no_periodo(ini_a, fim_a), pedidos_no_periodo(ini_b, fim_b)
            if ped_a is None:
                k[3].metric("Pedidos faturados", "—", help="Sem vendas.csv. Rode o coletor com o Excel no Y:.")
                k[4].metric("Conversão real", "—")
            else:
                conv_a = ped_a / a["sessions"] if a["sessions"] else 0
                conv_b = ped_b / b["sessions"] if b["sessions"] else 0
                k[3].metric("Pedidos faturados", numero(ped_a), variacao(ped_a, ped_b),
                            help="Do seu controle de vendas faturadas (cancelados já fora).")
                k[4].metric("Conversão real", porcento(conv_a, 2),
                            f"{(conv_a - conv_b) * 100:+.2f} p.p.".replace(".", ",") if conv_b else None,
                            help="Pedidos faturados ÷ sessões do site no mesmo período.")
            st.caption(f"Período: {texto_periodo}. "
                       "Compras e receita do GA4 não aparecem aqui porque contam PIX não pago, cartão "
                       "reprovado e página recarregada. O número oficial é o seu controle de faturados.")

        # ---------- Evolução diária ----------
        st.subheader("📅 Dia a dia")
        metricas_dia = {"Usuários ativos": "activeUsers", "Sessões": "sessions", "Novos usuários": "newUsers",
                        "Pedidos faturados": "pedidos"}
        escolhidas = st.multiselect("Métricas", list(metricas_dia), default=["Usuários ativos", "Sessões"],
                                    key="ga4_metricas_dia")
        dia = dados_ga4["diario"]
        dia = dia[dia["data"] >= dia["data"].max() - pd.Timedelta(days=max(dias_sel * 2, 30))].copy()
        if vendas_df is not None:
            ped_dia = vendas_df.groupby("data")["pedido"].nunique().rename("pedidos")
            dia = dia.merge(ped_dia, left_on="data", right_index=True, how="left")
        dia["pedidos"] = dia["pedidos"].fillna(0) if "pedidos" in dia else 0
        if escolhidas:
            longa_dia = dia.melt(id_vars="data", value_vars=[metricas_dia[m] for m in escolhidas],
                                 var_name="metrica", value_name="valor")
            longa_dia["metrica"] = longa_dia["metrica"].map({v: k for k, v in metricas_dia.items()})
            fig = px.line(longa_dia, x="data", y="valor", color="metrica", markers=True,
                          labels={"data": "Dia", "valor": "", "metrica": ""})
            fig.update_traces(line=dict(width=3))
            if dias_sel == 1:
                fig.add_vline(x=dia_sel, line_dash="dot", line_color="#555")
            st.plotly_chart(estilo_grafico(fig, 380), width="stretch", key="ga4_grafico_dia")
            st.caption("O último dia (hoje) ainda está em andamento." +
                       (" A linha pontilhada marca o dia escolhido." if dias_sel == 1 else ""))

        # ---------- Por hora ----------
        h_a, h_b = (dia_sel, dia_comp) if dias_sel == 1 else (HOJE, ONTEM)
        st.subheader(f"🕐 Hora a hora: {nome_dia(h_a)} x {nome_dia(h_b)}")
        hora = dados_ga4["horario"].copy()
        hora = hora[hora["data"].isin([h_a, h_b])]
        if hora.empty:
            st.info("Sem dados por hora para esses dias (o painel guarda os últimos 35 dias por hora).")
        else:
            hora["dia"] = hora["data"].map({h_a: nome_dia(h_a), h_b: nome_dia(h_b)})
            fig = px.line(hora, x="hora", y="activeUsers", color="dia", markers=True,
                          color_discrete_map={nome_dia(h_a): COR_GOODYEAR, nome_dia(h_b): COR_CINZA},
                          labels={"hora": "Hora do dia", "activeUsers": "Usuários ativos", "dia": ""})
            fig.update_traces(line=dict(width=3))
            fig.update_xaxes(dtick=1)
            st.plotly_chart(estilo_grafico(fig, 340), width="stretch", key="ga4_grafico_hora")

        # ---------- Aquisição ----------
        st.subheader("🧭 De onde vêm as visitas")
        if dias_sel == 1:
            # Um dia: usa a tabela de aquisição dia a dia
            ad = dados_ga4.get("aquisicao_diaria")
            if ad is None or ad.empty:
                st.info("Para ver a origem das visitas por dia, rode o coletor de novo (dado novo desta versão).")
                aq = pd.DataFrame(columns=["tipo", "nome", "atual_sessions", "atual_newUsers", "anterior_sessions"])
            else:
                metr = ["sessions", "newUsers"]
                atual_aq = ad[ad["data"] == dia_sel].groupby(["tipo", "nome"])[metr].sum().add_prefix("atual_")
                ant_aq = ad[ad["data"] == dia_comp].groupby(["tipo", "nome"])[metr].sum().add_prefix("anterior_")
                aq = atual_aq.join(ant_aq, how="outer").fillna(0).reset_index()
                aq = aq[aq["atual_sessions"] > 0]
        else:
            aq = dados_ga4["aquisicao"]
            aq = aq[aq["dias"] == dias_sel].copy()
        for col in ["atual_sessions", "anterior_sessions", "atual_newUsers"]:
            if col not in aq:
                aq[col] = 0
        aq["var_sessoes"] = [variacao(x, y) or "novo" for x, y in zip(aq["atual_sessions"], aq["anterior_sessions"])]

        canais = aq[aq["tipo"] == "Grupo de canais"].sort_values("atual_sessions", ascending=False)
        if not canais.empty:
            fig = px.bar(canais, x="atual_sessions", y="nome", orientation="h", text="var_sessoes",
                         labels={"atual_sessions": f"Sessões ({rotulo_periodo})", "nome": " "},
                         color_discrete_sequence=[COR_GOODYEAR])
            fig.update_traces(texttemplate="<b>%{x:,.0f}</b> (%{text})", textposition="outside")
            fig.update_yaxes(categoryorder="total ascending")
            st.plotly_chart(estilo_grafico(fig, max(320, 42 * len(canais))), width="stretch",
                            key="ga4_grafico_canais")
            st.caption("Entre parênteses: variação das sessões contra o período anterior.")

        def tabela_aquisicao(tipo):
            t = aq[aq["tipo"] == tipo].sort_values("atual_sessions", ascending=False).head(15)
            return pd.DataFrame({
                tipo: t["nome"],
                "Sessões": t["atual_sessions"].map(numero),
                "Var. sessões": t["var_sessoes"],
                "Novos usuários": t["atual_newUsers"].map(numero),
            })

        a1, a2 = st.columns(2)
        with a1:
            st.markdown("**Origem**")
            st.dataframe(tabela_aquisicao("Origem"), hide_index=True, width="stretch")
        with a2:
            st.markdown("**Campanha**")
            st.dataframe(tabela_aquisicao("Campanha"), hide_index=True, width="stretch")

        # ---------- Ligação com os pneus monitorados ----------
        produtos_m["caminho"] = produtos_m["url_roma"].fillna("").map(
            lambda u: "/" + u.rstrip("/").split("/")[-1] if u.startswith("http") else None)
        mapa_caminho = dict(zip(produtos_m["caminho"], produtos_m["pneu"]))

        # ---------- Páginas ----------
        st.subheader("📄 Páginas mais vistas (últimos 30 dias)")
        pg = dados_ga4["paginas"].head(25).copy()
        pg["Pneu monitorado"] = pg["pagePath"].map(mapa_caminho).fillna("")
        st.dataframe(pd.DataFrame({
            "Página": pg["pagePath"], "Visualizações": pg["screenPageViews"].map(numero),
            "Usuários": pg["activeUsers"].map(numero), "Pneu monitorado": pg["Pneu monitorado"],
        }), hide_index=True, width="stretch")

        # ---------- Buscas ----------
        st.subheader("🔍 O que os clientes pesquisam no site (últimos 30 dias)")
        bs = dados_ga4["buscas"].copy()
        if bs.empty:
            st.info("O GA4 não registrou termos de busca no período.")
        else:
            medidas_monit = set(produtos_m["medida"].str.upper().str.replace("C", "", regex=False))
            bs["Status"] = bs["medida"].map(
                lambda m: "" if pd.isna(m) or not m else
                ("✅ Monitorada" if str(m).upper() in medidas_monit else "🆕 Não monitorada"))
            por_medida = (bs.dropna(subset=["medida"]).groupby("medida", as_index=False)["buscas"].sum()
                          .sort_values("buscas", ascending=False).head(15))
            if not por_medida.empty:
                por_medida["status"] = por_medida["medida"].map(
                    lambda m: "Monitorada" if m.upper() in medidas_monit else "Não monitorada")
                fig = px.bar(por_medida, x="buscas", y="medida", color="status", orientation="h",
                             text="buscas", color_discrete_map={"Monitorada": COR_GOODYEAR,
                                                                "Não monitorada": COR_LARANJA},
                             labels={"buscas": "Buscas", "medida": " ", "status": ""})
                fig.update_traces(texttemplate="<b>%{text:,.0f}</b>", textposition="outside")
                fig.update_yaxes(categoryorder="total ascending")
                st.plotly_chart(estilo_grafico(fig, max(320, 36 * len(por_medida))), width="stretch",
                                key="ga4_grafico_buscas")
                st.caption("Medidas mais buscadas. Em laranja: muita procura e fora da lista monitorada, "
                           "candidatas a entrar no painel.")
            with st.expander("📋 Todos os termos buscados"):
                st.dataframe(pd.DataFrame({"Termo": bs["termo"], "Buscas": bs["buscas"].map(numero),
                                           "Medida": bs["medida"].fillna(""), "Status": bs["Status"]}),
                             hide_index=True, width="stretch")

        # ---------- Funil por pneu x vendas faturadas x preço ----------
        st.subheader("🛒 Funil de cada pneu x vendas faturadas x preço (últimos 30 dias)")
        it = dados_ga4["itens"].copy()
        ini_30, fim_30 = HOJE - pd.Timedelta(days=30), ONTEM
        vendas_30 = recorte(vendas_df, ini_30, fim_30) if vendas_df is not None else pd.DataFrame(
            columns=["codigo", "pedido", "qtd", "valor"])
        vend_cod = (vendas_30.groupby("codigo")
                    .agg(pedidos=("pedido", "nunique"), pneus=("qtd", "sum"), receita=("valor", "sum")))
        if it.empty:
            st.info("O GA4 não trouxe dados de produtos (eventos de e-commerce) no período.")
        else:
            # Visualizações e carrinho vêm do GA4; pedidos e receita, do seu controle de faturados
            it["itemId"] = it["itemId"].astype(str).str.replace(r"\.0$", "", regex=True)
            it = (it.groupby("itemId", as_index=False)
                  .agg(itemName=("itemName", "first"), itemsViewed=("itemsViewed", "sum"),
                       itemsAddedToCart=("itemsAddedToCart", "sum")))
            it = it.merge(vend_cod, left_on="itemId", right_index=True, how="left")
            it[["pedidos", "pneus", "receita"]] = it[["pedidos", "pneus", "receita"]].fillna(0)
            it["pneu"] = it["itemId"].map(MAPA_SKU)

            monit = produtos_m[["sku_roma", "pneu"]].merge(it.drop(columns="pneu"), left_on="sku_roma",
                                                           right_on="itemId", how="left")
            for col in ["itemsViewed", "itemsAddedToCart"]:
                monit[col] = monit[col].fillna(0)
            # pneus monitorados que venderam mas não aparecem no GA4 também entram
            monit = monit.drop(columns=["pedidos", "pneus", "receita"]).merge(
                vend_cod, left_on="sku_roma", right_index=True, how="left")
            monit[["pedidos", "pneus", "receita"]] = monit[["pedidos", "pneus", "receita"]].fillna(0)
            vistos = monit["itemsViewed"].where(monit["itemsViewed"] > 0)
            monit["tx_carrinho"] = monit["itemsAddedToCart"] / vistos
            monit["tx_conversao"] = monit["pedidos"] / vistos
            monit["dif_preco"] = monit["pneu"].map(POSICAO_PRECO)

            st.dataframe(pd.DataFrame({
                "Pneu": monit["pneu"],
                "Visualizações": monit["itemsViewed"].map(numero),
                "Carrinho": monit["itemsAddedToCart"].map(numero),
                "% carrinho": monit["tx_carrinho"].map(porcento),
                "Pedidos faturados": monit["pedidos"].map(numero),
                "Pneus vendidos": monit["pneus"].map(numero),
                "Receita faturada": monit["receita"].map(formatar_real),
                "% conversão": monit["tx_conversao"].map(lambda v: porcento(v, 2)),
                "Roma x menor PIX": monit["dif_preco"].map(formatar_pct),
            }), hide_index=True, width="stretch")
            st.caption("Visualizações e carrinho: GA4. Pedidos, pneus e receita: seu controle de faturados "
                       "(pelo código do produto). % conversão = pedidos faturados ÷ visualizações do produto.")

            graf = monit.dropna(subset=["dif_preco", "tx_conversao"])
            if len(graf) >= 3:
                fig = px.scatter(graf, x="dif_preco", y="tx_conversao", size="itemsViewed", text="pneu",
                                 labels={"dif_preco": "Preço da Roma x menor PIX dos concorrentes",
                                         "tx_conversao": "Conversão (pedidos faturados ÷ visualizações)"},
                                 color_discrete_sequence=[COR_GOODYEAR])
                fig.update_traces(textposition="top center", textfont=dict(size=11))
                fig.update_xaxes(tickformat="+.0%")
                fig.update_yaxes(tickformat=".1%")
                fig.add_vline(x=0, line_dash="dot", line_color="#555")
                st.plotly_chart(estilo_grafico(fig, 460), width="stretch", key="ga4_dispersao")
                st.caption("Cada bolha é um pneu (tamanho = visualizações). À esquerda da linha, a Roma está mais "
                           "barata. Se os pneus à direita (Roma mais cara) converterem menos, o preço está pesando. "
                           "Com poucas vendas por pneu, leia como tendência, não como certeza.")

            with st.expander("📋 Funil de todos os produtos do site"):
                todos = it.sort_values("itemsViewed", ascending=False).head(100)
                st.dataframe(pd.DataFrame({
                    "Produto": todos["itemName"], "Código": todos["itemId"],
                    "Visualizações": todos["itemsViewed"].map(numero),
                    "Carrinho": todos["itemsAddedToCart"].map(numero),
                    "Pedidos faturados": todos["pedidos"].map(numero),
                    "Receita faturada": todos["receita"].map(formatar_real),
                }), hide_index=True, width="stretch")

        # ---------- Google Ads ----------
        st.subheader("📣 Google Ads")
        ads = dados_ga4.get("ads")
        if ads is None or ads.empty:
            st.info("Ainda sem dados do Google Ads. Eles chegam pelo próprio GA4 quando a conta do Google Ads "
                    "está **vinculada** à propriedade: GA4 > Administrador > Vinculações de produtos > "
                    "Vinculações do Google Ads. Depois de vincular, rode o coletor de novo.")
        else:
            ads_a, ads_b = recorte(ads, ini_a, fim_a), recorte(ads, ini_b, fim_b)

            def resumo_ads(t):
                custo, cliques, impr = t["custo"].sum(), t["cliques"].sum(), t["impressoes"].sum()
                return {"custo": custo, "cliques": cliques, "impressoes": impr,
                        "cpc": custo / cliques if cliques else None, "ctr": cliques / impr if impr else None}

            ra, rb = resumo_ads(ads_a), resumo_ads(ads_b)
            receita_a = recorte(vendas_df, ini_a, fim_a)["valor"].sum() if vendas_df is not None else None
            receita_b = recorte(vendas_df, ini_b, fim_b)["valor"].sum() if vendas_df is not None else None
            g = st.columns(5)
            g[0].metric("Investimento", formatar_real(ra["custo"]), variacao(ra["custo"], rb["custo"]),
                        delta_color="off")
            g[1].metric("Cliques", numero(ra["cliques"]), variacao(ra["cliques"], rb["cliques"]))
            g[2].metric("CPC médio", formatar_real(ra["cpc"]) if ra["cpc"] else "—",
                        variacao(ra["cpc"], rb["cpc"]) if ra["cpc"] and rb["cpc"] else None, delta_color="inverse")
            g[3].metric("CTR", porcento(ra["ctr"], 2))
            if receita_a:
                peso_a = ra["custo"] / receita_a
                peso_b = rb["custo"] / receita_b if receita_b else None
                g[4].metric("Mídia ÷ receita faturada", porcento(peso_a),
                            f"{(peso_a - peso_b) * 100:+.1f} p.p.".replace(".", ",") if peso_b else None,
                            delta_color="inverse",
                            help="Quanto do faturamento do site foi gasto em Google Ads no período. "
                                 "Considera TODAS as vendas do site, não só as que vieram do anúncio.")
            else:
                g[4].metric("Mídia ÷ receita faturada", "—", help="Sem vendas faturadas no período.")

            ads_dia = (ads[ads["data"] >= HOJE - pd.Timedelta(days=max(dias_sel * 2, 30))]
                       .groupby("data", as_index=False)[["custo", "cliques"]].sum())
            ads_dia["cor"] = ["Dia escolhido" if dias_sel == 1 and d == dia_sel else "Outros dias"
                              for d in ads_dia["data"]]
            fig = px.bar(ads_dia, x="data", y="custo", color="cor",
                         labels={"data": "Dia", "custo": "Investimento (R$)", "cor": ""},
                         color_discrete_map={"Dia escolhido": COR_GOODYEAR, "Outros dias": COR_GOODYEAR_CLARO})
            fig.update_layout(showlegend=dias_sel == 1)
            st.plotly_chart(estilo_grafico(fig, 320), width="stretch", key="ga4_ads_dia")
            if dias_sel == 1 and dia_sel >= HOJE:
                st.caption("O custo do Google Ads chega até ontem. Escolha um dia anterior para ver o investimento.")

            camp = (ads_a.groupby(["campanha", "tipo_campanha"], as_index=False)
                    [["custo", "cliques", "impressoes"]].sum().sort_values("custo", ascending=False))
            st.dataframe(pd.DataFrame({
                "Campanha": camp["campanha"], "Tipo": camp["tipo_campanha"],
                "Investimento": camp["custo"].map(formatar_real), "Cliques": camp["cliques"].map(numero),
                "Impressões": camp["impressoes"].map(numero),
                "CPC": (camp["custo"] / camp["cliques"].where(camp["cliques"] > 0)).map(formatar_real),
                "CTR": (camp["cliques"] / camp["impressoes"].where(camp["impressoes"] > 0)).map(
                    lambda v: porcento(v, 2)),
            }), hide_index=True, width="stretch")
            st.caption("Custo, cliques e impressões vêm do Google Ads pelo GA4 (conta vinculada). Para ver o "
                       "resultado por produto do Shopping, o próximo passo seria a API do Google Ads.")


# ============================================================
# 12. VENDAS (seu controle de faturados)
# ============================================================

def resumo_vendas(t):
    pedidos = t["pedido"].nunique()
    pneus, receita = t["qtd"].sum(), t["valor"].sum()
    return {"pedidos": pedidos, "pneus": pneus, "receita": receita,
            "ticket": receita / pedidos if pedidos else None,
            "preco_pneu": receita / pneus if pneus else None}


def sessoes_no_periodo(dados, inicio, fim):
    """Sessões do GA4 no período: pelo diário (últimos 90 dias) ou, se for mais antigo, pelo mensal."""
    if dados is None:
        return None
    diario = dados.get("diario")
    if diario is not None and not diario.empty and inicio >= diario["data"].min():
        return recorte(diario, inicio, fim)["sessions"].sum()
    mensal_ga4 = dados.get("mensal")
    if mensal_ga4 is not None and not mensal_ga4.empty:
        meses = mensal_ga4[(mensal_ga4["mes"] >= inicio.to_period("M").to_timestamp()) & (mensal_ga4["mes"] <= fim)]
        return meses["sessions"].sum() if not meses.empty else None
    return None


with aba_vendas:
    st.markdown("**Vendas faturadas do e-commerce (seu controle, sem cancelados), cruzadas com o tráfego do "
                "site e o investimento em Google Ads.**")

    if vendas_df is None or vendas_df.empty:
        st.info("Ainda não há vendas (falta o arquivo `vendas.csv` na pasta). No terminal do VS Code, dentro da "
                "pasta do projeto, rode `python vendas.py` e veja a mensagem: se disser que o Excel não foi "
                "encontrado, ajuste o `CAMINHO_EXCEL` no topo do `vendas.py`. Depois atualize esta página (F5).")
    else:
        ultima_venda = vendas_df["data"].max()
        aviso_atraso = " ⚠️ A planilha pode estar desatualizada." if ultima_venda < ONTEM - pd.Timedelta(days=3) else ""
        st.caption(f"Vendas até {ultima_venda:%d/%m/%Y} (última data na planilha).{aviso_atraso}")

        # Dados do GA4 (arquivos da última coleta) para sessões e Google Ads
        ga4_salvo, _, _ = carregar_ga4()
        ads_v = ga4_salvo.get("ads") if ga4_salvo else None

        # ---------- Período ----------
        opcoes_p = ["Um dia", "Últimos 7 dias", "Últimos 30 dias", "Mês atual", "Ano até ontem"]
        periodo = st.radio("Período", opcoes_p, index=2, horizontal=True, key="vendas_periodo")
        if periodo == "Um dia":
            ini, ini_ant = escolher_dia("vendas", vendas_df["data"].min(), padrao=min(ONTEM, ultima_venda))
            fim, fim_ant = ini, ini_ant
            texto_comp = nome_dia(ini_ant)
        elif periodo.startswith("Últimos"):
            (ini, fim), (ini_ant, fim_ant) = janela(7 if "7" in periodo else 30)
            texto_comp = f"{ini_ant:%d/%m} a {fim_ant:%d/%m}"
        elif periodo == "Mês atual":
            ini, fim = ONTEM.replace(day=1), ONTEM
            ini_ant = ini - pd.DateOffset(months=1)
            fim_ant = min(ini_ant + (fim - ini), ini - pd.Timedelta(days=1))
            texto_comp = f"mesmos dias do mês anterior ({ini_ant:%d/%m} a {fim_ant:%d/%m})"
        else:
            ini, fim = ONTEM.replace(month=1, day=1), ONTEM
            ini_ant, fim_ant = ini - pd.DateOffset(years=1), fim - pd.DateOffset(years=1)
            texto_comp = "mesmo período do ano passado"
        atual_v, anterior_v = recorte(vendas_df, ini, fim), recorte(vendas_df, ini_ant, fim_ant)
        ra, rb = resumo_vendas(atual_v), resumo_vendas(anterior_v)
        tem_anterior = rb["pedidos"] > 0

        def delta(chave):
            return variacao(ra[chave], rb[chave]) if tem_anterior and ra[chave] is not None else None

        k = st.columns(6)
        k[0].metric("Pedidos", numero(ra["pedidos"]), delta("pedidos"))
        k[1].metric("Pneus vendidos", numero(ra["pneus"]), delta("pneus"))
        k[2].metric("Receita faturada", formatar_real(ra["receita"]), delta("receita"))
        k[3].metric("Ticket médio", formatar_real(ra["ticket"]), delta("ticket"))
        k[4].metric("Preço médio por pneu", formatar_real(ra["preco_pneu"]), delta("preco_pneu"))
        sess_a, sess_b = sessoes_no_periodo(ga4_salvo, ini, fim), sessoes_no_periodo(ga4_salvo, ini_ant, fim_ant)
        if sess_a:
            conv_a = ra["pedidos"] / sess_a
            conv_b = rb["pedidos"] / sess_b if sess_b and tem_anterior else None
            k[5].metric("Conversão real", porcento(conv_a, 2),
                        f"{(conv_a - conv_b) * 100:+.2f} p.p.".replace(".", ",") if conv_b else None,
                        help=f"Pedidos faturados ÷ {numero(sess_a)} sessões do site no período (GA4).")
        else:
            k[5].metric("Conversão real", "—", help="Sem sessões do GA4 para o período.")
        st.caption((nome_dia(ini) if ini == fim else f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}") +
                   (f", comparado com {texto_comp}." if tem_anterior else ". Sem vendas no período de comparação."))

        # ---------- Mês a mês ----------
        st.subheader("📆 Mês a mês")
        mes = (vendas_df.assign(mes=vendas_df["data"].dt.to_period("M").dt.to_timestamp())
               .groupby("mes").agg(pedidos=("pedido", "nunique"), pneus=("qtd", "sum"), receita=("valor", "sum")))
        mes["ticket"] = mes["receita"] / mes["pedidos"]
        mensal_ga4 = ga4_salvo.get("mensal") if ga4_salvo else None
        if mensal_ga4 is not None and not mensal_ga4.empty:
            mes = mes.join(mensal_ga4.set_index("mes")["sessions"])
            mes["conversao"] = mes["pedidos"] / mes["sessions"]
        if ads_v is not None and not ads_v.empty:
            mes = mes.join(ads_v.assign(mes=ads_v["data"].dt.to_period("M").dt.to_timestamp())
                           .groupby("mes")["custo"].sum())
            mes["peso_midia"] = mes["custo"] / mes["receita"]
        mes = mes.reset_index()
        mes["rotulo"] = mes["pedidos"].map(lambda p: f"{p} ped.")
        fig = px.bar(mes, x="mes", y="receita", text="rotulo", color_discrete_sequence=[COR_GOODYEAR],
                     labels={"mes": "", "receita": "Receita faturada (R$)"})
        fig.update_traces(textposition="outside")
        fig.update_xaxes(dtick="M1", tickformat="%b/%y")
        st.plotly_chart(estilo_grafico(fig, 360), width="stretch", key="vendas_mes")

        tabela_mes = pd.DataFrame({
            "Mês": mes["mes"].dt.strftime("%m/%Y"), "Pedidos": mes["pedidos"].map(numero),
            "Pneus": mes["pneus"].map(numero), "Receita": mes["receita"].map(formatar_real),
            "Ticket médio": mes["ticket"].map(formatar_real)})
        if "sessions" in mes:
            tabela_mes["Sessões"] = mes["sessions"].map(lambda v: "—" if pd.isna(v) else numero(v))
            tabela_mes["Conversão real"] = mes["conversao"].map(lambda v: porcento(v, 2))
        if "custo" in mes:
            tabela_mes["Google Ads"] = mes["custo"].map(formatar_real)
            tabela_mes["Mídia ÷ receita"] = mes["peso_midia"].map(porcento)
        st.dataframe(tabela_mes.iloc[::-1], hide_index=True, width="stretch")
        st.caption("O mês atual ainda está em andamento. Conversão real = pedidos faturados ÷ sessões do site.")

        if atual_v.empty:
            st.info("Nenhuma venda faturada no período escolhido.")
        else:
            # ---------- Pedidos do dia (modo Um dia) ----------
            if ini == fim:
                st.subheader(f"🧾 Pedidos faturados em {nome_dia(ini)}")
                st.dataframe(pd.DataFrame({
                    "Pedido": atual_v["pedido"], "Pneu": atual_v["descricao"], "Grupo": atual_v["grupo"],
                    "Quantidade": atual_v["qtd"], "Valor": atual_v["valor"].map(formatar_real),
                }), hide_index=True, width="stretch")

        if not atual_v.empty and ini != fim:
            # ---------- Evolução no período ----------
            st.subheader("📅 Vendas no período")
            longo = (fim - ini).days > 45
            evol = atual_v.assign(quando=atual_v["data"].dt.to_period("W").dt.start_time if longo
                                  else atual_v["data"])
            evol = evol.groupby("quando", as_index=False).agg(pedidos=("pedido", "nunique"),
                                                               receita=("valor", "sum"))
            fig = px.bar(evol, x="quando", y="receita", text="pedidos", color_discrete_sequence=[COR_GOODYEAR],
                         labels={"quando": "Semana" if longo else "Dia", "receita": "Receita faturada (R$)"})
            fig.update_traces(texttemplate="%{text} ped.", textposition="outside")
            st.plotly_chart(estilo_grafico(fig, 340), width="stretch", key="vendas_periodo_graf")

            # ---------- Tamanho do pedido ----------
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("🧩 Tamanho do pedido")
                ped = atual_v.groupby("pedido").agg(pneus=("qtd", "sum"), receita=("valor", "sum"),
                                                     tamanho=("tamanho_pedido", "first"))
                tam = ped.groupby("tamanho").agg(pedidos=("pneus", "size"), receita=("receita", "sum"))
                tam["pct"] = tam["pedidos"] / tam["pedidos"].sum()
                tam["ticket"] = tam["receita"] / tam["pedidos"]
                tam = tam.reindex([t for t in ["1 pneu", "2 pneus", "4 pneus", "Outras quantidades"]
                                   if t in tam.index]).reset_index()
                tam["rotulo"] = [f"{porcento(p, 0)} · ticket {formatar_real(t)}" for p, t in zip(tam["pct"], tam["ticket"])]
                fig = px.bar(tam, x="pedidos", y="tamanho", orientation="h", text="rotulo",
                             color_discrete_sequence=[COR_GOODYEAR], labels={"pedidos": "Pedidos", "tamanho": " "})
                fig.update_traces(textposition="outside")
                fig.update_yaxes(categoryorder="array", categoryarray=list(tam["tamanho"])[::-1])
                st.plotly_chart(estilo_grafico(fig, 300), width="stretch", key="vendas_tamanho")
            with c2:
                st.subheader("🚙 Por grupo")
                grp = atual_v.groupby("grupo", as_index=False).agg(receita=("valor", "sum"), pneus=("qtd", "sum"))
                fig = px.bar(grp, x="receita", y="grupo", orientation="h", text="pneus",
                             color_discrete_sequence=[COR_GOODYEAR], labels={"receita": "Receita (R$)", "grupo": " "})
                fig.update_traces(texttemplate="%{text} pneus", textposition="outside")
                fig.update_yaxes(categoryorder="total ascending")
                st.plotly_chart(estilo_grafico(fig, 300), width="stretch", key="vendas_grupo")

            # ---------- Pneus mais vendidos ----------
            st.subheader("🏆 Pneus mais vendidos no período")
            nomes = vendas_df.sort_values("data").groupby("codigo")["descricao"].last()
            top = (atual_v.groupby("codigo")
                   .agg(pedidos=("pedido", "nunique"), pneus=("qtd", "sum"), receita=("valor", "sum"))
                   .sort_values(["pneus", "receita"], ascending=False).reset_index())
            top["Monitorado"] = top["codigo"].map(lambda c: "✅" if c in MAPA_SKU else "")
            top["dif"] = top["codigo"].map(MAPA_SKU).map(POSICAO_PRECO)
            st.dataframe(pd.DataFrame({
                "Pneu": top["codigo"].map(nomes), "Código": top["codigo"], "Monitorado": top["Monitorado"],
                "Pedidos": top["pedidos"].map(numero), "Pneus": top["pneus"].map(numero),
                "Receita": top["receita"].map(formatar_real),
                "Preço médio/pneu": (top["receita"] / top["pneus"]).map(formatar_real),
                "Roma x menor PIX hoje": top["dif"].map(formatar_pct),
            }).head(25), hide_index=True, width="stretch")
            nao_monit = top[top["Monitorado"] == ""].head(5)
            if not nao_monit.empty:
                st.caption("Vendem bem e não estão no monitor de preços: " +
                           "; ".join(nomes.get(c, c) for c in nao_monit["codigo"]) +
                           ". Candidatos a entrar na lista de pneus monitorados.")

        # ---------- Os 14 monitorados ----------
        st.subheader("🎯 Pneus monitorados: vendas no período x preço de hoje")
        m14 = produtos_m[["item", "grupo", "pneu", "sku_roma"]].copy()
        v14 = atual_v.groupby("codigo").agg(pedidos=("pedido", "nunique"), pneus=("qtd", "sum"),
                                            receita=("valor", "sum"))
        v14_ant = anterior_v.groupby("codigo")["qtd"].sum().rename("pneus_ant")
        m14 = m14.merge(v14, left_on="sku_roma", right_index=True, how="left").merge(
            v14_ant, left_on="sku_roma", right_index=True, how="left")
        m14[["pedidos", "pneus", "receita", "pneus_ant"]] = m14[["pedidos", "pneus", "receita", "pneus_ant"]].fillna(0)
        m14["dif"] = m14["pneu"].map(POSICAO_PRECO)
        st.dataframe(pd.DataFrame({
            "Pneu": m14["pneu"], "Grupo": m14["grupo"],
            "Pneus vendidos": m14["pneus"].map(numero),
            "Período anterior": m14["pneus_ant"].map(numero) if tem_anterior else "—",
            "Pedidos": m14["pedidos"].map(numero), "Receita": m14["receita"].map(formatar_real),
            "Roma x menor PIX hoje": m14["dif"].map(formatar_pct),
        }), hide_index=True, width="stretch")
        st.caption("Positivo em 'Roma x menor PIX' = Roma mais cara que o concorrente mais barato. "
                   "Pneu monitorado sem venda e com Roma mais cara é o primeiro lugar para olhar.")

        # ---------- Google Ads x vendas ----------
        if ads_v is not None and not ads_v.empty:
            st.subheader("📣 Google Ads x vendas faturadas")
            custo_a = recorte(ads_v, ini, fim)["custo"].sum()
            custo_b = recorte(ads_v, ini_ant, fim_ant)["custo"].sum()
            m = st.columns(3)
            m[0].metric("Investimento no período", formatar_real(custo_a), variacao(custo_a, custo_b),
                        delta_color="off")
            m[1].metric("Mídia ÷ receita faturada", porcento(custo_a / ra["receita"]) if ra["receita"] else "—",
                        help="Investimento em Google Ads ÷ toda a receita faturada do site no período.")
            m[2].metric("Receita por R$ 1 investido", f"R$ {ra['receita'] / custo_a:.2f}".replace(".", ",")
                        if custo_a else "—",
                        help="Receita faturada total ÷ investimento. Não é o ROAS do Google Ads: inclui vendas "
                             "de todos os canais.")
