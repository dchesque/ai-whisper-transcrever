from flask import Flask, request, jsonify, render_template, send_from_directory
import whisper
import os
import subprocess
import uuid
import shutil
import threading
import time
import json
from datetime import datetime, timedelta
import tempfile
from pathlib import Path
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Dicionário para armazenar o estado das tarefas de transcrição (em memória)
# Nota: em ambiente serverless, isso será reiniciado a cada invocação
tasks = {}

# Configuração da pasta de arquivos temporários
# No ambiente serverless, usamos a pasta /tmp que é a única com permissão de escrita
if os.environ.get('VERCEL_ENV'):
    # Estamos na Vercel
    TEMP_DIR = '/tmp'
    logger.info("Executando na Vercel, usando diretório temporário: /tmp")
else:
    # Ambiente de desenvolvimento
    TEMP_DIR = 'uploads'
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    logger.info(f"Executando em ambiente de desenvolvimento, usando diretório: {TEMP_DIR}")

# Tempo de expiração dos arquivos (10 minutos)
FILE_EXPIRATION_MINUTES = 10

# Verifica se o FFmpeg está instalado
def is_ffmpeg_installed():
    return shutil.which("ffmpeg") is not None

# Dicionário de modelos disponíveis
models = {}

# Lista de passos da transcrição
STEPS = {
    "UPLOAD": "Arquivo recebido",
    "EXTRACT": "Extraindo áudio do vídeo",
    "VALIDATE": "Validando arquivo de áudio",
    "LOAD_MODEL": "Carregando modelo",
    "TRANSCRIBE": "Transcrevendo áudio",
    "FINISH": "Finalizando transcrição"
}

# Função para limpar arquivos mais antigos que FILE_EXPIRATION_MINUTES
def cleanup_old_files(directory):
    """Remove arquivos com mais de FILE_EXPIRATION_MINUTES do diretório especificado"""
    current_time = datetime.now()
    count = 0
    
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            # Verificar se é um arquivo (não um diretório)
            if os.path.isfile(file_path):
                # Obter o timestamp de modificação do arquivo
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                # Se o arquivo for mais antigo que o tempo de expiração
                if current_time - file_modified > timedelta(minutes=FILE_EXPIRATION_MINUTES):
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        logger.error(f"Erro ao excluir arquivo {file_path}: {str(e)}")
        
        if count > 0:
            logger.info(f"Limpeza: {count} arquivo(s) removido(s) de {directory}")
    except Exception as e:
        logger.error(f"Erro durante a limpeza de arquivos em {directory}: {str(e)}")

def update_task_progress(task_id, progress, step=None, status="processing"):
    """Atualiza o progresso de uma tarefa"""
    if task_id in tasks:
        tasks[task_id]["progress"] = progress
        if step:
            tasks[task_id]["step"] = step
        tasks[task_id]["status"] = status
        tasks[task_id]["updated_at"] = datetime.now().timestamp()
        
def update_task_result(task_id, text=None, detected_language=None, error=None):
    """Atualiza o resultado de uma tarefa"""
    if task_id in tasks:
        if error:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = error
        else:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["text"] = text
            if detected_language:
                tasks[task_id]["detected_language"] = detected_language
        tasks[task_id]["updated_at"] = datetime.now().timestamp()

def is_valid_audio_file(file_path):
    """Verifica se o arquivo de áudio é válido usando ffmpeg"""
    try:
        # Executar ffprobe para verificar se o arquivo de áudio é válido
        command = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "json", file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        
        # Verificar se a duração está disponível e é maior que 0
        if "format" in output and "duration" in output["format"]:
            duration = float(output["format"]["duration"])
            return duration > 0
    except Exception as e:
        logger.error(f"Erro ao validar arquivo de áudio: {str(e)}")
        return False
    
    return False

def transcribe_task(task_id, file_path, model_name, is_video, language_mode, language=None, audio_path=None):
    """Função executada em thread para processar a transcrição"""
    try:
        # Se é um vídeo, extrai o áudio
        if is_video:
            update_task_progress(task_id, 10, STEPS["EXTRACT"])
            
            # Comando melhorado do FFmpeg para extrair o áudio
            command = [
                "ffmpeg", "-i", file_path,
                "-vn",  # desabilita a saída de vídeo
                "-acodec", "pcm_s16le",  # converte para WAV
                "-ar", "16000",  # taxa de amostragem para 16kHz (melhor para Whisper)
                "-ac", "1",  # mono (melhor para reconhecimento de fala)
                "-y",  # sobrescreve se existir
                audio_path
            ]
            
            try:
                subprocess.run(command, check=True, capture_output=True)
                update_task_progress(task_id, 25, STEPS["EXTRACT"])
                file_to_transcribe = audio_path
            except subprocess.CalledProcessError as e:
                error_msg = e.stderr.decode() if e.stderr else str(e)
                update_task_result(task_id, error=f"Erro ao extrair áudio: {error_msg}")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
                
            # Verifica se o arquivo de áudio é válido
            update_task_progress(task_id, 30, STEPS["VALIDATE"])
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                update_task_result(task_id, error="O arquivo de áudio extraído está vazio.")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
                
            if not is_valid_audio_file(audio_path):
                # Tenta extrair o áudio novamente com uma abordagem diferente para arquivos TS
                if file_path.lower().endswith('.ts'):
                    update_task_progress(task_id, 35, STEPS["EXTRACT"] + " (tentativa alternativa)")
                    try:
                        # Abordagem alternativa para arquivos TS
                        command = [
                            "ffmpeg", "-i", file_path,
                            "-map", "0:a:0",  # pega o primeiro stream de áudio
                            "-acodec", "pcm_s16le",
                            "-ar", "16000",
                            "-ac", "1",
                            "-y",
                            audio_path
                        ]
                        subprocess.run(command, check=True, capture_output=True)
                        
                        if not is_valid_audio_file(audio_path):
                            update_task_result(task_id, error="Não foi possível extrair áudio válido do arquivo.")
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            return
                    except subprocess.CalledProcessError as e:
                        error_msg = e.stderr.decode() if e.stderr else str(e)
                        update_task_result(task_id, error=f"Erro ao extrair áudio (segunda tentativa): {error_msg}")
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        return
                else:
                    update_task_result(task_id, error="O arquivo de áudio extraído não é válido.")
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
        else:
            update_task_progress(task_id, 20, STEPS["UPLOAD"])
            file_to_transcribe = file_path
            
            # Verificar se o arquivo de áudio direto é válido
            update_task_progress(task_id, 30, STEPS["VALIDATE"])
            if not is_valid_audio_file(file_to_transcribe):
                update_task_result(task_id, error="O arquivo de áudio fornecido não é válido.")
                if os.path.exists(file_path):
                    os.remove(file_path)
                return
        
        # Carrega o modelo, se ainda não estiver carregado
        update_task_progress(task_id, 40, STEPS["LOAD_MODEL"])
        
        if model_name not in models:
            try:
                models[model_name] = whisper.load_model(model_name)
            except Exception as e:
                update_task_result(task_id, error=f"Erro ao carregar o modelo {model_name}: {str(e)}")
                return
        
        model = models[model_name]
        update_task_progress(task_id, 50, STEPS["TRANSCRIBE"])
        
        # Transcreve o áudio
        try:
            # Verificar tamanho do arquivo antes da transcrição
            file_size = os.path.getsize(file_to_transcribe)
            if file_size == 0:
                update_task_result(task_id, error="O arquivo de áudio está vazio e não pode ser transcrito.")
                return
            
            # Determinar os parâmetros de transcrição baseados no modo de idioma
            transcribe_params = {}
            
            # Sempre usar task=transcribe para garantir que o resultado seja no idioma original (sem tradução)
            transcribe_params["task"] = "transcribe"
            
            # Configurar o idioma baseado no modo selecionado
            if language_mode == "auto":
                # Primeiro detectar o idioma se estiver no modo automático
                update_task_progress(task_id, 55, "Detectando idioma...")
                audio = whisper.load_audio(file_to_transcribe)
                audio = whisper.pad_or_trim(audio)
                mel = whisper.log_mel_spectrogram(audio).to(model.device)
                _, probs = model.detect_language(mel)
                detected_language = max(probs, key=probs.get)
                logger.info(f"Idioma detectado: {detected_language} (confiança: {probs[detected_language]:.2%})")
                
                # Usar o idioma detectado
                transcribe_params["language"] = detected_language
                update_task_progress(task_id, 60, f"Idioma detectado: {detected_language}")
            else:
                # Usar o idioma especificado pelo usuário
                transcribe_params["language"] = language
                update_task_progress(task_id, 60, f"Usando idioma: {language}")
            
            # Realizar a transcrição com os parâmetros configurados
            result = model.transcribe(file_to_transcribe, **transcribe_params)
            text = result["text"]
            detected_language = result.get("language", "desconhecido")
            
            # Simula progresso gradual (na prática, seria bom ter feedback real do processo)
            for progress in range(65, 95, 5):
                time.sleep(0.2)  # Simula o tempo de processamento
                update_task_progress(task_id, progress, STEPS["TRANSCRIBE"])
                
            update_task_progress(task_id, 95, STEPS["FINISH"])
            update_task_result(task_id, text=text, detected_language=detected_language)
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {str(e)}")
            update_task_result(task_id, error=f"Erro na transcrição: {str(e)}")
        
    finally:
        # Remove os arquivos temporários
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            if is_video and audio_path and os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as e:
            logger.error(f"Erro ao remover arquivos temporários: {str(e)}")

@app.route('/')
def index():
    # Aproveita cada requisição para fazer limpeza de arquivos antigos
    try:
        cleanup_old_files(TEMP_DIR)
    except Exception as e:
        logger.error(f"Erro ao limpar arquivos antigos: {str(e)}")
        
    return render_template('index.html')

@app.route('/progress/<task_id>')
def progress(task_id):
    """Rota para verificar o progresso de uma transcrição"""
    if task_id not in tasks:
        return jsonify({"error": "Tarefa não encontrada"}), 404
    
    task = tasks[task_id]
    
    # Verifica se a tarefa está ativa há mais de 10 minutos
    now = datetime.now().timestamp()
    if now - task["updated_at"] > 600 and task["status"] == "processing":
        task["status"] = "error"
        task["error"] = "Tempo limite excedido"
    
    response = {
        "status": task["status"],
        "progress": task["progress"],
        "step": task.get("step", "")
    }
    
    if task["status"] == "completed":
        response["text"] = task["text"]
        if "detected_language" in task:
            response["detected_language"] = task["detected_language"]
    elif task["status"] == "error":
        response["error"] = task["error"]
    
    return jsonify(response)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado."}), 400
    
    # Limpa arquivos antigos a cada requisição
    try:
        cleanup_old_files(TEMP_DIR)
    except Exception as e:
        logger.error(f"Erro ao limpar arquivos antigos: {str(e)}")
    
    file = request.files['file']
    model_name = request.form.get('model', 'base')
    language_mode = request.form.get('language_mode', 'auto')
    language = request.form.get('language', 'pt') if language_mode == 'specify' else None
    
    # Valida o modelo
    if model_name not in ['base', 'small', 'medium', 'large']:
        return jsonify({"error": "Modelo inválido. Escolha entre 'base', 'small', 'medium' ou 'large'."}), 400
    
    # Valida o modo de idioma
    if language_mode not in ['auto', 'specify']:
        return jsonify({"error": "Modo de idioma inválido. Escolha entre 'auto' ou 'specify'."}), 400
    
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado."}), 400
    
    # Obtém a extensão do arquivo
    filename = file.filename
    extension = os.path.splitext(filename)[1].lower()
    
    # Verificar se a extensão é suportada
    supported_audio = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    supported_video = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.ts']
    
    if extension not in supported_audio + supported_video:
        return jsonify({"error": f"Formato de arquivo não suportado: {extension}. Use um dos formatos suportados."}), 400
    
    # Gera um ID único para a tarefa
    task_id = str(uuid.uuid4())
    
    # Inicializa o estado da tarefa
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "step": STEPS["UPLOAD"],
        "created_at": datetime.now().timestamp(),
        "updated_at": datetime.now().timestamp()
    }
    
    # Salva o arquivo enviado com um nome único
    unique_filename = str(uuid.uuid4()) + extension
    input_path = os.path.join(TEMP_DIR, unique_filename)
    file.save(input_path)
    
    # Verifica o tamanho do arquivo
    file_size = os.path.getsize(input_path)
    if file_size == 0:
        os.remove(input_path)
        return jsonify({"error": "O arquivo enviado está vazio."}), 400
    
    # Verifica se o arquivo é um vídeo ou áudio
    is_video = extension in supported_video
    
    # Se for vídeo, verifica se o FFmpeg está instalado
    if is_video:
        if not is_ffmpeg_installed():
            os.remove(input_path)
            return jsonify({"error": "FFmpeg não está instalado. É necessário para processar arquivos de vídeo."}), 500
        
        # Gera um nome único para o arquivo de áudio extraído
        audio_filename = str(uuid.uuid4()) + ".wav"
        audio_path = os.path.join(TEMP_DIR, audio_filename)
    else:
        audio_path = None
    
    # Inicia uma thread para processar a transcrição
    thread = threading.Thread(
        target=transcribe_task,
        args=(task_id, input_path, model_name, is_video, language_mode, language, audio_path)
    )
    thread.daemon = True
    thread.start()
    
    # Retorna o ID da tarefa para o cliente monitorar o progresso
    return jsonify({"task_id": task_id})

# Inicia carregando o modelo base por padrão
try:
    models["base"] = whisper.load_model("base")
    logger.info("Modelo base carregado com sucesso!")
except Exception as e:
    logger.error(f"Erro ao carregar o modelo base: {str(e)}")

if __name__ == "__main__":
    # Verifica se o FFmpeg está instalado
    if not is_ffmpeg_installed():
        logger.warning("AVISO: FFmpeg não está instalado. A transcrição de arquivos de vídeo não funcionará.")
    
    # Informa sobre a configuração
    logger.info(f"Tempo de expiração dos arquivos: {FILE_EXPIRATION_MINUTES} minutos")
    logger.info(f"Diretório temporário: {TEMP_DIR}")
    
    # Inicia o servidor
    app.run(debug=True)
