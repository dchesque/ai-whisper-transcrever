import logging
import os
import sys
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import datetime
from ..config.config import Config

class Logger:
    """
    Classe para configuração e gerenciamento centralizado de logs
    """
    
    # Níveis de log disponíveis
    LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    # Formatos de log predefinidos
    FORMATS = {
        'simple': '%(levelname)s - %(message)s',
        'standard': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'detailed': '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s',
        'json': '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
    }
    
    @classmethod
    def setup(cls, logger_name='transcrever', level='INFO', log_format='standard', 
              console=True, file=True, file_level='INFO'):
        """
        Configura um logger com os handlers e formatos especificados
        
        Args:
            logger_name (str): Nome do logger
            level (str): Nível de log para console
            log_format (str): Formato do log
            console (bool): Se deve usar console handler
            file (bool): Se deve usar file handler
            file_level (str): Nível de log para arquivo
            
        Returns:
            logging.Logger: Logger configurado
        """
        # Criar diretório de logs se não existir
        log_dir = Config.get_log_dir()
        
        # Obter ou criar logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(cls.LEVELS.get(level.upper(), logging.INFO))
        logger.propagate = False
        
        # Remover handlers existentes
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # Configurar formato
        log_format = cls.FORMATS.get(log_format, cls.FORMATS['standard'])
        formatter = logging.Formatter(log_format)
        
        # Adicionar console handler se solicitado
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(cls.LEVELS.get(level.upper(), logging.INFO))
            logger.addHandler(console_handler)
            
        # Adicionar file handler se solicitado
        if file:
            log_file = os.path.join(log_dir, f"{logger_name}.log")
            
            # Usar RotatingFileHandler para limitar tamanho
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(cls.LEVELS.get(file_level.upper(), logging.INFO))
            logger.addHandler(file_handler)
            
        return logger
    
    @classmethod
    def get_logger(cls, name='transcrever', **kwargs):
        """
        Obtém um logger configurado com o nome especificado
        
        Args:
            name (str): Nome do logger
            **kwargs: Parâmetros de configuração para o logger
            
        Returns:
            logging.Logger: Logger configurado
        """
        return cls.setup(logger_name=name, **kwargs)
    
    @classmethod
    def setup_daily_file_logger(cls, logger_name='transcrever_daily', **kwargs):
        """
        Configura um logger que usa arquivos diários
        
        Args:
            logger_name (str): Nome do logger
            **kwargs: Parâmetros de configuração para o logger
            
        Returns:
            logging.Logger: Logger configurado
        """
        log_dir = Config.get_log_dir()
        logger = logging.getLogger(logger_name)
        logger.setLevel(cls.LEVELS.get(kwargs.get('level', 'INFO').upper(), logging.INFO))
        logger.propagate = False
        
        # Remover handlers existentes
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            
        # Obter formato
        log_format = cls.FORMATS.get(kwargs.get('log_format', 'standard'), cls.FORMATS['standard'])
        formatter = logging.Formatter(log_format)
        
        # Adicionar console handler se solicitado
        if kwargs.get('console', True):
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(cls.LEVELS.get(kwargs.get('level', 'INFO').upper(), logging.INFO))
            logger.addHandler(console_handler)
            
        # Configurar arquivo de log diário
        if kwargs.get('file', True):
            log_file = os.path.join(log_dir, f"{logger_name}.log")
            
            # TimedRotatingFileHandler para rotação diária
            file_handler = TimedRotatingFileHandler(
                log_file,
                when='midnight',
                interval=1,
                backupCount=30,  # Manter logs por 30 dias
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(cls.LEVELS.get(kwargs.get('file_level', 'INFO').upper(), logging.INFO))
            file_handler.suffix = "%Y-%m-%d"  # Sufixo do arquivo de backup
            logger.addHandler(file_handler)
            
        return logger

# Criar um logger para uso geral
logger = Logger.get_logger('transcrever')

# Criar um logger para erros críticos
error_logger = Logger.get_logger('transcrever_error', level='ERROR', file_level='ERROR')

# Criar um logger para transcrições (informação detalhada)
transcription_logger = Logger.get_logger('transcription', 
                                        log_format='detailed', 
                                        level='INFO',
                                        file_level='DEBUG')

# Criar um logger para estatísticas (formato JSON para análise)
stats_logger = Logger.setup_daily_file_logger('transcription_stats', 
                                             log_format='json',
                                             console=False)

def log_transcription_stats(task_id, file_name, model, duration, transcription_time, success):
    """Registra estatísticas de uma transcrição para análise"""
    data = {
        'task_id': task_id,
        'file_name': file_name,
        'model': model,
        'audio_duration': duration,
        'transcription_time': transcription_time,
        'success': success,
        'timestamp': datetime.datetime.now().isoformat()
    }
    
    # Converter para string formatada
    stats_str = (f"task_id={data['task_id']} file={data['file_name']} "
                f"model={data['model']} duration={data['audio_duration']:.2f}s "
                f"proc_time={data['transcription_time']:.2f}s success={data['success']}")
    
    stats_logger.info(stats_str) 