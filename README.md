# TranscreveAI

TranscreveAI é uma aplicação web moderna para transcrição de áudio e vídeo utilizando IA. O projeto utiliza o modelo Whisper da OpenAI para fornecer transcrições precisas em múltiplos idiomas.

## Funcionalidades

- 🎵 Transcrição de arquivos de áudio (MP3, WAV, OGG)
- 🎥 Transcrição de arquivos de vídeo (MP4, AVI, MOV)
- 📺 Transcrição direta de vídeos do YouTube
- 🌍 Suporte a múltiplos idiomas
- 📝 Edição de transcrições em tempo real
- 💾 Download em diversos formatos (TXT, SRT, VTT, DOCX)
- 🎨 Interface moderna e responsiva
- 🌓 Suporte a modo escuro

## Requisitos

- Python 3.8 ou superior
- FFmpeg (para processamento de áudio/vídeo)
- Redis (opcional, para processamento em fila)

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/transcreve-ai.git
cd transcreve-ai
```

2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. Inicialize o banco de dados:
```bash
flask db upgrade
```

## Executando o Projeto

### Usando os Scripts de Inicialização (Recomendado)

A aplicação está configurada para ser executada na porta 3000. Use os scripts fornecidos para iniciar facilmente:

#### Windows:
```
start.bat
```

#### Linux/Mac:
```bash
# Primeiro, torne o script executável
chmod +x start.sh
# Execute o script
./start.sh
```

A aplicação estará disponível em `http://localhost:3000`.

### Método Alternativo

1. Inicie o servidor de desenvolvimento:
```bash
flask run --port=3000
```

2. (Opcional) Inicie o worker do Celery para processamento em background:
```bash
celery -A app.celery worker --loglevel=info
```

## Configuração do Ambiente de Produção

### Usando Docker

1. Construa a imagem:
```bash
docker build -t transcreve-ai .
```

2. Execute o container expondo a porta 3000:
```bash
docker run -d -p 3000:3000 transcreve-ai
```

### Deploy Manual

1. Configure um servidor web (Nginx/Apache) para redirecionar para a porta 3000
2. Configure o Gunicorn:
```bash
gunicorn -w 4 -b 127.0.0.1:3000 wsgi:app
```

## Estrutura do Projeto

```
transcreve-ai/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── static/
│   └── templates/
├── migrations/
├── tests/
├── .env.example
├── config.py
├── requirements.txt
├── start.bat         # Script de inicialização para Windows
├── start.sh          # Script de inicialização para Linux/Mac
└── wsgi.py
```

## Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. Push para a branch (`git push origin feature/nova-feature`)
5. Crie um Pull Request

## Licença

Este projeto está licenciado sob a MIT License - veja o arquivo [LICENSE](LICENSE) para detalhes.

## Contato

- Email: seu-email@exemplo.com
- Website: https://transcreve.ai
- Twitter: [@transcreve_ai](https://twitter.com/transcreve_ai)

## Agradecimentos

- [OpenAI Whisper](https://github.com/openai/whisper)
- [Flask](https://flask.palletsprojects.com/)
- [Celery](https://docs.celeryproject.org/)
- Todos os contribuidores do projeto 