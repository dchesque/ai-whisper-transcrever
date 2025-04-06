from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory, session, make_response
from flask_login import LoginManager, current_user, UserMixin, login_user, logout_user
import os
import whisper
import logging
from datetime import datetime
from config import get_config
import tempfile
import uuid
import shutil
import threading
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from werkzeug.utils import secure_filename
import subprocess
import requests
import yt_dlp
import re

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Classe de usuário para o Flask-Login
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

app = Flask(__name__)
app.config.from_object(get_config())  # Carregando configurações do config.py

# Configurar Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Configurar pasta de uploads e PDFs
UPLOAD_FOLDER = 'uploads'
PDF_FOLDER = 'pdfs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

# Modelo Whisper para transcrição
whisper_model = None
whisper_lock = threading.Lock()

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        with whisper_lock:
            if whisper_model is None:
                logger.info("Carregando modelo Whisper...")
                whisper_model = whisper.load_model("base")
                logger.info("Modelo Whisper carregado")
    return whisper_model

def text_to_pdf(text, output_path):
    """Converte texto para PDF usando reportlab"""
    buffer = BytesIO()
    # Criar um PDF com reportlab
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Configurar fonte e tamanho
    c.setFont("Helvetica", 12)
    
    # Margens
    margin = 50
    y = height - margin
    
    # Título
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "Transcrição de Áudio/Vídeo")
    y -= 30
    
    # Data
    c.setFont("Helvetica", 10)
    current_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.drawString(margin, y, f"Gerado em: {current_date}")
    y -= 30
    
    # Conteúdo da transcrição
    c.setFont("Helvetica", 12)
    
    # Dividir o texto em linhas
    lines = text.split('\n')
    for line in lines:
        # Verificar se precisamos de uma nova página
        if y < margin:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 12)
        
        # Desenhar texto
        words = line.split()
        if words:
            line_text = ""
            for word in words:
                test_text = line_text + " " + word if line_text else word
                text_width = c.stringWidth(test_text, "Helvetica", 12)
                
                if text_width > width - 2 * margin:
                    c.drawString(margin, y, line_text)
                    y -= 20
                    line_text = word
                else:
                    line_text = test_text
            
            if line_text:
                c.drawString(margin, y, line_text)
        
        y -= 20
    
    # Finalizar o PDF
    c.showPage()
    c.save()
    
    # Obter o conteúdo do buffer e salvá-lo no arquivo
    buffer.seek(0)
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

# Rotas de autenticação
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login com Magic Link"""
    if 'user' in session:
        return redirect(url_for('dashboard'))
    
    # Apenas renderizar a página de login, o envio do Magic Link é tratado por AJAX
    return render_template('login.html')

@app.route('/auth/send-magic-link', methods=['POST'])
def send_magic_link_route():
    """Rota para enviar Magic Link usando Supabase"""
    data = request.get_json()
    
    if not data or 'email' not in data:
        return jsonify({"error": "Email não fornecido"}), 400
    
    email = data['email']
    
    try:
        from auth import send_magic_link
        # Envia o magic link usando a função do auth.py
        success = send_magic_link(email)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Link mágico enviado com sucesso!"
            }), 200
        else:
            return jsonify({
                "success": False,
                "error": "Não foi possível enviar o magic link"
            }), 500
    except Exception as e:
        logger.error(f"Erro ao enviar magic link: {str(e)}")
        
        # Verificar se é um erro de limitação de taxa
        error_msg = str(e)
        if "security purposes" in error_msg and "seconds" in error_msg:
            # Extrair o tempo de espera da mensagem de erro
            try:
                wait_time = int(''.join(filter(str.isdigit, error_msg)))
                return jsonify({
                    "success": False,
                    "error": f"Por favor, aguarde {wait_time} segundos antes de solicitar um novo link.",
                    "wait_time": wait_time
                }), 429
            except:
                return jsonify({
                    "success": False,
                    "error": "Por favor, aguarde alguns segundos antes de solicitar um novo link.",
                    "wait_time": 30  # Tempo padrão de espera
                }), 429
        
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/auth/verify', methods=['GET', 'POST'])
def verify_auth():
    """Verifica o token de autenticação e cria a sessão do usuário"""
    # Se for um GET, renderiza a página de verificação
    if request.method == 'GET':
        # Log de todas as informações da requisição
        logger.info(f"GET para /auth/verify - URL: {request.url}")
        logger.info(f"Query params: {request.args}")
        
        # Para GET requests, apenas renderiza a página de verificação
        # O JavaScript nessa página fará a verificação real
        return render_template('verify.html')
    
    # Se for POST, verifica o token
    data = request.get_json()
    
    if not data or 'token' not in data:
        logger.error("Erro de verificação: Token não fornecido")
        return jsonify({"error": "Token não fornecido"}), 400
    
    token = data['token']
    token_type = data.get('type', 'magiclink')  # Obtém o tipo de token, padrão é 'magiclink'
    
    logger.info(f"Recebido token para verificação: {token[:15]}... (tipo: {token_type})")
    
    try:
        from auth import verify_auth_token, create_session
        
        # Verifica o token e obtém o usuário
        user = verify_auth_token(token, token_type)
        
        if user:
            # Cria a sessão do usuário
            create_session(user)
            logger.info(f"Autenticação bem-sucedida para: {user.email}")
            return jsonify({
                "success": True,
                "message": "Autenticação bem-sucedida",
                "user": {
                    "email": user.email,
                    "id": user.id
                }
            }), 200
        else:
            logger.warning("Falha na autenticação: Token inválido ou expirado")
            return jsonify({"success": False, "error": "Token inválido ou expirado"}), 401
    except Exception as e:
        logger.error(f"Erro ao verificar token: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/logout')
def logout():
    """Encerra a sessão do usuário"""
    from auth import clear_session
    clear_session()
    flash("Você foi desconectado com sucesso", "success")
    return redirect(url_for('index'))

# Rotas principais
@app.route('/')
def index():
    """Página inicial"""
    # Listar PDFs gerados
    pdfs = []
    try:
        for filename in os.listdir(PDF_FOLDER):
            if filename.endswith('.pdf'):
                file_path = os.path.join(PDF_FOLDER, filename)
                modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                pdfs.append({
                    'filename': filename,
                    'created_at': modified_time.strftime('%d/%m/%Y %H:%M')
                })
        
        # Ordenar por data (mais recente primeiro)
        pdfs.sort(key=lambda x: x['created_at'], reverse=True)
    except Exception as e:
        logger.error(f"Erro ao listar PDFs: {str(e)}")
    
    return render_template('index.html', current_user=current_user, pdfs=pdfs)

@app.route('/como-funciona')
def como_funciona():
    return render_template('como-funciona.html', current_user=current_user)

@app.route('/termos')
def termos():
    return render_template('termos.html', current_user=current_user)

@app.route('/privacidade')
def privacidade():
    return render_template('privacidade.html', current_user=current_user)

@app.route('/transcribe', methods=['POST'])
def transcribe():
    """Rota para transcrever arquivos"""
    # Verificar se o usuário está logado
    if 'user' not in session:
        return jsonify({'error': 'Você precisa estar logado para transcrever arquivos'}), 401
    
    # Verificar origem da entrada: arquivo ou URL
    has_file = 'file' in request.files
    has_url = 'url' in request.form and request.form['url'].strip()
    
    if not has_file and not has_url:
        return jsonify({'error': 'Nenhum arquivo ou URL fornecida'}), 400
    
    # Obter configurações
    model_name = request.form.get('model', 'base')
    language_mode = request.form.get('language_mode', 'auto')
    language = None if language_mode == 'auto' else request.form.get('language', None)
    
    try:
        # Criar diretório temporário para processamento
        temp_dir = tempfile.mkdtemp()
        audio_path = os.path.join(temp_dir, "audio_input.mp3")
        
        # Processar entrada (arquivo ou URL)
        if has_file:
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
            
            if not file.filename.lower().endswith(('.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.wmv', '.flv')):
                return jsonify({'error': 'Formato de arquivo não suportado'}), 400
            
            # Salvar arquivo
            safe_filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"{str(uuid.uuid4())}_{safe_filename}")
            file.save(filepath)
            input_path = filepath
            original_filename = file.filename
            file_type = os.path.splitext(file.filename)[1][1:].upper()  # Extrair extensão (MP3, MP4, etc)
        else:
            # Processar URL
            url = request.form['url']
            
            # Validar URL básica
            if not url.startswith(('http://', 'https://')):
                return jsonify({'error': 'URL inválida'}), 400
                
            # Baixar conteúdo da URL
            logger.info(f"Baixando conteúdo da URL: {url}")
            
            # Determinar se é YouTube ou URL direta
            is_youtube = re.search(r'(youtube\.com|youtu\.be)', url) is not None
            file_type = 'YOUTUBE' if is_youtube else 'URL'
            
            if is_youtube or not url.endswith(('.mp3', '.wav', '.ogg', '.mp4', '.avi', '.mov', '.wmv', '.flv')):
                # Usar yt-dlp para YouTube e outras plataformas de vídeo
                try:
                    # Definir opções do yt-dlp
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': audio_path,
                        'quiet': True,
                        'no_warnings': True,
                        'postprocessors': [{
                            'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3',
                            'preferredquality': '192',
                        }],
                    }
                    
                    # Baixar o áudio
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        # Obter título do vídeo, se disponível
                        video_title = info.get('title', url)
                        
                    # Verificar se o arquivo foi baixado
                    if not os.path.exists(audio_path):
                        audio_path = audio_path + ".mp3"  # yt-dlp adiciona extensão
                    
                    input_path = audio_path
                    original_filename = video_title
                    
                    # Obter duração do vídeo, se disponível (em segundos)
                    duration = info.get('duration', 0)
                    
                except Exception as e:
                    logger.error(f"Erro ao baixar vídeo: {str(e)}")
                    return jsonify({'error': f'Erro ao baixar o áudio/vídeo: {str(e)}'}), 500
            else:
                # URL direta para arquivo de áudio/vídeo
                try:
                    response = requests.get(url, stream=True)
                    if response.status_code != 200:
                        return jsonify({'error': f'Erro ao acessar URL: {response.status_code}'}), 400
                    
                    # Salvar arquivo no disco
                    with open(audio_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    input_path = audio_path
                    original_filename = url
                    duration = 0  # Não temos como saber a duração de um arquivo URL direta
                except Exception as e:
                    logger.error(f"Erro ao baixar arquivo: {str(e)}")
                    return jsonify({'error': f'Erro ao baixar arquivo: {str(e)}'}), 500
        
        # Obter informações do arquivo
        duration = 0
        if 'duration' not in locals() or not duration:
            try:
                # Tentar obter duração do arquivo com ffprobe se disponível
                import subprocess
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                if result.stdout:
                    duration = int(float(result.stdout.strip()))
            except:
                # Se não conseguir, não se preocupe
                duration = 0
                
        # Carregar o modelo Whisper especificado
        logger.info(f"Carregando modelo Whisper: {model_name}")
        model = whisper.load_model(model_name)
        
        # Transcrever arquivo
        logger.info(f"Iniciando transcrição do arquivo: {original_filename if has_file else url}")
        
        # Configure opções com base no idioma e outras configurações
        transcribe_options = {}
        if language:
            transcribe_options['language'] = language
            
        # Executar transcrição
        result = model.transcribe(input_path, **transcribe_options)
        
        # Obter o texto transcrito
        text = result["text"]
        
        # Adicionar informações sobre o arquivo
        text_with_info = text + f"\n\nArquivo original: {original_filename if has_file else 'URL: ' + url}"
        text_with_info += f"\nModelo utilizado: {model_name}"
        text_with_info += f"\nIdioma: {'Detecção automática' if language is None else language}"
        text_with_info += f"\nData de processamento: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        
        # Salvar em formato PDF
        pdf_filename = f"transcricao_{uuid.uuid4()}.pdf"
        pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
        
        # Criar PDF a partir do texto
        text_to_pdf(text_with_info, pdf_path)
        
        # Salvar no banco de dados Supabase (se o usuário estiver logado)
        transcription_id = None
        if 'user' in session:
            try:
                from database import save_transcription
                
                # Criar um título baseado no nome do arquivo ou URL
                title = original_filename
                if has_url and is_youtube:
                    # Para vídeos do YouTube, usar o título do vídeo
                    title = original_filename
                elif has_url:
                    # Para URLs, usar um título genérico
                    title = f"Transcrição de URL"
                elif has_file:
                    # Para arquivos, usar o nome do arquivo sem a extensão
                    title = os.path.splitext(original_filename)[0]
                
                # Obter idioma detectado
                detected_language = result.get("language", "")
                if not detected_language and language:
                    detected_language = language
                
                # Salvar transcrição no Supabase
                user_id = session['user']['id']
                result = save_transcription(
                    user_id=user_id,
                    title=title,
                    original_filename=original_filename,
                    transcription_text=text,
                    language=detected_language,
                    file_type=file_type,
                    duration=duration
                )
                
                if result:
                    transcription_id = result.get('id')
                    logger.info(f"Transcrição salva no banco de dados com ID: {transcription_id}")
                else:
                    logger.warning("Não foi possível salvar a transcrição no banco de dados")
                    
            except Exception as e:
                logger.error(f"Erro ao salvar transcrição no banco de dados: {str(e)}")
                # Continuar mesmo se falhar ao salvar no banco de dados
        
        # Remover arquivo temporário
        if has_file:
            os.remove(filepath)
        
        # Limpar diretório temporário
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Determinar para onde redirecionar o usuário após a transcrição
        redirect_to = 'dashboard' if transcription_id else 'index'
        
        return jsonify({
            'success': True,
            'text': text,
            'pdf_filename': pdf_filename,
            'transcription_id': transcription_id,
            'redirect_to': url_for(redirect_to)
        })
    except Exception as e:
        logger.error(f"Erro durante a transcrição: {str(e)}")
        # Limpar recursos
        try:
            if has_file and 'filepath' in locals() and os.path.exists(filepath):
                os.remove(filepath)
            if 'temp_dir' in locals():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass
        return jsonify({'error': f'Erro durante a transcrição: {str(e)}'}), 500

@app.route('/download_pdf/<filename>')
def download_pdf(filename):
    """Rota para baixar PDF gerado"""
    return send_from_directory(PDF_FOLDER, filename)

@app.route('/delete_pdf/<filename>', methods=['POST'])
def delete_pdf(filename):
    """Rota para excluir PDF"""
    # Verificar se o usuário está logado
    if 'user' not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        # Verificar se o arquivo existe
        file_path = os.path.join(PDF_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "Arquivo não encontrado"}), 404
        
        # Excluir o arquivo
        os.remove(file_path)
        logger.info(f"PDF {filename} excluído com sucesso")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Erro ao excluir PDF: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/dashboard')
def dashboard():
    """Página de dashboard do usuário"""
    # Verificar se o usuário está logado
    if 'user' not in session:
        flash("Você precisa estar logado para acessar o dashboard", "error")
        return redirect(url_for('login'))
    
    user = session['user']
    logger.info(f"Acessando dashboard para usuário: {user['email']}")
    
    try:
        # Buscar transcrições do usuário no Supabase
        from database import get_user_transcriptions, get_user_categories
        
        transcriptions = get_user_transcriptions(user['id'])
        logger.info(f"Encontradas {len(transcriptions)} transcrições para o usuário")
        
        # Buscar categorias do usuário
        categories = get_user_categories(user['id'])
        logger.info(f"Encontradas {len(categories)} categorias para o usuário")
        
        # Buscar PDFs locais (temporário até migrarmos completamente para o Supabase)
        pdfs = []
        try:
            for filename in os.listdir(PDF_FOLDER):
                if filename.endswith('.pdf'):
                    file_path = os.path.join(PDF_FOLDER, filename)
                    modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    pdfs.append({
                        'filename': filename,
                        'created_at': modified_time.strftime('%d/%m/%Y %H:%M')
                    })
            
            # Ordenar por data (mais recente primeiro)
            pdfs.sort(key=lambda x: x['created_at'], reverse=True)
        except Exception as e:
            logger.error(f"Erro ao listar PDFs: {str(e)}")
        
        return render_template('dashboard.html', 
                              user=user, 
                              transcriptions=transcriptions,
                              categories=categories, 
                              pdfs=pdfs)
    except Exception as e:
        logger.error(f"Erro ao carregar dashboard: {str(e)}")
        flash("Ocorreu um erro ao carregar suas transcrições", "error")
        return redirect(url_for('index'))

@app.route('/transcription/<transcription_id>/download')
def download_transcription(transcription_id):
    """Rota para baixar o texto de uma transcrição"""
    # Verificar se o usuário está logado
    if 'user' not in session:
        flash("Você precisa estar logado para baixar transcrições", "error")
        return redirect(url_for('login'))
    
    try:
        from database import get_transcription
        
        # Obter a transcrição
        user_id = session['user']['id']
        transcription = get_transcription(transcription_id, user_id)
        
        if not transcription:
            return jsonify({"error": "Transcrição não encontrada"}), 404
        
        # Verificar se o usuário quer o formato PDF
        format_type = request.args.get('format', 'txt')
        
        if format_type == 'pdf':
            # Gerar PDF
            title = transcription['title'] or transcription['original_filename']
            filename = f"{title}.pdf".replace(' ', '_')
            
            # Diretório temporário para o PDF
            pdf_dir = os.path.join(os.getcwd(), 'transcricoes_pdf')
            os.makedirs(pdf_dir, exist_ok=True)
            
            pdf_path = os.path.join(pdf_dir, f"{uuid.uuid4()}.pdf")
            
            # Criar o PDF
            text_to_pdf(transcription['transcription_text'], pdf_path)
            
            # Enviar o arquivo
            return send_from_directory(
                directory=os.path.dirname(pdf_path),
                path=os.path.basename(pdf_path),
                as_attachment=True,
                download_name=re.sub(r'[^\w\.-]', '_', filename)
            )
        else:
            # Preparar o arquivo de texto para download
            filename = f"{transcription['title'] or transcription['original_filename']}.txt"
            # Sanitizar o nome do arquivo para download
            filename = re.sub(r'[^\w\.-]', '_', filename)
            
            response = make_response(transcription['transcription_text'])
            response.headers.set('Content-Type', 'text/plain')
            response.headers.set('Content-Disposition', f'attachment; filename={filename}')
            return response
    except Exception as e:
        logger.error(f"Erro ao baixar transcrição: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/transcription/<transcription_id>/delete', methods=['DELETE'])
def delete_transcription_route(transcription_id):
    """Rota para excluir uma transcrição"""
    # Verificar se o usuário está logado
    if 'user' not in session:
        return jsonify({"error": "Não autorizado"}), 401
    
    try:
        from database import delete_transcription
        
        # Excluir a transcrição
        user_id = session['user']['id']
        success = delete_transcription(transcription_id, user_id)
        
        if success:
            logger.info(f"Transcrição {transcription_id} excluída com sucesso")
            return jsonify({"success": True})
        else:
            logger.warning(f"Falha ao excluir transcrição {transcription_id}")
            return jsonify({"error": "Não foi possível excluir a transcrição"}), 400
    except Exception as e:
        logger.error(f"Erro ao excluir transcrição: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/transcription/<transcription_id>/update', methods=['POST'])
def update_transcription_metadata():
    """Atualiza os metadados (título, categoria) de uma transcrição"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    transcription_id = request.view_args.get('transcription_id')
    
    try:
        # Extrair dados do formulário
        data = request.json
        update_data = {}
        
        # Validar e incluir campos para atualização
        if 'title' in data and data['title'].strip():
            update_data['title'] = data['title'].strip()
            
        if 'category' in data:
            update_data['category'] = data['category'].strip() if data['category'] else None
        
        if not update_data:
            return jsonify({'success': False, 'error': 'Nenhum dado válido para atualização'}), 400
        
        # Atualizar no banco de dados
        from database import update_transcription
        result = update_transcription(transcription_id, user['id'], update_data)
        
        if result:
            logger.info(f"Transcrição {transcription_id} atualizada com sucesso: {update_data}")
            return jsonify({
                'success': True, 
                'message': 'Transcrição atualizada com sucesso',
                'transcription': result
            })
        else:
            logger.warning(f"Falha ao atualizar transcrição {transcription_id}")
            return jsonify({'success': False, 'error': 'Não foi possível atualizar a transcrição'}), 400
            
    except Exception as e:
        logger.error(f"Erro ao atualizar transcrição: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

@app.route('/transcription/<transcription_id>/details', methods=['GET'])
def get_transcription_details():
    """Obtém detalhes de uma transcrição específica"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    transcription_id = request.view_args.get('transcription_id')
    
    try:
        # Buscar transcrição no banco de dados
        from database import get_transcription
        transcription = get_transcription(transcription_id, user['id'])
        
        if transcription:
            return jsonify({
                'success': True,
                'transcription': transcription
            })
        else:
            return jsonify({'success': False, 'error': 'Transcrição não encontrada'}), 404
            
    except Exception as e:
        logger.error(f"Erro ao buscar detalhes da transcrição: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

# Rotas para gerenciar categorias personalizadas
@app.route('/categories', methods=['GET'])
def get_categories():
    """Obtém todas as categorias do usuário"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    
    try:
        from database import get_user_categories
        categories = get_user_categories(user['id'])
        
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        logger.error(f"Erro ao buscar categorias: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

@app.route('/categories', methods=['POST'])
def create_category():
    """Cria uma nova categoria para o usuário"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    
    try:
        data = request.json
        
        if not data or 'name' not in data or not data['name'].strip():
            return jsonify({'success': False, 'error': 'Nome da categoria é obrigatório'}), 400
        
        from database import create_user_category
        
        category = create_user_category(
            user['id'],
            data['name'].strip(),
            data.get('color')
        )
        
        if category:
            logger.info(f"Categoria criada com sucesso: {category['name']}")
            return jsonify({
                'success': True,
                'message': 'Categoria criada com sucesso',
                'category': category
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível criar a categoria'}), 400
    except Exception as e:
        logger.error(f"Erro ao criar categoria: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

@app.route('/categories/<category_id>', methods=['PUT'])
def update_category(category_id):
    """Atualiza uma categoria existente"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    
    try:
        data = request.json
        update_data = {}
        
        if 'name' in data and data['name'].strip():
            update_data['name'] = data['name'].strip()
        
        if 'color' in data:
            update_data['color'] = data['color']
        
        if not update_data:
            return jsonify({'success': False, 'error': 'Nenhum dado válido para atualização'}), 400
        
        from database import update_user_category
        
        category = update_user_category(category_id, user['id'], update_data)
        
        if category:
            logger.info(f"Categoria {category_id} atualizada com sucesso")
            return jsonify({
                'success': True,
                'message': 'Categoria atualizada com sucesso',
                'category': category
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível atualizar a categoria'}), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar categoria: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

@app.route('/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    """Exclui uma categoria existente"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    
    try:
        from database import delete_user_category
        
        success = delete_user_category(category_id, user['id'])
        
        if success:
            logger.info(f"Categoria {category_id} excluída com sucesso")
            return jsonify({
                'success': True,
                'message': 'Categoria excluída com sucesso'
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível excluir a categoria'}), 400
    except Exception as e:
        logger.error(f"Erro ao excluir categoria: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

@app.route('/transcription/<transcription_id>/category', methods=['POST'])
def set_transcription_category():
    """Define a categoria de uma transcrição"""
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Usuário não autenticado'}), 401
    
    user = session['user']
    transcription_id = request.view_args.get('transcription_id')
    
    try:
        data = request.json
        category_id = data.get('category_id')
        
        from database import update_transcription_category
        
        # Se category_id for None ou vazio, a categoria será removida
        result = update_transcription_category(transcription_id, user['id'], category_id)
        
        if result:
            logger.info(f"Categoria da transcrição {transcription_id} atualizada com sucesso")
            return jsonify({
                'success': True,
                'message': 'Categoria da transcrição atualizada com sucesso',
                'transcription': result
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível atualizar a categoria da transcrição'}), 400
    except Exception as e:
        logger.error(f"Erro ao atualizar categoria da transcrição: {str(e)}")
        return jsonify({'success': False, 'error': 'Erro ao processar solicitação'}), 500

if __name__ == "__main__":
    # Carregar configurações
    config = get_config()
    # Garantir que a porta seja sempre 3000
    port = 3000
    app.run(debug=config.DEBUG, port=port, host='0.0.0.0')
