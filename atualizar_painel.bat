@echo off
REM ============================================================
REM ATUALIZA O PAINEL ONLINE EM UM CLIQUE | Roma Pneus
REM 1. Roda o coletor (precos, parcelas, campanhas, GA4 e vendas)
REM 2. Sobe os arquivos de dados para o GitHub
REM 3. O Streamlit Cloud percebe a mudanca e atualiza o painel sozinho
REM Pode ser agendado no Agendador de Tarefas do Windows (veja o LEIA-ME).
REM ============================================================
cd /d "%~dp0"
echo Coletando dados...
python coletor.py
if errorlevel 1 (
  echo O coletor deu erro. Nada foi enviado ao GitHub.
  pause
  exit /b 1
)
echo Enviando para o GitHub...
git add *.csv *.xlsx
git commit -m "Coleta automatica %date% %time%"
git push
echo Pronto! O painel online atualiza em 1 a 2 minutos.
timeout /t 10
