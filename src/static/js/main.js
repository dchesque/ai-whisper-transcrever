/**
 * Transcrever - Script principal da aplicação
 * Versão 2.0.0
 */

// Variáveis globais
let queuedFiles = [];
let activeTaskId = null;
let isProcessing = false;
let isPolling = false;
let pollInterval = null;
let pollErrorCount = 0; // Contador de erros de polling
let appSettings = null;
let currentTheme = localStorage.getItem('theme') || 'light';

// DOM Elements
document.addEventListener('DOMContentLoaded', () => {
    // Carregar configurações
    loadSettings();
    
    // Aplicar tema
    applyTheme(currentTheme);
    
    // Inicializar upload de arquivos
    initFileUpload();
    
    // Inicializar alteração de tema
    initThemeToggle();
    
    // Inicializar tooltips
    initTooltips();
    
    // Carregar lista de PDFs gerados
    loadPDFs();
    
    // Verificar por tarefas incompletas
    checkIncompleteTranscriptions();
});

/**
 * Carrega as configurações da aplicação do servidor
 */
async function loadSettings() {
    try {
        const response = await fetch('/settings');
        if (!response.ok) throw new Error('Falha ao carregar configurações');
        
        appSettings = await response.json();
        
        // Aplicar as configurações na interface
        document.getElementById('app-version').textContent = appSettings.app_version;
        
        // Popular seletor de modelos
        const modelSelect = document.getElementById('model');
        if (modelSelect) {
            modelSelect.innerHTML = '';
            appSettings.available_models.forEach(model => {
                const option = document.createElement('option');
                option.value = model;
                option.textContent = model.charAt(0).toUpperCase() + model.slice(1);
                option.selected = model === appSettings.default_model;
                modelSelect.appendChild(option);
            });
        }
        
        // Popular formatos de exportação
        const exportFormats = document.getElementById('export-formats');
        if (exportFormats) {
            exportFormats.innerHTML = '';
            appSettings.export_formats.forEach(format => {
                const label = document.createElement('label');
                label.classList.add('checkbox-container');
                
                const input = document.createElement('input');
                input.type = 'checkbox';
                input.name = 'export_format';
                input.value = format;
                input.checked = format === 'pdf'; // PDF é o padrão
                
                const span = document.createElement('span');
                span.classList.add('checkbox-label');
                span.textContent = format.toUpperCase();
                
                label.appendChild(input);
                label.appendChild(span);
                exportFormats.appendChild(label);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar configurações:', error);
        showAlert('Não foi possível carregar as configurações do aplicativo.', 'error');
    }
}

/**
 * Aplica o tema (claro/escuro) à página
 */
function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    currentTheme = theme;
    
    // Atualizar o toggle do tema
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.checked = theme === 'dark';
    }
}

/**
 * Inicializa o toggle de tema claro/escuro
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.checked = currentTheme === 'dark';
        themeToggle.addEventListener('change', () => {
            const newTheme = themeToggle.checked ? 'dark' : 'light';
            applyTheme(newTheme);
        });
    }
}

/**
 * Inicializa tooltips
 */
function initTooltips() {
    const tooltips = document.querySelectorAll('.tooltip');
    tooltips.forEach(tooltip => {
        const text = tooltip.getAttribute('data-tooltip');
        if (text) {
            const tooltipText = document.createElement('span');
            tooltipText.classList.add('tooltip-text');
            tooltipText.textContent = text;
            tooltip.appendChild(tooltipText);
        }
    });
}

/**
 * Inicializa o upload de arquivos
 */
function initFileUpload() {
    const uploadForm = document.getElementById('upload-form');
    const mediaFile = document.getElementById('file');
    const uploadContainer = document.getElementById('upload-container');
    const submitBtn = document.getElementById('submit-btn');
    const clearQueueBtn = document.getElementById('clear-queue-btn');
    
    if (!uploadForm || !mediaFile) return;
    
    // Desativar botão de envio inicialmente
    submitBtn.disabled = true;
    
    // Event listener para seleção de arquivo
    mediaFile.addEventListener('change', (e) => {
        const files = e.target.files;
        
        if (files.length > 0) {
            // Adicionar arquivos à fila
            const newFiles = Array.from(files);
            for (const file of newFiles) {
                // Verificar se arquivo já está na fila
                const isDuplicate = queuedFiles.some(queuedFile => 
                    queuedFile.name === file.name && 
                    queuedFile.size === file.size
                );
                
                if (!isDuplicate) {
                    queuedFiles.push(file);
                }
            }
            
            // Atualizar a lista de arquivos
            updateFilesList();
            
            // Ativar o botão de envio se há arquivos na fila
            submitBtn.disabled = queuedFiles.length === 0;
        }
    });
    
    // Eventos de drag & drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadContainer.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        uploadContainer.classList.add('highlight');
    }
    
    function unhighlight() {
        uploadContainer.classList.remove('highlight');
    }
    
    // Lidar com soltar o arquivo
    uploadContainer.addEventListener('drop', handleDrop, false);
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            // Adicionar arquivos à fila
            const newFiles = Array.from(files);
            for (const file of newFiles) {
                // Verificar se arquivo já está na fila
                const isDuplicate = queuedFiles.some(queuedFile => 
                    queuedFile.name === file.name && 
                    queuedFile.size === file.size
                );
                
                if (!isDuplicate) {
                    queuedFiles.push(file);
                }
            }
            
            // Atualizar a lista de arquivos
            updateFilesList();
            
            // Ativar o botão de envio se há arquivos na fila
            submitBtn.disabled = queuedFiles.length === 0;
        }
    }
    
    // Limpar a fila de arquivos
    if (clearQueueBtn) {
        clearQueueBtn.addEventListener('click', () => {
            queuedFiles = [];
            updateFilesList();
            submitBtn.disabled = true;
        });
    }
    
    // Event listener para envio do formulário
    uploadForm.addEventListener('submit', handleFormSubmit);
}

/**
 * Atualiza a lista visual de arquivos na fila
 */
function updateFilesList() {
    const filesList = document.getElementById('files-list');
    const queueTitle = document.getElementById('queue-title');
    const queueCount = document.getElementById('queue-count');
    const clearQueueBtn = document.getElementById('clear-queue-btn');
    
    if (!filesList) return;
    
    // Atualizar título e contador
    if (queueTitle) {
        queueTitle.style.display = queuedFiles.length > 0 ? 'block' : 'none';
    }
    
    if (queueCount) {
        queueCount.textContent = queuedFiles.length;
    }
    
    if (clearQueueBtn) {
        clearQueueBtn.style.display = queuedFiles.length > 0 ? 'inline-block' : 'none';
    }
    
    // Limpar e atualizar a lista
    filesList.innerHTML = '';
    
    queuedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.classList.add('file-item');
        
        // Determinar ícone baseado no tipo
        let iconClass = 'fas fa-file-audio';
        if (file.type.includes('video')) {
            iconClass = 'fas fa-file-video';
        }
        
        // Formatar tamanho
        const fileSize = formatFileSize(file.size);
        
        fileItem.innerHTML = `
            <div class="file-icon">
                <i class="${iconClass}"></i>
            </div>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${fileSize}</div>
            </div>
            <div class="file-actions">
                <button type="button" class="btn btn-sm btn-danger remove-file" data-index="${index}">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;
        
        filesList.appendChild(fileItem);
        
        // Event listener para remover arquivo
        const removeBtn = fileItem.querySelector('.remove-file');
        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                queuedFiles.splice(index, 1);
                updateFilesList();
                
                // Atualizar estado do botão de envio
                const submitBtn = document.getElementById('submit-btn');
                if (submitBtn) {
                    submitBtn.disabled = queuedFiles.length === 0;
                }
            });
        }
    });
}

/**
 * Lida com o envio do formulário
 */
async function handleFormSubmit(e) {
    e.preventDefault();
    
    if (queuedFiles.length === 0) {
        showAlert('Por favor, selecione pelo menos um arquivo para transcrever.', 'warning');
        return;
    }
    
    if (isProcessing) {
        showAlert('Já existe uma transcrição em andamento. Aguarde a conclusão.', 'warning');
        return;
    }
    
    // Obter valores do formulário
    const model = document.getElementById('model').value;
    // Definir padrões para os valores removidos
    const languageMode = 'auto';
    const language = 'pt';
    const exportFormats = 'pdf';
    const queueMode = true; // Sempre usar modo fila para múltiplos arquivos
    
    isProcessing = true;
    
    // Mostrar indicador de carregamento
    const submitBtn = document.getElementById('submit-btn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enviando...';
    submitBtn.disabled = true;
    
    // Criar promessas para cada arquivo
    const uploadPromises = [];
    
    for (const file of queuedFiles) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('model', model);
        formData.append('language_mode', languageMode);
        formData.append('language', language);
        formData.append('queue_mode', queueMode);
        formData.append('export_formats', exportFormats);
        
        uploadPromises.push(
            fetch('/transcribe', {
                method: 'POST',
                body: formData
            }).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
        );
    }
    
    try {
        // Enviar todos os arquivos
        const results = await Promise.all(uploadPromises);
        
        // Processar resultados
        if (results.length > 0) {
            showAlert(`${results.length} arquivo(s) adicionado(s) à fila de transcrição.`, 'success');
            
            // Iniciar polling para o primeiro resultado
            activeTaskId = results[0].task_id;
            startProgressPolling(activeTaskId);
            
            // Limpar a fila visual depois de enviar
            queuedFiles = [];
            updateFilesList();
            
            // Mudar para a tela de progresso
            document.getElementById('upload-section').style.display = 'none';
            document.getElementById('progress-section').style.display = 'block';
        }
    } catch (error) {
        console.error('Erro ao enviar arquivos:', error);
        showAlert('Ocorreu um erro ao enviar os arquivos. Por favor, tente novamente.', 'error');
        
        isProcessing = false;
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
    }
}

/**
 * Inicia o polling para verificar o progresso da transcrição
 */
function startProgressPolling(taskId) {
    if (isPolling) return;
    
    isPolling = true;
    
    // Mostrar a seção de progresso
    const progressSection = document.getElementById('progress-section');
    if (progressSection) {
        progressSection.style.display = 'block';
    }
    
    // Configurar elementos de progresso
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const progressStep = document.getElementById('progress-step');
    const queueStatus = document.getElementById('queue-status');
    const timeEstimate = document.getElementById('time-estimate');
    
    if (progressBar) progressBar.style.width = '0%';
    if (progressText) progressText.textContent = '0%';
    
    // Limpar intervalo anterior se existir
    if (pollInterval) clearInterval(pollInterval);
    
    // Verificar o progresso a cada 2 segundos
    pollInterval = setInterval(() => pollProgress(taskId), 2000);
    
    /**
     * Função para verificar o progresso
     */
    async function pollProgress(taskId) {
        try {
            const response = await fetch(`/progress/${taskId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Atualizar a barra de progresso
            if (progressBar) progressBar.style.width = `${data.progress}%`;
            if (progressText) progressText.textContent = `${data.progress}%`;
            if (progressStep) progressStep.textContent = data.step || '';
            
            // Atualizar status da fila
            if (queueStatus && data.queue_status && data.queue_status !== 'none') {
                queueStatus.style.display = 'block';
                
                if (data.queue_status === 'queued' && data.queue_position) {
                    queueStatus.textContent = `Aguardando na fila (posição ${data.queue_position})`;
                } else if (data.queue_status === 'processing') {
                    queueStatus.textContent = 'Processando da fila';
                }
            } else if (queueStatus) {
                queueStatus.style.display = 'none';
            }
            
            // Atualizar estimativa de tempo
            if (timeEstimate && data.formatted_time) {
                timeEstimate.style.display = 'block';
                timeEstimate.textContent = `Tempo estimado: ${data.formatted_time}`;
            } else if (timeEstimate) {
                timeEstimate.style.display = 'none';
            }
            
            // Verificar se a transcrição está completa
            if (data.status === 'completed') {
                clearInterval(pollInterval);
                isPolling = false;
                
                // Exibir resultado
                showResult(data.text, data.detected_language);
                
                // Verificar se há mais arquivos na fila
                checkQueueStatus();
            }
            
            // Verificar se houve erro
            if (data.status === 'error') {
                clearInterval(pollInterval);
                isPolling = false;
                
                showAlert(`Erro na transcrição: ${data.error}`, 'error');
                
                // Voltar à tela de upload
                document.getElementById('progress-section').style.display = 'none';
                document.getElementById('upload-section').style.display = 'block';
                
                // Verificar se há mais arquivos na fila
                checkQueueStatus();
            }
            
        } catch (error) {
            console.error('Erro ao verificar progresso:', error);
            
            // Se houver erro, parar o polling após algumas tentativas
            pollErrorCount++;
            
            if (pollErrorCount > 5) {
                clearInterval(pollInterval);
                isPolling = false;
                showAlert('Erro ao verificar o progresso da transcrição.', 'error');
            }
        }
    }
}

/**
 * Verificar o status da fila para ver se há mais arquivos para processar
 */
async function checkQueueStatus() {
    try {
        const response = await fetch('/queue_status');
        if (!response.ok) throw new Error('Falha ao verificar status da fila');
        
        const data = await response.json();
        
        // Se houver mais itens na fila, iniciar o polling para o próximo
        if (data.has_items && data.next_task_id) {
            activeTaskId = data.next_task_id;
            
            // Aguardar um pouco antes de iniciar o próximo polling
            setTimeout(() => {
                startProgressPolling(activeTaskId);
            }, 2000);
        } else {
            // Não há mais itens na fila
            activeTaskId = null;
            isProcessing = false;
            
            // Recarregar a lista de PDFs
            loadPDFs();
        }
    } catch (error) {
        console.error('Erro ao verificar status da fila:', error);
    }
}

/**
 * Mostra o resultado da transcrição
 */
function showResult(text, detectedLanguage) {
    const resultSection = document.getElementById('result-section');
    const transcriptionText = document.getElementById('transcription-text');
    const detectedLangEl = document.getElementById('detected-language');
    
    if (resultSection && transcriptionText) {
        // Mostrar a seção de resultado
        resultSection.style.display = 'block';
        
        // Preencher o texto
        transcriptionText.textContent = text;
        
        // Mostrar idioma detectado
        if (detectedLangEl && detectedLanguage) {
            detectedLangEl.textContent = detectedLanguage;
            detectedLangEl.parentElement.style.display = 'block';
        }
        
        // Rolar para a seção de resultado
        resultSection.scrollIntoView({ behavior: 'smooth' });
    }
}

/**
 * Verifica se há transcrições incompletas
 */
async function checkIncompleteTranscriptions() {
    try {
        const response = await fetch('/queue_status');
        if (!response.ok) throw new Error('Falha ao verificar transcrições incompletas');
        
        const data = await response.json();
        
        // Se houver tarefas ativas, verificar status e mostrar progresso
        if (data.active_tasks > 0 || data.has_items) {
            // Mostrar notificação
            showAlert('Existem transcrições em andamento ou na fila.', 'info');
            
            if (data.active_tasks > 0) {
                // Buscar a tarefa ativa
                const activeTask = await getCurrentActiveTask();
                if (activeTask) {
                    activeTaskId = activeTask.task_id;
                    startProgressPolling(activeTaskId);
                }
            } else if (data.has_items && data.next_task_id) {
                // Iniciar a próxima da fila
                activeTaskId = data.next_task_id;
                startProgressPolling(activeTaskId);
            }
        }
    } catch (error) {
        console.error('Erro ao verificar transcrições incompletas:', error);
    }
}

/**
 * Busca a tarefa atualmente ativa
 */
async function getCurrentActiveTask() {
    try {
        const response = await fetch('/transcriptions?limit=1');
        if (!response.ok) throw new Error('Falha ao buscar transcrições');
        
        const data = await response.json();
        
        if (data.transcriptions && data.transcriptions.length > 0) {
            return data.transcriptions[0];
        }
        
        return null;
    } catch (error) {
        console.error('Erro ao buscar tarefa ativa:', error);
        return null;
    }
}

/**
 * Carrega a lista de PDFs gerados
 */
async function loadPDFs() {
    const pdfsList = document.getElementById('pdfs-list');
    if (!pdfsList) return;
    
    try {
        const response = await fetch('/pdfs');
        if (!response.ok) throw new Error('Falha ao carregar PDFs');
        
        const data = await response.json();
        
        // Limpar a lista
        pdfsList.innerHTML = '';
        
        // Adicionar PDFs à lista
        if (data.pdfs && data.pdfs.length > 0) {
            data.pdfs.forEach(pdf => {
                const listItem = document.createElement('div');
                listItem.classList.add('list-item');
                
                const fileName = pdf.filename;
                const fileSize = formatFileSize(pdf.size);
                const date = new Date(pdf.created_at).toLocaleString();
                
                listItem.innerHTML = `
                    <div class="file-icon">
                        <i class="fas fa-file-pdf"></i>
                    </div>
                    <div class="file-info">
                        <div class="file-name">${fileName}</div>
                        <div class="file-meta">${fileSize} • ${date}</div>
                    </div>
                    <div class="file-actions">
                        <a href="/pdfs/${fileName}" class="btn btn-sm btn-outline" download>
                            <i class="fas fa-download"></i> Baixar
                        </a>
                    </div>
                `;
                
                pdfsList.appendChild(listItem);
            });
            
            // Mostrar seção de PDFs
            const pdfsSection = document.getElementById('pdfs-section');
            if (pdfsSection) pdfsSection.style.display = 'block';
        } else {
            pdfsList.innerHTML = '<div class="alert alert-info">Nenhum PDF encontrado.</div>';
        }
    } catch (error) {
        console.error('Erro ao carregar PDFs:', error);
        pdfsList.innerHTML = '<div class="alert alert-danger">Erro ao carregar PDFs.</div>';
    }
}

/**
 * Mostra um alerta para o usuário
 */
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alerts-container');
    if (!alertsContainer) return;
    
    const alertEl = document.createElement('div');
    alertEl.classList.add('alert', `alert-${type}`);
    alertEl.textContent = message;
    
    // Adicionar ícone baseado no tipo
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'warning') icon = 'exclamation-triangle';
    if (type === 'error') icon = 'times-circle';
    
    alertEl.innerHTML = `<i class="fas fa-${icon}"></i> ${message}`;
    
    // Adicionar botão para fechar
    const closeBtn = document.createElement('button');
    closeBtn.classList.add('close-alert');
    closeBtn.innerHTML = '&times;';
    closeBtn.addEventListener('click', () => alertEl.remove());
    alertEl.appendChild(closeBtn);
    
    // Adicionar ao container
    alertsContainer.appendChild(alertEl);
    
    // Auto-remover após 5 segundos
    setTimeout(() => {
        alertEl.classList.add('fade-out');
        setTimeout(() => alertEl.remove(), 500);
    }, 5000);
}

/**
 * Formata o tamanho do arquivo para exibição
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Exporta a transcrição atual para um formato
 */
function exportTranscription(format) {
    // TODO: Implementar exportação em diferentes formatos
    showAlert(`Exportação para ${format.toUpperCase()} em desenvolvimento.`, 'info');
}

/**
 * Copia o texto da transcrição para a área de transferência
 */
function copyTranscriptionText() {
    const transcriptionText = document.getElementById('transcription-text');
    if (!transcriptionText) return;
    
    navigator.clipboard.writeText(transcriptionText.textContent)
        .then(() => {
            showAlert('Texto copiado para a área de transferência.', 'success');
        })
        .catch(err => {
            console.error('Erro ao copiar texto:', err);
            showAlert('Erro ao copiar texto.', 'error');
        });
} 