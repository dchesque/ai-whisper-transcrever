import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

class Config:
    """Configurações base da aplicação"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'chave-secreta-dev'
    DEBUG = False
    TESTING = False
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    PDF_FOLDER = os.path.join(os.getcwd(), 'pdfs')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100 MB limit
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PORT = 3000  # Porta padrão definida como 3000
    
    # Configurações do Banco de Dados
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    
    # Configurações de Upload
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov', 'wmv', 'flv'}
    
    # Configurações do Whisper
    WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
    WHISPER_DEVICE = os.getenv('WHISPER_DEVICE', 'cpu')
    
    # Configurações de Cache
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Configurações de Sessão
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 horas
    
    # Configurações de Email
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
    PORT = 3000  # Explicitamente definir para desenvolvimento

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'
    PORT = 3000  # Explicitamente definir para testes

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///prod.db'
    PORT = int(os.environ.get('PORT', 3000))  # Permitir sobrescrever pela variável de ambiente
    
    # Configurações de Segurança para Produção
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True

# Dicionário de configurações
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Retorna a configuração baseada no ambiente."""
    env = os.getenv('FLASK_ENV', 'default')
    return config.get(env, config['default']) 