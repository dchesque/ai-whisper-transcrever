/**
 * TranscreveAI - Script principal da aplicação
 */

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar upload de arquivos
    initFileUpload();
});

/**
 * Inicializa o upload de arquivos
 */
function initFileUpload() {
    const fileInput = document.getElementById('fileInput');
    const dropZone = document.getElementById('dropZone');
    const transcribeButton = document.getElementById('transcribeButton');
    const resultContainer = document.getElementById('resultContainer');
    const resultText = document.getElementById('resultText');
    
    if (!fileInput || !dropZone || !transcribeButton) return;
    
    // Botão para selecionar arquivo
    dropZone.querySelector('button').addEventListener('click', () => {
        fileInput.click();
    });
    
    // Event listener para seleção de arquivo
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            // Mostrar nome do arquivo
            const fileName = document.createElement('p');
            fileName.textContent = `Arquivo selecionado: ${file.name}`;
            fileName.classList.add('upload-description');
            
            const existingDesc = dropZone.querySelector('.upload-description');
            if (existingDesc) {
                dropZone.replaceChild(fileName, existingDesc);
            }
            
            // Ativar o botão de transcrição
            transcribeButton.disabled = false;
        }
    });
    
    // Eventos de drag & drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('drag-over');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('drag-over');
        }, false);
    });
    
    // Lidar com soltar o arquivo
    dropZone.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files[0];
        if (file) {
            fileInput.files = e.dataTransfer.files;
            
            // Mostrar nome do arquivo
            const fileName = document.createElement('p');
            fileName.textContent = `Arquivo selecionado: ${file.name}`;
            fileName.classList.add('upload-description');
            
            const existingDesc = dropZone.querySelector('.upload-description');
            if (existingDesc) {
                dropZone.replaceChild(fileName, existingDesc);
            }
            
            // Ativar o botão de transcrição
            transcribeButton.disabled = false;
        }
    }, false);
    
    // Event listener para botão de transcrição
    transcribeButton.addEventListener('click', async () => {
        const file = fileInput.files[0];
        const language = document.getElementById('language').value;
        
        if (!file) {
            alert('Por favor, selecione um arquivo para transcrever.');
            return;
        }
        
        // Desativar botão durante o processamento
        transcribeButton.disabled = true;
        transcribeButton.textContent = 'Processando...';
        
        // Criar FormData para envio
        const formData = new FormData();
        formData.append('file', file);
        formData.append('language', language);
        
        try {
            // Enviar para o backend
            const response = await fetch('/transcribe', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro durante a transcrição');
            }
            
            const data = await response.json();
            
            // Mostrar resultado
            resultText.textContent = data.text;
            resultContainer.style.display = 'block';
            
            // Armazenar o nome do PDF para download
            resultContainer.dataset.pdfFilename = data.pdf_filename;
            
            // Habilitar botões de download
            document.querySelector('.download-button-container').style.display = 'flex';
            
            // Resetar botão
            transcribeButton.textContent = 'Transcrever';
            transcribeButton.disabled = false;
            
            // Rolar para o resultado
            resultContainer.scrollIntoView({ behavior: 'smooth' });
            
            // Atualizar a lista de PDFs se necessário
            setTimeout(() => {
                location.reload();
            }, 2000);
            
        } catch (error) {
            console.error('Erro ao transcrever arquivo:', error);
            alert('Ocorreu um erro ao processar o arquivo: ' + error.message);
            
            // Resetar botão
            transcribeButton.textContent = 'Transcrever';
            transcribeButton.disabled = false;
        }
    });
    
    // Download de TXT
    const downloadTxtBtn = document.getElementById('downloadTxt');
    if (downloadTxtBtn) {
        downloadTxtBtn.addEventListener('click', () => {
            const text = resultText.textContent;
            const filename = 'transcricao.txt';
            
            const element = document.createElement('a');
            element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
            element.setAttribute('download', filename);
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        });
    }
    
    // Download de PDF
    const downloadPdfBtn = document.getElementById('downloadPdf');
    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener('click', () => {
            const pdfFilename = resultContainer.dataset.pdfFilename;
            if (pdfFilename) {
                window.location.href = `/download_pdf/${pdfFilename}`;
            } else {
                alert('PDF não disponível');
            }
        });
    }
} 