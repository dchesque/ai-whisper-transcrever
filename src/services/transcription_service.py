import whisper
import os
import time
import threading
import uuid
import json
import subprocess
import queue
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from ..config.config import Config
from ..utils.logger import logger, error_logger, transcription_logger, log_transcription_stats
from ..database.models import get_session, Transcription, TranscriptionLog
from ..utils.exporters import save_to_pdf, save_to_txt, save_to_srt, save_to_docx

class TranscriptionManager:
    """
    Gerenciador de transcrições com suporte a múltiplas transcrições simultâneas
    e gerenciamento de fila
    """
    
    def __init__(self):
        # Dicionário para armazenar o estado das tarefas em andamento
        self.tasks = {}
        
        # Fila de tarefas pendentes
        self.task_queue = queue.Queue()
        
        # Thread pool para executar transcrições simultaneamente
        self.executor = ThreadPoolExecutor(max_workers=Config.MAX_CONCURRENT_TRANSCRIPTIONS)
        
        # Flag para controlar o processamento contínuo da fila
        self.is_queue_processing = False
        
        # Cache para modelos carregados
        self.models = {}
        
        # Iniciar o processamento da fila
        self.start_queue_processing()
        
        # Diretórios
        self.upload_dir = Config.get_upload_dir()
        self.pdf_dir = Config.get_pdf_dir()
        
        logger.info(f"TranscriptionManager inicializado com {Config.MAX_CONCURRENT_TRANSCRIPTIONS} workers")
    
    def start_queue_processing(self):
        """Inicia o processamento da fila em segundo plano"""
        if not self.is_queue_processing:
            self.is_queue_processing = True
            threading.Thread(target=self._process_queue, daemon=True).start()
            logger.info("Iniciado processamento da fila em segundo plano")
    
    def _process_queue(self):
        """Processa continuamente a fila de transcrições"""
        while self.is_queue_processing:
            # Verificar quantas tarefas estão sendo processadas atualmente
            active_tasks = sum(1 for task in self.tasks.values() 
                              if task.get("status") == "processing" and not task.get("queue_status"))
            
            # Se há espaço para mais tarefas, pegar da fila
            if active_tasks < Config.MAX_CONCURRENT_TRANSCRIPTIONS:
                try:
                    # Tentar pegar próxima tarefa da fila (sem bloquear)
                    task_info = self.task_queue.get_nowait()
                    task_id = task_info["task_id"]
                    
                    # Atualizar status da tarefa
                    if task_id in self.tasks:
                        self.tasks[task_id]["queue_status"] = "processing"
                        self.update_task_progress(task_id, 5, "Iniciando processamento")
                        
                        # Atualizar posição na fila para outras tarefas
                        self._update_queue_positions()
                        
                        # Iniciar processamento em um executor
                        self.executor.submit(
                            self._transcribe_task,
                            task_id=task_id,
                            file_path=task_info["input_path"],
                            model_name=task_info["model_name"],
                            is_video=task_info["is_video"],
                            language_mode=task_info["language_mode"],
                            language=task_info["language"],
                            audio_path=task_info["audio_path"],
                            original_filename=task_info["original_filename"],
                            export_formats=task_info.get("export_formats", ["pdf"]),
                            source_type=task_info.get("source_type", "upload")
                        )
                        
                        # Log
                        logger.info(f"Iniciando processamento da tarefa {task_id} da fila")
                        
                except queue.Empty:
                    # Nada na fila, esperar
                    pass
            
            # Dormir antes de verificar novamente
            time.sleep(0.5)
    
    def _update_queue_positions(self):
        """Atualiza a posição na fila para todas as tarefas em espera"""
        queued_tasks = [t_id for t_id, t in self.tasks.items() 
                        if t.get("queue_status") == "queued"]
        
        for i, task_id in enumerate(queued_tasks):
            self.tasks[task_id]["queue_position"] = f"{i + 1}/{len(queued_tasks)}"
    
    def add_task(self, file_path, original_filename, model_name, is_video, language_mode="auto", 
                language=None, user_id=None, queue_mode=True, export_formats=None, source_type=None):
        """
        Adiciona uma nova tarefa de transcrição
        
        Args:
            file_path: Caminho do arquivo a ser transcrito
            original_filename: Nome original do arquivo
            model_name: Nome do modelo whisper a ser usado
            is_video: Se o arquivo é um vídeo
            language_mode: 'auto' para detectar idioma ou 'specify' para usar language
            language: Código do idioma se language_mode='specify'
            user_id: ID do usuário (opcional)
            queue_mode: Se a tarefa deve ser enfileirada ou processada imediatamente
            export_formats: Lista de formatos para exportação (pdf, txt, srt, docx)
            source_type: Tipo de origem do arquivo (upload, youtube, etc.)
            
        Returns:
            task_id: ID da tarefa criada
        """
        # Gera um ID único para a tarefa
        task_id = str(uuid.uuid4())
        
        # Define formatos de exportação
        if export_formats is None:
            export_formats = ["pdf"]
            
        # Se o formato não for suportado, usar PDF como fallback
        export_formats = [fmt for fmt in export_formats if fmt in Config.EXPORT_FORMATS]
        if not export_formats:
            export_formats = ["pdf"]
        
        # Inicializa o estado da tarefa
        self.tasks[task_id] = {
            "status": "processing" if not queue_mode else "pending",
            "progress": 0,
            "step": "Inicializando",
            "created_at": datetime.now().timestamp(),
            "updated_at": datetime.now().timestamp(),
            "original_filename": original_filename,
            "user_id": user_id,
            "source_type": source_type or "upload"  # Indica a origem do arquivo
        }
        
        # Se for vídeo, precisamos extrair o áudio
        audio_path = None
        if is_video:
            # Gera um nome único para o arquivo de áudio extraído
            audio_filename = str(uuid.uuid4()) + ".wav"
            audio_path = os.path.join(self.upload_dir, audio_filename)
        
        # Criar registro no banco de dados
        try:
            db_session = get_session()
            db_transcription = Transcription(
                task_id=task_id,
                user_id=user_id,
                original_filename=original_filename,
                file_type="video" if is_video else "audio",
                model_used=model_name,
                language=language,
                status="pending" if queue_mode else "processing",
                started_at=None if queue_mode else datetime.utcnow(),
                source_type=source_type or "upload"  # Adiciona a fonte à tabela
            )
            db_session.add(db_transcription)
            db_session.commit()
            
            # Adicionar primeiro registro de log
            db_log = TranscriptionLog(
                transcription_id=db_transcription.id,
                status="pending" if queue_mode else "processing",
                progress=0,
                step="Adicionado à fila" if queue_mode else "Iniciando processamento",
                message=f"Tarefa criada para o arquivo {original_filename}"
            )
            db_session.add(db_log)
            db_session.commit()
            db_session.close()
        except Exception as e:
            error_logger.error(f"Erro ao criar registro de transcrição: {str(e)}")
        
        # Se estiver no modo fila, adiciona à fila de transcrição
        if queue_mode:
            self.tasks[task_id]["queue_status"] = "queued"
            self.tasks[task_id]["step"] = "Adicionado à fila de transcrição"
            
            # Adicionar à fila
            self.task_queue.put({
                "task_id": task_id,
                "input_path": file_path,
                "model_name": model_name,
                "is_video": is_video,
                "language_mode": language_mode,
                "language": language,
                "audio_path": audio_path,
                "original_filename": original_filename,
                "export_formats": export_formats,
                "source_type": source_type or "upload"
            })
            
            # Atualizar posições na fila
            self._update_queue_positions()
            
            logger.info(f"Arquivo '{original_filename}' adicionado à fila. Total na fila: {self.task_queue.qsize()}")
            
        else:
            # Iniciar processamento imediatamente
            self.executor.submit(
                self._transcribe_task,
                task_id=task_id,
                file_path=file_path,
                model_name=model_name,
                is_video=is_video,
                language_mode=language_mode,
                language=language,
                audio_path=audio_path,
                original_filename=original_filename,
                export_formats=export_formats,
                source_type=source_type or "upload"
            )
        
        return task_id
    
    def get_task_status(self, task_id):
        """Retorna o status atual de uma tarefa"""
        if task_id not in self.tasks:
            # Tentar recuperar do banco de dados
            try:
                db_session = get_session()
                db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                
                if db_task:
                    # Reconstruir estado da tarefa da versão em banco
                    self.tasks[task_id] = {
                        "status": db_task.status,
                        "progress": 100 if db_task.status == "completed" else 0,
                        "step": "Transcrição finalizada" if db_task.status == "completed" else "Status desconhecido",
                        "created_at": db_task.created_at.timestamp(),
                        "updated_at": db_task.updated_at.timestamp(),
                        "original_filename": db_task.original_filename
                    }
                    
                    if db_task.status == "completed":
                        self.tasks[task_id]["text"] = db_task.text_content
                        if db_task.detected_language:
                            self.tasks[task_id]["detected_language"] = db_task.detected_language
                    elif db_task.status == "error":
                        self.tasks[task_id]["error"] = db_task.error_message
                
                db_session.close()
            except Exception as e:
                error_logger.error(f"Erro ao recuperar status da tarefa {task_id} do banco: {str(e)}")
                return None
        
        if task_id in self.tasks:
            # Verificar timeout
            now = datetime.now().timestamp()
            if (now - self.tasks[task_id]["updated_at"] > Config.TASK_TIMEOUT_SECONDS and 
                self.tasks[task_id]["status"] == "processing"):
                self.tasks[task_id]["status"] = "error"
                self.tasks[task_id]["error"] = "Tempo limite excedido"
                
                # Atualizar no banco de dados
                try:
                    db_session = get_session()
                    db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                    if db_task:
                        db_task.status = "error"
                        db_task.error_message = "Tempo limite excedido"
                        db_session.commit()
                    db_session.close()
                except Exception as e:
                    error_logger.error(f"Erro ao atualizar timeout no banco: {str(e)}")
            
            return self.tasks[task_id]
        
        return None
    
    def update_task_progress(self, task_id, progress, step=None, status="processing", time_estimate=None):
        """Atualiza o progresso de uma tarefa"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            if step:
                self.tasks[task_id]["step"] = step
            self.tasks[task_id]["status"] = status
            self.tasks[task_id]["updated_at"] = datetime.now().timestamp()
            
            if time_estimate is not None:
                self.tasks[task_id]["time_estimate"] = time_estimate
            
            # Atualizar log no banco de dados
            try:
                db_session = get_session()
                db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                
                if db_task:
                    if status != db_task.status:
                        db_task.status = status
                    
                    # Adicionar log de progresso
                    db_log = TranscriptionLog(
                        transcription_id=db_task.id,
                        status=status,
                        progress=progress,
                        step=step or "",
                        message=f"Progresso atualizado para {progress}%"
                    )
                    db_session.add(db_log)
                    db_session.commit()
                
                db_session.close()
            except Exception as e:
                error_logger.error(f"Erro ao atualizar progresso no banco: {str(e)}")
    
    def update_task_result(self, task_id, text=None, detected_language=None, error=None, 
                          original_filename=None, export_formats=None, processing_duration=None):
        """Atualiza o resultado de uma tarefa"""
        if task_id in self.tasks:
            if error:
                self.tasks[task_id]["status"] = "error"
                self.tasks[task_id]["error"] = error
            else:
                self.tasks[task_id]["status"] = "completed"
                self.tasks[task_id]["text"] = text
                if detected_language:
                    self.tasks[task_id]["detected_language"] = detected_language
                
                # Exportar para os formatos solicitados
                if text and original_filename:
                    export_results = self._export_transcription(
                        text, original_filename, detected_language, export_formats
                    )
                    self.tasks[task_id]["export_results"] = export_results
            
            self.tasks[task_id]["updated_at"] = datetime.now().timestamp()
            if processing_duration:
                self.tasks[task_id]["processing_duration"] = processing_duration
            
            # Atualizar no banco de dados
            try:
                db_session = get_session()
                db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                
                if db_task:
                    # Atualizar status
                    db_task.status = "error" if error else "completed"
                    db_task.completed_at = datetime.utcnow()
                    
                    if error:
                        db_task.error_message = error
                    else:
                        db_task.text_content = text
                        db_task.detected_language = detected_language
                        
                        # Informações de exportação
                        if "export_results" in self.tasks[task_id]:
                            export_results = self.tasks[task_id]["export_results"]
                            if "pdf" in export_results:
                                db_task.pdf_filename = os.path.basename(export_results["pdf"])
                            
                            # Outros formatos como JSON
                            other_formats = {k: os.path.basename(v) 
                                           for k, v in export_results.items() 
                                           if k != "pdf"}
                            if other_formats:
                                db_task.other_formats = json.dumps(other_formats)
                    
                    # Duração do processamento
                    if processing_duration:
                        db_task.processing_duration = processing_duration
                    
                    # Log final
                    db_log = TranscriptionLog(
                        transcription_id=db_task.id,
                        status=db_task.status,
                        progress=100 if not error else 0,
                        step="Concluído" if not error else "Erro",
                        message="Transcrição concluída com sucesso" if not error else f"Erro: {error}"
                    )
                    db_session.add(db_log)
                    db_session.commit()
                
                db_session.close()
            except Exception as e:
                error_logger.error(f"Erro ao atualizar resultado no banco: {str(e)}")
    
    def _export_transcription(self, text, original_filename, language=None, export_formats=None):
        """
        Exporta a transcrição para vários formatos
        
        Args:
            text: Texto da transcrição
            original_filename: Nome original do arquivo
            language: Idioma detectado
            export_formats: Lista de formatos para exportação (pdf, txt, srt, docx)
            
        Returns:
            dict: Dicionário com caminhos dos arquivos gerados por formato
        """
        results = {}
        
        if export_formats is None:
            export_formats = ["pdf"]
        
        try:
            # Remover a extensão do arquivo original
            base_filename = os.path.splitext(os.path.basename(original_filename))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Exportar para cada formato
            for fmt in export_formats:
                if fmt == "pdf":
                    pdf_path = save_to_pdf(text, original_filename, language)
                    results["pdf"] = pdf_path
                
                elif fmt == "txt":
                    txt_path = save_to_txt(text, original_filename, language)
                    results["txt"] = txt_path
                
                elif fmt == "srt":
                    srt_path = save_to_srt(text, original_filename, language)
                    results["srt"] = srt_path
                
                elif fmt == "docx":
                    docx_path = save_to_docx(text, original_filename, language)
                    results["docx"] = docx_path
            
            return results
        except Exception as e:
            error_logger.error(f"Erro ao exportar transcrição: {str(e)}")
            return {"error": str(e)}
    
    def _transcribe_task(self, task_id, file_path, model_name, is_video, language_mode, 
                        language, audio_path, original_filename, export_formats=None, source_type=None):
        """Função executada em thread para processar a transcrição"""
        start_time = time.time()
        duration = None
        
        transcription_logger.info(f"Iniciando transcrição da tarefa {task_id} - {original_filename}")
        
        try:
            # Atualizar no banco de dados
            try:
                db_session = get_session()
                db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                if db_task and db_task.status != "processing":
                    db_task.status = "processing"
                    db_task.started_at = datetime.utcnow()
                    db_session.commit()
                db_session.close()
            except Exception as e:
                error_logger.error(f"Erro ao atualizar status inicial no banco: {str(e)}")
            
            # Se é um vídeo, extrai o áudio
            if is_video:
                self.update_task_progress(task_id, 10, "Extraindo áudio do vídeo")
                
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
                    self.update_task_progress(task_id, 25, "Áudio extraído com sucesso")
                    file_to_transcribe = audio_path
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode() if e.stderr else str(e)
                    self.update_task_result(task_id, error=f"Erro ao extrair áudio: {error_msg}")
                    
                    # Limpar arquivos
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                    
                # Verifica se o arquivo de áudio é válido utilizando uma função auxiliar
                self.update_task_progress(task_id, 30, "Validando arquivo de áudio")
                
                if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                    self.update_task_result(task_id, error="O arquivo de áudio extraído está vazio.")
                    
                    # Limpar arquivos
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    return
                
                # Verificação de validez do áudio extraído
                try:
                    # Usar ffprobe para verificar duração
                    command = [
                        "ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "json", audio_path
                    ]
                    result = subprocess.run(command, capture_output=True, text=True, check=True)
                    output = json.loads(result.stdout)
                    
                    if "format" not in output or "duration" not in output["format"]:
                        raise ValueError("Informação de duração não encontrada")
                        
                    audio_valid = True
                except Exception as e:
                    audio_valid = False
                    error_logger.error(f"Erro ao validar áudio: {str(e)}")
                
                if not audio_valid:
                    self.update_task_result(task_id, error="O arquivo de áudio extraído não é válido.")
                    
                    # Limpar arquivos
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                    return
            else:
                self.update_task_progress(task_id, 20, "Arquivo de áudio recebido")
                file_to_transcribe = file_path
            
            # Obter duração do áudio para estimativa de tempo
            try:
                command = [
                    "ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "json", file_to_transcribe
                ]
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                output = json.loads(result.stdout)
                
                if "format" in output and "duration" in output["format"]:
                    duration = float(output["format"]["duration"])
                    
                    # Estimar tempo de transcrição baseado na duração
                    factors = {
                        "base": 0.1,
                        "small": 0.15,
                        "medium": 0.3,
                        "large": 0.5
                    }
                    
                    # Tempo adicional para extração (se for vídeo)
                    video_extraction_time = 60 if is_video else 0  # 1 minuto para extração
                    
                    # Tempo para carregar o modelo
                    model_load_time = {
                        "base": 10,
                        "small": 20,
                        "medium": 40,
                        "large": 60
                    }
                    
                    # Calcular estimativa
                    processing_time = duration * factors.get(model_name, 0.2)
                    total_estimate = int(processing_time + video_extraction_time + model_load_time.get(model_name, 30))
                    
                    # Atualizar progresso com estimativa
                    self.update_task_progress(
                        task_id, 
                        35, 
                        f"Preparando transcrição de áudio de {self._format_time(duration)}", 
                        time_estimate=total_estimate
                    )
                    
                    # Atualizar duração no banco
                    try:
                        db_session = get_session()
                        db_task = db_session.query(Transcription).filter_by(task_id=task_id).first()
                        if db_task:
                            db_task.audio_duration = duration
                            db_session.commit()
                        db_session.close()
                    except Exception as e:
                        error_logger.error(f"Erro ao atualizar duração no banco: {str(e)}")
            except Exception as e:
                transcription_logger.warning(f"Não foi possível obter duração do áudio: {str(e)}")
            
            # Carregar modelo, com cache
            self.update_task_progress(task_id, 40, "Carregando modelo de transcrição")
            
            # Verificar se o modelo já está em cache
            if model_name not in self.models:
                try:
                    self.models[model_name] = whisper.load_model(model_name)
                    transcription_logger.info(f"Modelo {model_name} carregado com sucesso")
                except Exception as e:
                    self.update_task_result(task_id, error=f"Erro ao carregar o modelo {model_name}: {str(e)}")
                    return
            
            model = self.models[model_name]
            
            # Atualizar progresso antes da transcrição
            elapsed_time = time.time() - start_time
            if duration:
                time_remaining = max(0, total_estimate - elapsed_time)
                self.update_task_progress(
                    task_id, 
                    50, 
                    f"Transcrevendo áudio (tempo restante: {self._format_time(time_remaining)})",
                    time_estimate=time_remaining
                )
            else:
                self.update_task_progress(task_id, 50, "Transcrevendo áudio")
            
            # Detectar idioma se necessário
            detected_language = None
            if language_mode == "auto":
                try:
                    self.update_task_progress(task_id, 55, "Detectando idioma...")
                    audio = whisper.load_audio(file_to_transcribe)
                    audio = whisper.pad_or_trim(audio)
                    mel = whisper.log_mel_spectrogram(audio).to(model.device)
                    _, probs = model.detect_language(mel)
                    detected_language = max(probs, key=probs.get)
                    
                    transcription_logger.info(f"Idioma detectado: {detected_language} (confiança: {probs[detected_language]:.2%})")
                    
                    # Atualizar progresso
                    elapsed_time = time.time() - start_time
                    if duration:
                        time_remaining = max(0, total_estimate - elapsed_time)
                        self.update_task_progress(
                            task_id, 
                            60, 
                            f"Idioma detectado: {detected_language} (tempo restante: {self._format_time(time_remaining)})",
                            time_estimate=time_remaining
                        )
                    else:
                        self.update_task_progress(task_id, 60, f"Idioma detectado: {detected_language}")
                    
                except Exception as e:
                    transcription_logger.error(f"Erro ao detectar idioma: {str(e)}")
                    detected_language = "pt"  # Fallback para português
            
            # Transcrever áudio
            transcription_start_time = time.time()
            try:
                # Configurar parâmetros
                transcribe_params = {
                    "task": "transcribe"  # Sempre usar transcribe para manter no idioma original
                }
                
                # Definir idioma
                if language_mode == "auto" and detected_language:
                    transcribe_params["language"] = detected_language
                elif language_mode == "specify" and language:
                    transcribe_params["language"] = language
                
                # Realizar transcrição
                result = model.transcribe(file_to_transcribe, **transcribe_params)
                text = result["text"]
                
                if not detected_language:
                    detected_language = result.get("language", "desconhecido")
                
                # Calcular tempo total de transcrição
                total_transcription_time = time.time() - transcription_start_time
                total_processing_time = time.time() - start_time
                
                # Log de estatísticas
                log_transcription_stats(
                    task_id=task_id,
                    file_name=original_filename,
                    model=model_name,
                    duration=duration or 0,
                    transcription_time=total_transcription_time,
                    success=True
                )
                
                # Finalizar
                self.update_task_progress(task_id, 95, "Finalizando e salvando resultados")
                self.update_task_result(
                    task_id,
                    text=text,
                    detected_language=detected_language,
                    original_filename=original_filename,
                    export_formats=export_formats,
                    processing_duration=total_processing_time
                )
                
                transcription_logger.info(
                    f"Transcrição concluída: {task_id} - {original_filename} - "
                    f"Tempo: {total_processing_time:.2f}s - Idioma: {detected_language}"
                )
                
            except Exception as e:
                error_msg = f"Erro na transcrição: {str(e)}"
                transcription_logger.error(error_msg)
                self.update_task_result(task_id, error=error_msg)
                
                # Log de falha
                log_transcription_stats(
                    task_id=task_id,
                    file_name=original_filename,
                    model=model_name,
                    duration=duration or 0,
                    transcription_time=time.time() - transcription_start_time,
                    success=False
                )
            
        finally:
            # Limpar arquivos temporários
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                if is_video and audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception as e:
                error_logger.error(f"Erro ao remover arquivos temporários: {str(e)}")
    
    def _format_time(self, seconds):
        """Formata segundos para uma representação legível"""
        if seconds is None:
            return "Calculando..."
        
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_queue_status(self):
        """Retorna informações sobre o status da fila"""
        # Encontrar todas as tarefas que estão na fila
        queued_tasks = [task_id for task_id in self.tasks.keys() 
                       if self.tasks[task_id].get("queue_status") == "queued"]
        
        # Verificar se há tarefas na fila e retornar o ID da próxima
        if queued_tasks:
            # Ordenar pela data de criação
            queued_tasks.sort(key=lambda x: self.tasks[x].get("created_at", 0))
            next_task_id = queued_tasks[0] if queued_tasks else None
            
            return {
                "queue_size": len(queued_tasks),
                "next_task_id": next_task_id,
                "has_items": True,
                "active_tasks": sum(1 for t in self.tasks.values() if t.get("status") == "processing")
            }
        else:
            return {
                "queue_size": 0,
                "next_task_id": None,
                "has_items": False,
                "active_tasks": sum(1 for t in self.tasks.values() if t.get("status") == "processing")
            }
    
    def cleanup_old_tasks(self, hours=24):
        """Remove tarefas antigas da memória (já salvas no banco)"""
        now = datetime.now().timestamp()
        cutoff = now - (hours * 3600)  # Converter horas para segundos
        
        to_remove = []
        for task_id, task in self.tasks.items():
            if task.get("updated_at", 0) < cutoff:
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            logger.info(f"Limpeza: {len(to_remove)} tarefa(s) removida(s) da memória")
    
    def get_model_info(self, model_name=None):
        """Retorna informações sobre os modelos disponíveis ou um modelo específico"""
        models_info = {
            "base": {
                "size": "74 MB",
                "speed": "Rápido",
                "ram": "1 GB",
                "quality": "Básica"
            },
            "small": {
                "size": "244 MB",
                "speed": "Médio",
                "ram": "2 GB",
                "quality": "Boa"
            },
            "medium": {
                "size": "769 MB",
                "speed": "Lento",
                "ram": "4 GB",
                "quality": "Muito boa"
            },
            "large": {
                "size": "1.5 GB",
                "speed": "Muito lento",
                "ram": "8 GB",
                "quality": "Excelente"
            }
        }
        
        if model_name:
            return models_info.get(model_name, {"error": "Modelo não encontrado"})
        
        return models_info
    
    def list_completed_transcriptions(self, limit=10, user_id=None):
        """Lista as transcrições concluídas mais recentes"""
        try:
            db_session = get_session()
            query = db_session.query(Transcription).filter_by(status="completed")
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            transcriptions = query.order_by(Transcription.completed_at.desc()).limit(limit).all()
            
            result = []
            for t in transcriptions:
                result.append({
                    "id": t.id,
                    "task_id": t.task_id,
                    "filename": t.original_filename,
                    "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                    "duration": t.audio_duration,
                    "pdf": t.pdf_filename
                })
            
            db_session.close()
            return result
        except Exception as e:
            error_logger.error(f"Erro ao listar transcrições: {str(e)}")
            return []

# Instância global do gerenciador de transcrições
transcription_manager = TranscriptionManager() 