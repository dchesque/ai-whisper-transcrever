from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
import datetime
import os
from ..config.config import Config

Base = declarative_base()

def get_engine():
    """Cria e retorna uma engine SQLAlchemy"""
    db_path = Config.DB_NAME
    
    # Garantir que o diretório do banco de dados existe
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Criar engine
    engine = create_engine(f'sqlite:///{db_path}', echo=Config.DEBUG)
    return engine

def get_session():
    """Cria e retorna uma sessão SQLAlchemy"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Inicializa o banco de dados, criando todas as tabelas"""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine

class User(Base):
    """Modelo para usuários do sistema"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relacionamentos
    transcriptions = relationship("Transcription", back_populates="user")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"

class Transcription(Base):
    """Modelo para as transcrições realizadas"""
    __tablename__ = 'transcriptions'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(36), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)  # audio ou video
    model_used = Column(String(20), nullable=False)
    language = Column(String(10))
    detected_language = Column(String(10))
    status = Column(String(20), default='pending')  # pending, processing, completed, error
    source_type = Column(String(20), default='upload')  # upload, youtube, etc.
    
    # Metadados de processamento
    audio_duration = Column(Float)  # duração em segundos
    processing_duration = Column(Float)  # tempo de processamento em segundos
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    
    # Conteúdo
    text_content = Column(Text)
    text_summary = Column(Text)
    
    # Informações de arquivo gerado
    pdf_filename = Column(String(255))
    other_formats = Column(String(255))  # JSON com outros formatos gerados
    
    # Relacionamentos
    user = relationship("User", back_populates="transcriptions")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<Transcription(id={self.id}, original_filename='{self.original_filename}', status='{self.status}')>"
    
    @property
    def is_completed(self):
        return self.status == 'completed'
    
    @property
    def is_processing(self):
        return self.status == 'processing'
    
    @property
    def is_failed(self):
        return self.status == 'error'
    
    @property
    def processing_time(self):
        """Retorna o tempo de processamento em formato legível"""
        if not self.processing_duration:
            return "N/A"
            
        seconds = int(self.processing_duration)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

class TranscriptionLog(Base):
    """Modelo para logs detalhados de transcrição"""
    __tablename__ = 'transcription_logs'
    
    id = Column(Integer, primary_key=True)
    transcription_id = Column(Integer, ForeignKey('transcriptions.id'), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(20))
    progress = Column(Integer)  # 0-100
    step = Column(String(50))
    message = Column(Text)
    
    def __repr__(self):
        return f"<TranscriptionLog(id={self.id}, status='{self.status}', progress={self.progress})>"

class Setting(Base):
    """Modelo para configurações do sistema"""
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text)
    description = Column(Text)
    
    def __repr__(self):
        return f"<Setting(key='{self.key}', value='{self.value}')>" 