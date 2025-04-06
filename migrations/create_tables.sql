-- Habilitar a extensão UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Tabela de usuários (gerenciada pelo Supabase Auth)
-- Apenas para referência, não é necessário criar
/*
CREATE TABLE auth.users (
  id uuid NOT NULL PRIMARY KEY,
  email text,
  created_at timestamp with time zone,
  updated_at timestamp with time zone,
  ...
);
*/

-- Remover tabela existente e seus objetos relacionados
DROP TRIGGER IF EXISTS set_transcriptions_updated_at ON public.transcriptions;
DROP FUNCTION IF EXISTS public.set_updated_at();
DROP TABLE IF EXISTS public.transcriptions;

-- Tabela de transcrições
CREATE TABLE public.transcriptions (
    id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
    title text NOT NULL,
    transcription_text text NOT NULL,
    original_filename text,
    duration integer,
    language text,
    file_type text,
    category text,
    created_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at timestamp with time zone DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Índices para melhor performance
CREATE INDEX idx_transcriptions_user_id ON public.transcriptions(user_id);
CREATE INDEX idx_transcriptions_created_at ON public.transcriptions(created_at);

-- Função para atualizar o updated_at automaticamente
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar o updated_at
CREATE TRIGGER set_transcriptions_updated_at
    BEFORE UPDATE ON public.transcriptions
    FOR EACH ROW
    EXECUTE FUNCTION public.set_updated_at();

-- Habilitar RLS (Row Level Security)
ALTER TABLE public.transcriptions ENABLE ROW LEVEL SECURITY;

-- Políticas de segurança (RLS)
CREATE POLICY "Usuários podem inserir suas próprias transcrições"
    ON public.transcriptions
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Usuários podem visualizar suas próprias transcrições"
    ON public.transcriptions
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Usuários podem atualizar suas próprias transcrições"
    ON public.transcriptions
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Usuários podem excluir suas próprias transcrições"
    ON public.transcriptions
    FOR DELETE
    USING (auth.uid() = user_id); 