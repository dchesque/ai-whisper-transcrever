from supabase import create_client
from dotenv import load_dotenv
import os

# Carregar variáveis de ambiente
load_dotenv()

# Configurar cliente Supabase
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def init_db():
    """Inicializa o banco de dados com as tabelas necessárias"""
    # Criar tabela de transcrições
    # Nota: No Supabase, você precisa criar esta tabela manualmente através do dashboard
    """
    SQL para criar a tabela:
    
    create table transcriptions (
        id uuid default uuid_generate_v4() primary key,
        user_id uuid references auth.users,
        title text,
        original_filename text,
        transcription_text text,
        language text,
        created_at timestamp with time zone default timezone('utc'::text, now()),
        file_type text,
        duration integer,
        category text,
        status text default 'completed'
    );

    -- Políticas de segurança RLS (Row Level Security)
    alter table transcriptions enable row level security;

    -- Política para inserção
    create policy "Users can insert their own transcriptions"
    on transcriptions for insert
    with check (auth.uid() = user_id);

    -- Política para seleção
    create policy "Users can view their own transcriptions"
    on transcriptions for select
    using (auth.uid() = user_id);

    -- Política para deleção
    create policy "Users can delete their own transcriptions"
    on transcriptions for delete
    using (auth.uid() = user_id);

    -- Política para atualização
    create policy "Users can update their own transcriptions"
    on transcriptions for update
    using (auth.uid() = user_id);
    """
    pass

def save_transcription(user_id, title, original_filename, transcription_text, language, file_type, duration, category=None):
    """Salva uma transcrição no banco de dados"""
    try:
        data = {
            "user_id": user_id,
            "title": title,
            "original_filename": original_filename,
            "transcription_text": transcription_text,
            "language": language,
            "file_type": file_type,
            "duration": duration,
            "category": category
        }
        
        result = supabase.table("transcriptions").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao salvar transcrição: {str(e)}")
        return None

def update_transcription(transcription_id, user_id, data):
    """Atualiza uma transcrição existente"""
    try:
        result = supabase.table("transcriptions")\
            .update(data)\
            .eq("id", transcription_id)\
            .eq("user_id", user_id)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao atualizar transcrição: {str(e)}")
        return None

def get_user_transcriptions(user_id):
    """Obtém todas as transcrições de um usuário"""
    try:
        result = supabase.table("transcriptions")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute()
        return result.data
    except Exception as e:
        print(f"Erro ao buscar transcrições: {str(e)}")
        return []

def get_transcription(transcription_id, user_id):
    """Obtém uma transcrição específica"""
    try:
        result = supabase.table("transcriptions")\
            .select("*")\
            .eq("id", transcription_id)\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao buscar transcrição: {str(e)}")
        return None

def delete_transcription(transcription_id, user_id):
    """Deleta uma transcrição específica"""
    try:
        result = supabase.table("transcriptions")\
            .delete()\
            .eq("id", transcription_id)\
            .eq("user_id", user_id)\
            .execute()
        return True
    except Exception as e:
        print(f"Erro ao deletar transcrição: {str(e)}")
        return False

# Funções para gerenciar categorias personalizadas
def get_user_categories(user_id):
    """Obtém todas as categorias de um usuário"""
    try:
        result = supabase.table("user_categories")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("name")\
            .execute()
        return result.data
    except Exception as e:
        print(f"Erro ao buscar categorias: {str(e)}")
        return []

def create_user_category(user_id, name, color=None):
    """Cria uma nova categoria para o usuário"""
    try:
        data = {
            "user_id": user_id,
            "name": name,
            "color": color
        }
        
        result = supabase.table("user_categories").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao criar categoria: {str(e)}")
        return None

def update_user_category(category_id, user_id, data):
    """Atualiza uma categoria existente"""
    try:
        result = supabase.table("user_categories")\
            .update(data)\
            .eq("id", category_id)\
            .eq("user_id", user_id)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao atualizar categoria: {str(e)}")
        return None

def delete_user_category(category_id, user_id):
    """Deleta uma categoria específica"""
    try:
        # Primeiro, removemos a associação das transcrições com esta categoria
        supabase.table("transcriptions")\
            .update({"category_id": None})\
            .eq("category_id", category_id)\
            .eq("user_id", user_id)\
            .execute()
        
        # Depois, excluímos a categoria
        result = supabase.table("user_categories")\
            .delete()\
            .eq("id", category_id)\
            .eq("user_id", user_id)\
            .execute()
        return True
    except Exception as e:
        print(f"Erro ao deletar categoria: {str(e)}")
        return False

def get_transcription_with_category(transcription_id, user_id):
    """Obtém uma transcrição específica com informações da categoria"""
    try:
        result = supabase.table("transcriptions")\
            .select("*, user_categories(id, name, color)")\
            .eq("id", transcription_id)\
            .eq("user_id", user_id)\
            .limit(1)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao buscar transcrição com categoria: {str(e)}")
        return None

def update_transcription_category(transcription_id, user_id, category_id):
    """Atualiza a categoria de uma transcrição"""
    try:
        result = supabase.table("transcriptions")\
            .update({"category_id": category_id})\
            .eq("id", transcription_id)\
            .eq("user_id", user_id)\
            .execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"Erro ao atualizar categoria da transcrição: {str(e)}")
        return None 