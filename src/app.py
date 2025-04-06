from flask import Flask, request, jsonify, render_template, send_from_directory, session
import os
import uuid
import shutil
import threading
import time
import json
import logging
from datetime import datetime
import tempfile
from pathlib import Path
import apscheduler
from apscheduler.schedulers.background import BackgroundScheduler

# Importar módulos da aplicação
from .config.config import Config
from .utils.logger import logger, error_logger, transcription_logger
from .database.models import init_db, get_session, Transcription, User
from .services.transcription_service import transcription_manager
from .services.youtube_service import YouTubeService
from .api.routes import api_bp

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = Config.UPLOAD_DIR
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# Registrar blueprint da API
app.register_blueprint(api_bp)

# Inicializar banco de dados
try:
    init_db()
    logger.info("Banco de dados inicializado com sucesso")
except Exception as e:
    error_logger.error(f"Erro ao inicializar banco de dados: {str(e)}")

# Scheduler para tarefas recorrentes
scheduler = BackgroundScheduler()

@scheduler.scheduled_job('interval', minutes=30)
def cleanup_old_files():
    """Remove arquivos temporários antigos"""
    try:
        # Limpar arquivos de upload
        now = datetime.now()
        upload_dir = Config.UPLOAD_DIR
        count = 0
        
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            if os.path.isfile(file_path):
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                if (now - file_modified).total_seconds() > Config.FILE_EXPIRATION_MINUTES * 60:
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        error_logger.error(f"Erro ao excluir arquivo {file_path}: {str(e)}")
                        
        logger.info(f"Limpeza: {count} arquivo(s) temporário(s) removido(s)")
        
        # Limpar tarefas antigas da memória
        transcription_manager.cleanup_old_tasks(hours=24)
    except Exception as e:
        error_logger.error(f"Erro durante limpeza programada: {str(e)}")

# Iniciar o scheduler
try:
    scheduler.start()
    logger.info("Scheduler iniciado com sucesso")
except Exception as e:
    error_logger.error(f"Erro ao iniciar scheduler: {str(e)}")

@app.route('/')
def index():
    """Rota principal da aplicação"""
    # Verifica se existe pasta de uploads e PDFs
    os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(Config.PDF_DIR, exist_ok=True)
    
    # Obter informações dos modelos para exibir na interface
    models_info = transcription_manager.get_model_info()
    
    return render_template('index.html', 
                         app_name=Config.APP_NAME, 
                         app_version=Config.APP_VERSION,
                         models_info=models_info)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Rota para iniciar uma nova transcrição"""
    if 'file' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado."}), 400
    
    # Obter arquivo
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "Nenhum arquivo selecionado."}), 400
    
    # Obter parâmetros
    model_name = request.form.get('model', Config.DEFAULT_MODEL)
    language_mode = request.form.get('language_mode', 'auto')
    language = request.form.get('language', 'pt') if language_mode == 'specify' else None
    queue_mode = request.form.get('queue_mode', 'true') == 'true'
    
    # Obter formatos de exportação
    export_formats = request.form.get('export_formats', 'pdf')
    if export_formats:
        export_formats = export_formats.split(',')
    else:
        export_formats = ['pdf']
    
    # Validar o modelo
    if model_name not in Config.AVAILABLE_MODELS:
        return jsonify({"error": f"Modelo inválido. Escolha entre: {', '.join(Config.AVAILABLE_MODELS)}"}), 400
    
    # Validar o modo de idioma
    if language_mode not in ['auto', 'specify']:
        return jsonify({"error": "Modo de idioma inválido. Escolha entre 'auto' ou 'specify'."}), 400
    
    # Obter a extensão do arquivo
    filename = file.filename
    extension = os.path.splitext(filename)[1].lower()
    
    # Verificar se a extensão é suportada
    supported_audio = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    supported_video = ['.mp4', '.mov', '.avi', '.mkv', '.wmv', '.ts']
    
    if extension not in supported_audio + supported_video:
        return jsonify({"error": f"Formato de arquivo não suportado: {extension}. Use um dos formatos suportados."}), 400
    
    # Verificar se é um vídeo ou áudio
    is_video = extension in supported_video
    
    # Se for vídeo, verificar se o FFmpeg está instalado
    if is_video and not shutil.which("ffmpeg"):
        return jsonify({"error": "FFmpeg não está instalado. É necessário para processar arquivos de vídeo."}), 500
    
    # Salvar o arquivo com nome único
    unique_filename = str(uuid.uuid4()) + extension
    file_path = os.path.join(Config.UPLOAD_DIR, unique_filename)
    file.save(file_path)
    
    # Verificar tamanho do arquivo
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        os.remove(file_path)
        return jsonify({"error": "O arquivo enviado está vazio."}), 400
    
    # Obter ID do usuário da sessão, se existir
    user_id = session.get('user_id') if hasattr(session, 'get') else None
    
    # Adicionar tarefa ao gerenciador de transcrições
    try:
        task_id = transcription_manager.add_task(
            file_path=file_path,
            original_filename=filename,
            model_name=model_name,
            is_video=is_video,
            language_mode=language_mode,
            language=language,
            user_id=user_id,
            queue_mode=queue_mode,
            export_formats=export_formats
        )
        
        # Retornar o ID da tarefa para o cliente monitorar o progresso
        return jsonify({
            "task_id": task_id, 
            "queue_mode": queue_mode,
            "message": "Transcrição em fila" if queue_mode else "Transcrição iniciada"
        })
    except Exception as e:
        error_logger.error(f"Erro ao adicionar tarefa: {str(e)}")
        return jsonify({"error": f"Erro ao iniciar transcrição: {str(e)}"}), 500

@app.route('/progress/<task_id>')
def progress(task_id):
    """Rota para verificar o progresso de uma transcrição"""
    task = transcription_manager.get_task_status(task_id)
    
    if not task:
        return jsonify({"error": "Tarefa não encontrada"}), 404
    
    response = {
        "status": task.get("status", "unknown"),
        "progress": task.get("progress", 0),
        "step": task.get("step", ""),
        "queue_status": task.get("queue_status", "none")
    }
    
    # Adicionar informação de posição na fila, se disponível
    if "queue_position" in task:
        response["queue_position"] = task["queue_position"]
    
    # Adicionar estimativa de tempo, se disponível
    if "time_estimate" in task:
        response["time_estimate"] = task["time_estimate"]
        
        # Formatar o tempo restante
        seconds = task["time_estimate"]
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            formatted_time = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            formatted_time = f"{minutes}m {seconds}s"
        else:
            formatted_time = f"{seconds}s"
            
        response["formatted_time"] = formatted_time
    
    if task.get("status") == "completed":
        response["text"] = task.get("text", "")
        if "detected_language" in task:
            response["detected_language"] = task["detected_language"]
    elif task.get("status") == "error":
        response["error"] = task.get("error", "Erro desconhecido")
    
    return jsonify(response)

@app.route('/pdfs')
def list_pdfs():
    """Lista todos os PDFs gerados"""
    pdfs = []
    
    try:
        pdf_dir = Config.PDF_DIR
        if os.path.exists(pdf_dir):
            for filename in os.listdir(pdf_dir):
                if filename.endswith('.pdf'):
                    file_path = os.path.join(pdf_dir, filename)
                    file_stats = os.stat(file_path)
                    pdfs.append({
                        "filename": filename,
                        "size": file_stats.st_size,
                        "created_at": datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S')
                    })
    except Exception as e:
        error_logger.error(f"Erro ao listar PDFs: {str(e)}")
    
    return jsonify({"pdfs": pdfs})

@app.route('/pdfs/<filename>')
def download_pdf(filename):
    """Permite o download de um PDF específico"""
    return send_from_directory(Config.PDF_DIR, filename, as_attachment=True)

@app.route('/exports/<format>/<filename>')
def download_export(format, filename):
    """Permite o download de um arquivo exportado"""
    # Por segurança, validar o formato e o nome do arquivo
    if format not in Config.EXPORT_FORMATS:
        return jsonify({"error": "Formato inválido"}), 400
    
    if '..' in filename or '/' in filename:
        return jsonify({"error": "Nome de arquivo inválido"}), 400
    
    return send_from_directory(Config.PDF_DIR, filename, as_attachment=True)

@app.route('/queue_status')
def queue_status():
    """Retorna informações sobre o status da fila de processamento"""
    return jsonify(transcription_manager.get_queue_status())

@app.route('/transcriptions')
def list_transcriptions():
    """Lista as transcrições concluídas"""
    limit = int(request.args.get('limit', 10))
    user_id = session.get('user_id') if hasattr(session, 'get') else None
    
    transcriptions = transcription_manager.list_completed_transcriptions(limit, user_id)
    return jsonify({"transcriptions": transcriptions})

@app.route('/models')
def models_info():
    """Retorna informações sobre os modelos disponíveis"""
    return jsonify(transcription_manager.get_model_info())

@app.route('/settings', methods=['GET'])
def get_settings():
    """Retorna as configurações atuais"""
    settings = {
        "app_name": Config.APP_NAME,
        "app_version": Config.APP_VERSION,
        "default_model": Config.DEFAULT_MODEL,
        "default_theme": Config.DEFAULT_THEME,
        "max_concurrent_transcriptions": Config.MAX_CONCURRENT_TRANSCRIPTIONS,
        "available_models": Config.AVAILABLE_MODELS,
        "export_formats": Config.EXPORT_FORMATS
    }
    return jsonify(settings)

@app.route('/health')
def health_check():
    """Endpoint para verificação de saúde da aplicação"""
    return jsonify({
        "status": "online",
        "version": Config.APP_VERSION,
        "database": "connected" if get_session() is not None else "disconnected",
        "queue_size": transcription_manager.get_queue_status()["queue_size"],
        "active_tasks": transcription_manager.get_queue_status()["active_tasks"]
    })

@app.route('/transcribe_youtube', methods=['POST'])
def transcribe_youtube():
    """Rota para transcrever vídeo do YouTube a partir da URL"""
    data = request.get_json()
    
    if not data or 'youtube_url' not in data:
        return jsonify({"error": "URL do YouTube não fornecida."}), 400
    
    youtube_url = data['youtube_url']
    
    # Verificar se é uma URL válida do YouTube
    if not YouTubeService.is_valid_youtube_url(youtube_url):
        return jsonify({"error": "URL do YouTube inválida."}), 400
    
    # Obter parâmetros
    model_name = data.get('model', Config.DEFAULT_MODEL)
    language_mode = data.get('language_mode', 'auto')
    language = data.get('language', 'pt') if language_mode == 'specify' else None
    queue_mode = data.get('queue_mode', True)
    
    # Obter formatos de exportação
    export_formats = data.get('export_formats', 'pdf')
    if isinstance(export_formats, str):
        export_formats = export_formats.split(',')
    elif not isinstance(export_formats, list):
        export_formats = ['pdf']
    
    # Validar o modelo
    if model_name not in Config.AVAILABLE_MODELS:
        return jsonify({"error": f"Modelo inválido. Escolha entre: {', '.join(Config.AVAILABLE_MODELS)}"}), 400
    
    # Validar o modo de idioma
    if language_mode not in ['auto', 'specify']:
        return jsonify({"error": "Modo de idioma inválido. Escolha entre 'auto' ou 'specify'."}), 400
    
    # Baixar áudio do vídeo do YouTube
    logger.info(f"Iniciando download de áudio do YouTube: {youtube_url}")
    file_path, original_filename = YouTubeService.download_audio(youtube_url)
    
    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Falha ao baixar o áudio do vídeo do YouTube."}), 500
    
    # Verificar tamanho do arquivo
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        os.remove(file_path)
        return jsonify({"error": "O arquivo de áudio baixado está vazio."}), 400
    
    # Obter ID do usuário da sessão, se existir
    user_id = session.get('user_id') if hasattr(session, 'get') else None
    
    # Adicionar tarefa ao gerenciador de transcrições
    try:
        task_id = transcription_manager.add_task(
            file_path=file_path,
            original_filename=original_filename,
            model_name=model_name,
            is_video=False,  # Já foi convertido para áudio MP3
            language_mode=language_mode,
            language=language,
            user_id=user_id,
            queue_mode=queue_mode,
            export_formats=export_formats,
            source_type="youtube"
        )
        
        # Retornar o ID da tarefa para o cliente monitorar o progresso
        return jsonify({
            "task_id": task_id, 
            "queue_mode": queue_mode,
            "message": "Transcrição do vídeo do YouTube em fila" if queue_mode else "Transcrição do vídeo do YouTube iniciada"
        })
    except Exception as e:
        error_logger.error(f"Erro ao adicionar tarefa para YouTube: {str(e)}")
        # Limpar arquivo se ocorrer erro
        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({"error": f"Erro ao iniciar transcrição: {str(e)}"}), 500

@app.errorhandler(404)
def page_not_found(e):
    """Handler para páginas não encontradas"""
    return render_template('404.html', app_name=Config.APP_NAME), 404

@app.errorhandler(500)
def server_error(e):
    """Handler para erros de servidor"""
    error_logger.error(f"Erro 500: {str(e)}")
    return render_template('500.html', app_name=Config.APP_NAME), 500

def create_app():
    """Cria e configura a aplicação Flask"""
    return app

if __name__ == "__main__":
    app = create_app()
    
    # Verifica se o FFmpeg está instalado
    if not shutil.which("ffmpeg"):
        logger.warning("AVISO: FFmpeg não está instalado. A transcrição de arquivos de vídeo não funcionará.")
    
    # Inicia o servidor
    app.run(debug=Config.DEBUG) 