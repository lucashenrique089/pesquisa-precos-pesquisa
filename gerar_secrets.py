"""
GERA O TEXTO DO "SECRETS" DO STREAMLIT CLOUD | GA4 e Google Ads ao vivo na nuvem
==================================================================================
Para que serve: o painel online precisa da chave do robô do GA4 para consultar os dados
sozinho, sem você rodar o coletor. A chave NUNCA vai para o GitHub; ela fica guardada no
"cofre" do Streamlit Cloud (Settings > Secrets), que só o app consegue ler.

O que faz: lê a chave .json em C:\\chaves e escreve, na MESMA pasta C:\\chaves, o arquivo
secrets_streamlit.toml já no formato que o Streamlit pede. Assim você só copia e cola,
sem risco de errar as quebras de linha da private_key.

Como usar (uma vez só):
    python gerar_secrets.py
Depois: abra C:\\chaves\\secrets_streamlit.toml no Bloco de Notas, copie tudo e cole em
Streamlit Cloud > seu app > ⋮ > Settings > Secrets > Save.
"""

import json
import os

from ga4 import CHAVE

with open(CHAVE, encoding="utf-8") as arquivo:
    chave = json.load(arquivo)

# json.dumps escreve cada valor entre aspas e com os "\n" da private_key do jeito que o TOML aceita
linhas = ["[gcp_service_account]"] + [f"{campo} = {json.dumps(valor)}" for campo, valor in chave.items()]
destino = os.path.join(os.path.dirname(CHAVE), "secrets_streamlit.toml")
with open(destino, "w", encoding="utf-8") as arquivo:
    arquivo.write("\n".join(linhas) + "\n")

print(f"Pronto! Arquivo criado em {destino}")
print("Abra no Bloco de Notas, copie tudo e cole no Settings > Secrets do Streamlit Cloud.")
print("Ele fica FORA da pasta do projeto: não copie para cá nem suba no GitHub.")
