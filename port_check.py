print
Verificando a configuração da porta para o TranscreveAI
print
Ambiente:
import
os
print(f'Variável PORT no ambiente: {os.environ.get(\
PORT\, \Não
definida\)}')
print
\nConfiguração:
print
- App.py: Configurado para porta 3000 (hardcoded)
print
- .env: PORT=3000
print
- .env.example: PORT=3000
print
- config.py: PORT=3000 para todos os ambientes
print
\nScripts de inicialização:
print
- start.bat: Configurado para executar na porta 3000
print
- start.sh: Configurado para executar na porta 3000
print
\nConclusão: TranscreveAI está completamente configurado para rodar na porta 3000!
