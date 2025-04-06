from functools import wraps
from flask import session, redirect, url_for, request, flash, current_app
from database import supabase
import logging
from datetime import datetime, timedelta
import re

# Configurar logging
logger = logging.getLogger(__name__)

def login_required(f):
    """Decorator para rotas que requerem autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Retorna o usuário atual se estiver logado"""
    return session.get('user')

def send_magic_link(email):
    """Envia um magic link para o email fornecido usando o Supabase"""
    try:
        # Construir a URL de redirecionamento completa e explícita
        redirect_url = url_for('verify_auth', _external=True)
        
        # Verificar a URL de redirecionamento
        logger.info(f"Enviando magic link para {email} com redirect para {redirect_url}")
        
        # Usar a função sign_in_with_otp do Supabase para enviar o magic link
        data = {
            "email": email,
            "options": {
                "email_redirect_to": redirect_url
            }
        }
        
        logger.info(f"Enviando magic link com dados: {data}")
        
        # Usar a função correta para Magic Link
        result = supabase.auth.sign_in_with_otp(data)
        
        logger.info(f"Magic link enviado para {email}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar magic link: {str(e)}")
        return False

def verify_auth_token(token, token_type='magiclink'):
    """Verifica o token de autenticação do Supabase"""
    try:
        logger.info(f"Verificando token de autenticação: {token[:15]}...")
        
        # Verifica por tipo de token
        if token_type == 'magiclink':
            try:
                # Verificar por token hash
                session_data = supabase.auth.verify_otp({
                    "token_hash": token,
                    "type": "magiclink"
                })
                
                if session_data and hasattr(session_data, 'user'):
                    logger.info(f"Usuário autenticado via Magic Link: {session_data.user.email}")
                    return session_data.user
            except Exception as e:
                logger.warning(f"Falha ao verificar token como token_hash: {str(e)}")
                
                # Tenta verificar como access token
                try:
                    user = supabase.auth.get_user(token)
                    if user and hasattr(user, 'user'):
                        logger.info(f"Usuário autenticado como access_token: {user.user.email}")
                        return user.user
                except Exception as inner_e:
                    logger.warning(f"Falha ao verificar token como access_token: {str(inner_e)}")
        
        logger.warning("Autenticação falhou: token inválido ou expirado")
        return None
    except Exception as e:
        logger.error(f"Erro durante verificação do token: {str(e)}")
        return None

def create_session(user_data):
    """Cria uma sessão para o usuário"""
    session['user'] = {
        'id': user_data.id,
        'email': user_data.email,
        'created_at': user_data.created_at,
        'last_sign_in_at': datetime.now().isoformat()
    }
    logger.info(f"Sessão criada para usuário: {user_data.email}")

def clear_session():
    """Limpa a sessão do usuário"""
    if 'user' in session:
        email = session['user'].get('email', 'desconhecido')
        logger.info(f"Limpando sessão do usuário: {email}")
    
    session.pop('user', None)
    
    # Também faz logout no Supabase
    try:
        supabase.auth.sign_out()
        logger.info("Logout realizado no Supabase")
    except Exception as e:
        logger.error(f"Erro ao fazer logout no Supabase: {str(e)}") 