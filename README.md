# Transcrever 🎙️➡️📝

![Transcrever Logo](https://img.shields.io/badge/Transcrever-1.0-4361ee?style=for-the-badge)
[![Python](https://img.shields.io/badge/Python-3.7+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Whisper](https://img.shields.io/badge/OpenAI-Whisper-4CAF50?style=for-the-badge&logo=openai&logoColor=white)](https://github.com/openai/whisper)
[![Vercel](https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://vercel.com/)

**Transcrever** é uma aplicação web para conversão de arquivos de áudio e vídeo em texto, utilizando a tecnologia avançada de reconhecimento de fala OpenAI Whisper. Com uma interface amigável e intuitiva, o Transcrever permite transcrever seus arquivos de mídia em diversas línguas com alta precisão.

## 🌟 Funcionalidades

- 🎯 **Transcrição Precisa**: Converte áudio/vídeo em texto com alta precisão
- 🌎 **Detecção Automática de Idioma**: Identifica automaticamente o idioma do áudio
- 🗣️ **Suporte Multi-idioma**: Opção para selecionar manualmente o idioma da transcrição
- 🎛️ **Modelos de Diferentes Tamanhos**: Escolha entre diferentes modelos Whisper conforme sua necessidade de precisão e desempenho
- 📁 **Suporte a Múltiplos Formatos**: Processa vários formatos de áudio e vídeo (MP3, WAV, MP4, MOV, AVI, MKV, WMV, TS, etc.)
- 📋 **Interface Intuitiva**: Layout de duas colunas para fácil visualização de configurações e resultados
- 🖥️ **Design Responsivo**: Funciona bem em dispositivos móveis e desktops
- 📊 **Feedback em Tempo Real**: Barra de progresso para acompanhar o status da transcrição
- 🧹 **Limpeza Automática**: Remove arquivos temporários após 10 minutos para economizar espaço

## 🔧 Requisitos do Sistema

Para ambiente de desenvolvimento:
- Python 3.7 ou superior
- FFmpeg (para processamento de arquivos de vídeo)
- Dependências Python (listadas em `requirements.txt`)

Para produção (Vercel):
- Conta na Vercel
- Vercel CLI (opcional, para testes locais)
- Configuração do buildpack Python da Vercel

## 🚀 Instalação Local

1. Clone o repositório:
   ```bash
   git clone https://github.com/seu-usuario/transcrever.git
   cd transcrever
   ```

2. Crie e ative um ambiente virtual (recomendado):
   ```bash
   python -m venv venv
   
   # No Windows
   venv\Scripts\activate
   
   # No macOS/Linux
   source venv/bin/activate
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Instale o FFmpeg (necessário para processamento de vídeo):
   - **Windows**: Baixe do [site oficial](https://ffmpeg.org/download.html) e adicione ao PATH, ou use o Chocolatey:
     ```
     choco install ffmpeg
     ```
   - **macOS**:
     ```
     brew install ffmpeg
     ```
   - **Linux**:
     ```
     sudo apt update && sudo apt install ffmpeg
     ```

## 🎮 Como Executar Localmente

1. Inicie a aplicação:
   ```bash
   python app.py
   ```

2. Acesse a interface web em: http://127.0.0.1:5000

3. Uso da interface:
   - Arraste e solte ou selecione um arquivo de áudio/vídeo
   - Escolha o modelo de transcrição (base, small, medium, large)
   - Selecione o modo de idioma (automático ou específico)
   - Clique em "Transcrever"
   - Acompanhe o progresso da transcrição
   - Copie o resultado ou use conforme necessário

## 🌐 Deploy na Vercel

O Transcrever pode ser facilmente implantado na Vercel para disponibilizá-lo na nuvem:

1. Certifique-se de ter uma conta na [Vercel](https://vercel.com/)

2. Instale a Vercel CLI (opcional):
   ```bash
   npm install -g vercel
   ```

3. Faça login na Vercel:
   ```bash
   vercel login
   ```

4. Deploy básico pelo CLI:
   ```bash
   vercel
   ```

### Alternativa: Deploy via GitHub

1. Faça fork deste repositório para sua conta GitHub
2. Acesse o [Dashboard da Vercel](https://vercel.com/dashboard)
3. Clique em "New Project"
4. Selecione o repositório fork
5. Mantenha as configurações padrão (o vercel.json já está configurado)
6. Clique em "Deploy"

### ⚠️ Limitações do Deploy na Vercel

Por favor, esteja ciente das seguintes limitações ao usar a versão hospedada na Vercel:

1. **Tempo de Execução**: A Vercel tem um limite de execução de 10 segundos para funções serverless no plano gratuito, o que pode não ser suficiente para transcrições de arquivos grandes.

2. **Tamanho dos Arquivos**: Existe um limite de 4.5MB para upload de arquivos no plano gratuito da Vercel.

3. **Armazenamento Temporário**: Os arquivos são armazenados temporariamente e são excluídos automaticamente a cada nova execução da função serverless.

4. **Memória Limitada**: Pode haver problemas de memória ao utilizar modelos maiores (medium/large) para transcrição.

Para casos de uso mais intensivos, considere hospedar em um servidor dedicado ou serviço cloud como AWS, Google Cloud ou Azure.

## 📋 Formatos Suportados

### Áudio
- MP3 (.mp3)
- WAV (.wav)
- M4A (.m4a)
- OGG (.ogg)
- FLAC (.flac)

### Vídeo
- MP4 (.mp4)
- MOV (.mov)
- AVI (.avi)
- MKV (.mkv)
- WMV (.wmv)
- TS (.ts) - Transport Stream

## 🌐 Modelos Disponíveis

| Modelo | Descrição | Uso Recomendado |
|--------|-----------|-----------------|
| Base | Rápido, menor precisão | Textos simples, pouca interferência de ruído |
| Small | Equilíbrio entre velocidade e precisão | Uso geral |
| Medium | Boa precisão | Transcrições mais importantes, áudio com ruído moderado |
| Large | Alta precisão | Transcrições profissionais, áudio com muito ruído ou sotaques difíceis |

## 📊 Desempenho

O tempo de transcrição varia conforme:
- Tamanho do arquivo de áudio/vídeo
- Modelo escolhido
- Hardware do seu computador
- Complexidade do áudio (múltiplos falantes, ruído de fundo, etc.)

## 🛠️ Arquitetura do Projeto

```
transcrever/
├── app.py                # Aplicação Flask principal
├── wsgi.py               # Ponto de entrada para Vercel/WSGI
├── vercel.json           # Configuração de deploy na Vercel
├── requirements.txt      # Dependências Python
├── README.md             # Este documento
├── templates/            # Templates HTML
│   └── index.html        # Interface do usuário
└── uploads/              # Pasta para arquivos temporários (apenas dev)
```

## 🔍 Solução de Problemas

| Problema | Solução |
|----------|---------|
| FFmpeg não encontrado | Verifique se o FFmpeg está instalado e no PATH do sistema |
| Erro na transcrição | Verifique se o arquivo de áudio contém fala audível e não está corrompido |
| Memória insuficiente | Tente usar um modelo menor ou reduzir o tamanho do arquivo de áudio |
| Erro ao processar vídeo | Verifique se o formato do vídeo é suportado pelo FFmpeg |
| Timeout na Vercel | Os arquivos grandes podem exceder o limite de tempo de execução. Considere reduzir o tamanho do arquivo ou hospedar em outra plataforma |

## 📜 Licença

Este projeto está licenciado sob a [MIT License](LICENSE).

## 📧 Contato

Para sugestões, dúvidas ou feedback:
- **E-mail**: exemplo@email.com
- **GitHub Issues**: [Criar um novo issue](https://github.com/seu-usuario/transcrever/issues)

---

Desenvolvido com ❤️ usando tecnologia OpenAI Whisper 