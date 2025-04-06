import os
import uuid
import logging
import yt_dlp

from src.config.config import Config

# Configuração de logging
youtube_logger = logging.getLogger("transcrever.youtube")

class YouTubeService:
    """Serviço para download de vídeos do YouTube"""
    
    @staticmethod
    def is_valid_youtube_url(url):
        """Verifica se a URL é uma URL válida do YouTube"""
        # Verificação básica de URL do YouTube
        valid_hosts = ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com']
        try:
            import urllib.parse as urlparse
            parsed_url = urlparse.urlparse(url)
            return parsed_url.netloc in valid_hosts
        except:
            return False
    
    @staticmethod
    def download_audio(youtube_url):
        """
        Baixa o áudio de um vídeo do YouTube.
        
        Args:
            youtube_url: URL do vídeo do YouTube
            
        Returns:
            Tupla (caminho_do_arquivo, nome_original) ou (None, None) se falhar
        """
        if not YouTubeService.is_valid_youtube_url(youtube_url):
            youtube_logger.error(f"URL inválida: {youtube_url}")
            return None, None
        
        # Cria nome de arquivo único
        output_filename = str(uuid.uuid4()) + ".mp3"
        output_path = os.path.join(Config.UPLOAD_DIR, output_filename)
        
        # Configuração do yt-dlp
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
        
        try:
            # Obter informações do vídeo
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info_dict = ydl.extract_info(youtube_url, download=False)
                video_title = info_dict.get('title', 'video')
                original_filename = f"{video_title}.mp3"
            
            # Baixar o vídeo como áudio
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            
            youtube_logger.info(f"YouTube download concluído: {video_title}")
            return output_path, original_filename
            
        except Exception as e:
            youtube_logger.error(f"Erro ao baixar vídeo do YouTube: {str(e)}")
            # Remover arquivo parcial se existir
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            return None, None 