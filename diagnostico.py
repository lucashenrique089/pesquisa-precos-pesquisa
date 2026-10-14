"""
DIAGNÓSTICO RÁPIDO | Monitor de concorrência
=============================================
Testa cada fonte de dados com UM pneu e mostra ✅ (funcionou) ou ❌ (falhou).
Rode antes da primeira coleta, ou sempre que algum dado vier vazio no painel:

    python diagnostico.py

Leva menos de 1 minuto e não altera nenhum arquivo.
"""

import pandas as pd

import coletor
import parcelas
import campanhas


def mostrar(ok, titulo, detalhe=""):
    print(f"{'✅' if ok else '❌'} {titulo}" + (f"  ->  {detalhe}" if detalhe else ""))


produtos = pd.read_csv(coletor.ARQUIVO_PRODUTOS, sep=";", dtype=str)
item = produtos.iloc[0]
print(f"Pneu de teste: item {item['item']} · {item['medida']} {item['modelo']}\n")

# ---------- ROMA ----------
print("ROMA")
url_roma = item.get("url_roma")
if isinstance(url_roma, str) and url_roma.startswith("http"):
    api = coletor.roma_por_api(url_roma)
    mostrar(api is not None, "Preço pela API do Magento", api)
    html = coletor.roma_por_html(url_roma)
    mostrar(html is not None, "Preço pelo HTML da página", html)
    if api is None and html is None:
        print("   O painel vai usar o preço da planilha para a Roma.")
else:
    mostrar(False, "Link da Roma", "sem url_roma na planilha")

# ---------- PNEU STORE ----------
print("\nPNEU STORE")
ps = coletor.extrair_pneustore(item["url_pneustore"])
mostrar(ps["conc_preco_pix"] is not None or ps["conc_disponivel"] == "nao", "Preço da página", ps)
tabela = parcelas.tabela_pneustore(item["url_pneustore"], mostrar_resposta=True)
mostrar(bool(tabela), "Tabela real de parcelas (1x a 12x)",
        f"{len(tabela)} parcelas, 1x = R$ {tabela[0]['total']}" if tabela else
        "vai usar a fórmula; o NEXT_ACTION do parcelas.py pode ter mudado")
banners = campanhas.banners_pneustore()
mostrar(len(banners) > 0, "Banners da página inicial",
        f"{len(banners)} banner(s). Ex.: {banners[0]['titulo'][:60]}" if banners else "nenhum banner lido")

# ---------- ACHEI PNEUS ----------
print("\nACHEI PNEUS")
ac = coletor.extrair_acheipneus(item["sku_acheipneus"])
mostrar(ac["conc_preco_pix"] is not None or ac["conc_disponivel"] == "nao", "Preço pela API", ac)
tabela = parcelas.tabela_achei(item["sku_acheipneus"])
mostrar(bool(tabela), "Tabela real de parcelas pela API",
        f"{len(tabela)} parcelas" if tabela else "vai usar a fórmula (que já confere com o site)")
camp = campanhas.campanhas_achei({})
mostrar(len(camp) > 0, "Categorias de campanha", f"{len(camp)} encontrada(s)" if camp else "nenhuma")

print("\nSe algo aparecer com ❌, copie esta tela e mande para análise.")
