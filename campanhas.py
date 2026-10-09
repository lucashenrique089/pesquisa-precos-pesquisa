"""
RADAR DE CAMPANHAS DOS CONCORRENTES | Roma Pneus
=================================================
O que faz (chamado automaticamente pelo coletor.py a cada coleta):
  - Pneu Store: lê os banners da página inicial (texto do banner, link e imagem)
  - Achei Pneus: lê as categorias de campanha pela API (ex.: "Pneus em oferta",
    "Pneus com frete grátis") e verifica se estão ativas (com produtos) ou pausadas
  - Classifica cada campanha por tipo (Black Friday, desconto, frete grátis...) e força
  - Compara com a coleta anterior: campanha NOVA ou ENCERRADA
  - Salva campanhas_atuais.csv (foto de hoje) e historico_campanhas.csv (todas as coletas)
"""

from curl_cffi import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import os

ARQUIVO_CAMPANHAS = "campanhas_atuais.csv"
ARQUIVO_HIST_CAMPANHAS = "historico_campanhas.csv"

HOME_PNEUSTORE = "https://www.pneustore.com.br/"
API_ACHEI = "https://www.acheipneus.com.br/graphql"

# Tipo de campanha -> palavras que identificam (procuradas no texto e no link, sem acento)
TIPOS = [
    ("Black Friday", ["black", "blackfriday", "black-friday", "esquenta", "novembro", "cyber"]),
    ("Data comemorativa", ["niver", "aniversario", "semana do", "semana-do", "dia-do", "dia do",
                           "dia das", "mes do", "natal", "verao", "ferias", "dia dos pais",
                           "dia das maes", "consumidor", "liquida"]),
    ("Desconto / PIX", ["OFF", "desconto", "pix", "oferta", "promo", "cupom", "outlet"]),
    ("Frete grátis", ["frete"]),
    ("Parcelamento", ["sem juros", "10x", "12x", "parcel"]),
    ("Sorteio / prêmio", ["premiad", "sorteio", "premio", "concorra", "numeros da sorte", "ganhe"]),
    ("Brinde", ["brinde"]),
    ("Garantia", ["garantia"]),
    ("Pagamento alternativo", ["pagaleve", "boleto parcelado", "pix parcelado"]),
]

# Força de cada tipo para o ranking (quanto maior, mais agressiva a campanha)
FORCA_TIPO = {"Black Friday": 5, "Data comemorativa": 4, "Desconto / PIX": 3, "Frete grátis": 3,
              "Parcelamento": 2, "Sorteio / prêmio": 2, "Brinde": 2, "Garantia": 1,
              "Pagamento alternativo": 1, "Institucional / marca": 0}

# Banners que não são campanha (logos, redes sociais, selos, formas de pagamento)
IGNORAR = ["logo", "whatsapp", "instagram", "facebook", "youtube", "tiktok", "linkedin",
           "reclame", "ebit", "selo", "certificado", "bandeira", "visa", "mastercard",
           "elo", "hipercard", "amex", "google", "apple", "app store", "play store"]

# Categorias da Achei Pneus que são filtros do site, e não campanhas
FILTROS_ACHEI = {"pneu", "aro", "pneus", "pneus-de-carro", "audio", "som-automotivo", "ciclismo",
                 "pecas-e-acessorios", "assistance"}


def sem_acento(texto):
    trocas = str.maketrans("áàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ", "aaaaeeiooouucAAAAEEIOOOUUC")
    return str(texto).translate(trocas).lower()


def classificar(titulo, link):
    """Devolve (tipo, força, maior % encontrado no texto)."""
    texto = sem_acento(f"{titulo} {link}")
    tipo = "Institucional / marca"
    for nome, palavras in TIPOS:
        if any(re.search(r"(\b|\d)off\b", texto) if p == "OFF" else p in texto for p in palavras):
            tipo = nome
            break
    percentuais = [int(p) for p in re.findall(r"(\d{1,2})\s*%", texto)]
    maior_pct = max(percentuais) if percentuais else None
    forca = FORCA_TIPO.get(tipo, 0)
    if maior_pct and maior_pct >= 15:
        forca += 1
    return tipo, forca, maior_pct


# ============================================================
# PNEU STORE: banners da página inicial
# ============================================================

def banners_pneustore():
    try:
        resposta = requests.get(HOME_PNEUSTORE, impersonate="chrome", timeout=25)
    except Exception as erro:
        print("   Campanhas Pneu Store: falha ao acessar |", erro)
        return []
    if resposta.status_code != 200:
        print("   Campanhas Pneu Store: bloqueado ou erro", resposta.status_code)
        return []

    soup = BeautifulSoup(resposta.text, "html.parser")
    achados = []
    for a in soup.find_all("a", href=True):
        img = a.find("img")
        if img is None:
            continue
        titulo = (img.get("alt") or img.get("title") or a.get("title") or "").strip()
        link = a["href"].strip()
        if not titulo or len(titulo) < 3:
            continue
        if link.startswith("http") and "pneustore.com.br" not in link:
            continue                                   # link externo (rede social, selo)
        if re.search(r"-\d{6,}/?$", link):
            continue                                   # é um produto, não um banner
        if any(p in sem_acento(titulo) for p in IGNORAR):
            continue

        imagem = img.get("src") or img.get("data-src") or ""
        if not imagem and img.get("srcset"):
            imagem = img["srcset"].split(",")[0].split()[0]
        if imagem.startswith("/"):
            imagem = HOME_PNEUSTORE.rstrip("/") + imagem
        if link.startswith("/"):
            link = HOME_PNEUSTORE.rstrip("/") + link

        achados.append({"concorrente": "PneuStore", "fonte": "Banner da página inicial",
                        "titulo": titulo, "link": link, "imagem": imagem, "status": "ativa"})

    # Remove repetidos (o mesmo banner aparece na versão desktop e mobile)
    vistos, unicos = set(), []
    for c in achados:
        chave = (sem_acento(c["titulo"]), c["link"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(c)
    return unicos


# ============================================================
# ACHEI PNEUS: categorias de campanha pela API
# ============================================================

def consulta_achei(consulta):
    try:
        resposta = requests.get(API_ACHEI, params={"query": consulta},
                                impersonate="chrome", timeout=25)
        return resposta.json().get("data") or {}
    except Exception:
        return {}


def campanhas_achei(skus_monitorados):
    dados = consulta_achei("{categories(pageSize:200){items{children{id name url_path include_in_menu "
                           "children{id name url_path include_in_menu}}}}}")
    raizes = (dados.get("categories") or {}).get("items") or []
    candidatas = []
    for raiz in raizes:
        for cat in raiz.get("children") or []:
            candidatas.append(cat)
            candidatas.extend(cat.get("children") or [])

    achados = []
    for cat in candidatas:
        caminho = cat.get("url_path") or ""
        nome = (cat.get("name") or "").strip()
        if not caminho or caminho.split("/")[0] in FILTROS_ACHEI:
            continue
        tipo, _, _ = classificar(nome, caminho)
        escondida = cat.get("include_in_menu") == 0
        if not escondida and tipo == "Institucional / marca":
            continue                                   # categoria comum do menu

        # Quantos produtos estão na campanha e quais dos nossos pneus monitorados
        resultado = consulta_achei('{products(filter:{category_id:{eq:"%s"}},pageSize:200)'
                                   '{total_count items{sku}}}' % cat["id"])
        produtos = resultado.get("products") or {}
        total = produtos.get("total_count") or 0
        skus = {i.get("sku") for i in produtos.get("items") or []}
        nossos = [nome_pneu for sku, nome_pneu in skus_monitorados.items() if sku in skus]

        achados.append({
            "concorrente": "Achei Pneus", "fonte": "Categoria de campanha",
            "titulo": nome[:1].upper() + nome[1:],
            "link": f"https://www.acheipneus.com.br/{caminho}", "imagem": "",
            "status": "ativa" if total > 0 else "pausada",
            "qtd_produtos": total, "pneus_monitorados": "; ".join(nossos),
        })
    return achados


# ============================================================
# COLETA + COMPARAÇÃO COM A ANTERIOR
# ============================================================

def coletar_campanhas(data_coleta, produtos):
    """Coleta as campanhas, salva e devolve (campanhas_atuais, mudancas)."""
    skus = {}
    if "sku_acheipneus" in produtos.columns:
        for _, p in produtos.dropna(subset=["sku_acheipneus"]).iterrows():
            skus[str(p["sku_acheipneus"]).split(".")[0]] = f'{p["medida"]} {p["modelo"]}'

    lista = banners_pneustore() + campanhas_achei(skus)
    colunas = ["data_coleta", "concorrente", "fonte", "titulo", "tipo", "forca", "maior_pct",
               "status", "qtd_produtos", "pneus_monitorados", "link", "imagem", "novidade"]
    atuais = pd.DataFrame(lista)
    if atuais.empty:
        atuais = pd.DataFrame(columns=colunas)
    else:
        classes = atuais.apply(lambda c: classificar(c["titulo"], c["link"]), axis=1)
        atuais["tipo"] = [c[0] for c in classes]
        atuais["forca"] = [c[1] for c in classes]
        atuais["maior_pct"] = [c[2] for c in classes]
        atuais.loc[atuais["status"] == "pausada", "forca"] = 0
    atuais["data_coleta"] = data_coleta
    for col in colunas:
        if col not in atuais.columns:
            atuais[col] = None

    # Compara com a coleta anterior (chave = concorrente + título + link)
    mudancas = []
    chave = lambda d: d["concorrente"] + "|" + d["titulo"].map(sem_acento) + "|" + d["link"].astype(str)
    if os.path.exists(ARQUIVO_HIST_CAMPANHAS) and not atuais.empty:
        hist = pd.read_csv(ARQUIVO_HIST_CAMPANHAS, sep=";", encoding="utf-8-sig")
        if not hist.empty:
            anterior = hist[hist["data_coleta"] == hist["data_coleta"].max()]
            ativas_antes = anterior[anterior["status"] == "ativa"]
            k_antes, k_agora = set(chave(ativas_antes)), set(chave(atuais[atuais["status"] == "ativa"]))
            atuais["novidade"] = ["NOVA" if (k in k_agora and k not in k_antes) else ""
                                  for k in chave(atuais)]
            for _, c in atuais[atuais["novidade"] == "NOVA"].iterrows():
                mudancas.append({"concorrente": c["concorrente"], "campanha": c["titulo"],
                                 "tipo": c["tipo"], "mudanca": "🆕 Campanha nova"})
            for _, c in ativas_antes[chave(ativas_antes).isin(k_antes - k_agora)].iterrows():
                mudancas.append({"concorrente": c["concorrente"], "campanha": c["titulo"],
                                 "tipo": c["tipo"], "mudanca": "🛑 Campanha encerrada"})

    atuais = atuais[colunas].sort_values(["concorrente", "forca"], ascending=[True, False])
    atuais.to_csv(ARQUIVO_CAMPANHAS, sep=";", index=False, encoding="utf-8-sig")
    ja_existe = os.path.exists(ARQUIVO_HIST_CAMPANHAS)
    atuais.to_csv(ARQUIVO_HIST_CAMPANHAS, sep=";", index=False, mode="a",
                  header=not ja_existe, encoding="utf-8-sig")

    mudancas = pd.DataFrame(mudancas, columns=["concorrente", "campanha", "tipo", "mudanca"])
    ativas = atuais[atuais["status"] == "ativa"]
    print()
    print(f"Campanhas: {len(ativas)} ativa(s) "
          f"({(ativas['concorrente'] == 'PneuStore').sum()} Pneu Store, "
          f"{(ativas['concorrente'] == 'Achei Pneus').sum()} Achei Pneus)")
    for _, m in mudancas.iterrows():
        print(f"   {m['mudanca']} | {m['concorrente']}: {m['campanha']} ({m['tipo']})")
    if (atuais["concorrente"] == "PneuStore").sum() == 0:
        print("   Atenção: nenhum banner lido na Pneu Store (o site pode ter mudado o layout).")
    return atuais, mudancas
