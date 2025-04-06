from flask import Blueprint, jsonify, request
from datetime import datetime
import os

from ..config.config import Config
from ..services.transcription_service import transcription_manager
from ..database.models import get_session, Transcription

# Definir blueprint da API
api_bp = Blueprint('api', __name__, url_prefix='/api/v1')

@api_bp.route('/health', methods=['GET'])
def health_check():
    """Verifica o status de saúde da API"""
    session = get_session()
    db_status = "connected" if session else "disconnected"
    session.close() if session else None
    
    return jsonify({
        "status": "online",
        "version": Config.APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "active_tasks": transcription_manager.get_queue_status()["active_tasks"],
        "queue_size": transcription_manager.get_queue_status()["queue_size"],
    })

@api_bp.route('/models', methods=['GET'])
def get_models():
    """Retorna informações sobre os modelos disponíveis"""
    return jsonify(transcription_manager.get_model_info())

@api_bp.route('/transcriptions', methods=['GET'])
def get_transcriptions():
    """Retorna uma lista das transcrições recentes"""
    limit = request.args.get('limit', default=10, type=int)
    user_id = request.args.get('user_id', default=None, type=int)
    
    transcriptions = transcription_manager.list_completed_transcriptions(limit, user_id)
    return jsonify({"transcriptions": transcriptions})

@api_bp.route('/transcriptions/<task_id>', methods=['GET'])
def get_transcription(task_id):
    """Retorna detalhes de uma transcrição específica pelo ID da tarefa"""
    task = transcription_manager.get_task_status(task_id)
    if not task:
        return jsonify({"error": "Transcrição não encontrada"}), 404
    
    return jsonify(task)

@api_bp.route('/queue', methods=['GET'])
def get_queue_status():
    """Retorna informações sobre o status da fila de processamento"""
    return jsonify(transcription_manager.get_queue_status())

@api_bp.route('/pdfs', methods=['GET'])
def get_pdfs():
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
                        "created_at": datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                        "download_url": f"/api/v1/pdfs/{filename}"
                    })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify({"pdfs": pdfs})

@api_bp.route('/settings', methods=['GET'])
def get_settings():
    """Retorna as configurações atuais da aplicação"""
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

# Documentação da API - Ajuda para desenvolvedores
@api_bp.route('/', methods=['GET'])
def api_documentation():
    """Retorna documentação básica da API"""
    endpoints = [
        {
            "path": "/api/v1/health",
            "method": "GET",
            "description": "Verifica o status de saúde da API",
            "parameters": []
        },
        {
            "path": "/api/v1/models",
            "method": "GET",
            "description": "Retorna informações sobre os modelos disponíveis",
            "parameters": []
        },
        {
            "path": "/api/v1/transcriptions",
            "method": "GET",
            "description": "Retorna uma lista das transcrições recentes",
            "parameters": [
                {"name": "limit", "type": "integer", "description": "Número máximo de transcrições a retornar (padrão: 10)"},
                {"name": "user_id", "type": "integer", "description": "Filtrar por ID de usuário (opcional)"}
            ]
        },
        {
            "path": "/api/v1/transcriptions/<task_id>",
            "method": "GET",
            "description": "Retorna detalhes de uma transcrição específica pelo ID da tarefa",
            "parameters": [
                {"name": "task_id", "type": "string", "description": "ID da tarefa de transcrição"}
            ]
        },
        {
            "path": "/api/v1/queue",
            "method": "GET",
            "description": "Retorna informações sobre o status da fila de processamento",
            "parameters": []
        },
        {
            "path": "/api/v1/pdfs",
            "method": "GET",
            "description": "Lista todos os PDFs gerados",
            "parameters": []
        },
        {
            "path": "/api/v1/settings",
            "method": "GET",
            "description": "Retorna as configurações atuais da aplicação",
            "parameters": []
        }
    ]
    
    return jsonify({
        "name": "Transcrever API",
        "version": Config.APP_VERSION,
        "description": "API para o aplicativo Transcrever de transcrição de áudio e vídeo",
        "endpoints": endpoints
    }) 