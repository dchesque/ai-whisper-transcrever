import os
import json
from pathlib import Path

class Config:
    """Classe de configuração centralizada para o aplicativo"""
    
    # Diretórios padrão
    BASE_DIR = Path(__file__).parent.parent.parent
    UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
    PDF_DIR = os.path.join(BASE_DIR, 'transcricoes_pdf')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')
    
    # Configurações do aplicativo
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'chave-secreta-padrao-mudar-em-producao')
    APP_NAME = "Transcrever"
    APP_VERSION = "2.0.0"
    
    # Configurações da transcrição
    FILE_EXPIRATION_MINUTES = 30
    MAX_CONCURRENT_TRANSCRIPTIONS = 2
    TASK_TIMEOUT_SECONDS = 3600  # 1 hora
    
    # Configurações de whisper
    DEFAULT_MODEL = "base"
    AVAILABLE_MODELS = ["base", "small", "medium", "large"]
    
    # Configurações de exportação
    EXPORT_FORMATS = ["pdf", "txt", "srt", "docx"]
    
    # Configurações do banco de dados
    DB_TYPE = "sqlite"
    DB_NAME = os.path.join(BASE_DIR, 'database', 'transcrever.db')
    
    # Configurações de cache
    CACHE_DIR = os.path.join(BASE_DIR, 'cache')
    CACHE_MAX_SIZE_MB = 1000  # 1GB
    
    # Opções da interface
    DEFAULT_THEME = "light"  # light ou dark
    
    # Notificações
    ENABLE_NOTIFICATIONS = True
    
    # Configurações adicionais
    ENABLE_ANALYTICS = False
    
    @classmethod
    def get_upload_dir(cls):
        """Retorna o diretório de upload, criando-o se não existir"""
        if not os.path.exists(cls.UPLOAD_DIR):
            os.makedirs(cls.UPLOAD_DIR)
        return cls.UPLOAD_DIR
    
    @classmethod
    def get_pdf_dir(cls):
        """Retorna o diretório de PDFs, criando-o se não existir"""
        if not os.path.exists(cls.PDF_DIR):
            os.makedirs(cls.PDF_DIR)
        return cls.PDF_DIR
    
    @classmethod
    def get_log_dir(cls):
        """Retorna o diretório de logs, criando-o se não existir"""
        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR)
        return cls.LOG_DIR
    
    @classmethod
    def get_cache_dir(cls):
        """Retorna o diretório de cache, criando-o se não existir"""
        if not os.path.exists(cls.CACHE_DIR):
            os.makedirs(cls.CACHE_DIR)
        return cls.CACHE_DIR
    
    @classmethod
    def load_config_file(cls, config_file=None):
        """Carrega configurações a partir de um arquivo JSON"""
        if config_file is None:
            config_file = os.path.join(cls.BASE_DIR, 'config.json')
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # Atualiza as configurações da classe com os valores do arquivo
                for key, value in config_data.items():
                    if hasattr(cls, key):
                        setattr(cls, key, value)
                
                return True
            except Exception as e:
                print(f"Erro ao carregar arquivo de configuração: {str(e)}")
                return False
        return False
    
    @classmethod
    def save_config_file(cls, config_file=None):
        """Salva as configurações atuais em um arquivo JSON"""
        if config_file is None:
            config_file = os.path.join(cls.BASE_DIR, 'config.json')
            
        try:
            # Obtém todos os atributos da classe que não são métodos ou privados
            config_data = {key: value for key, value in cls.__dict__.items()
                          if not key.startswith('_') and not callable(value)}
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4, sort_keys=True)
            
            return True
        except Exception as e:
            print(f"Erro ao salvar arquivo de configuração: {str(e)}")
            return False

# Tenta carregar configurações de um arquivo externo se existir
Config.load_config_file() 