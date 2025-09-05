{% extends "base.html" %}

{% block title %}Download Processed File | {{ tool_name }} | PDFMaster Pro{% endblock %}

{% block extra_css %}
<style>
    /* Center all messages and content */
    .centered-content {
        display: flex;
        justify-content: center;
        align-items: center;
        text-align: center;
        flex-direction: column;
    }
    
    .download-container {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 30px;
        box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        margin-top: 20px;
        width: 100%;
    }
    
    .file-card {
        background: white;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
        border-left: 4px solid #4e73df;
        transition: transform 0.2s;
        text-align: left;
    }
    
    .file-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .file-info {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
    }
    
    .file-details {
        flex: 1;
        min-width: 300px;
    }
    
    .file-actions {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-top: 15px;
    }
    
    .file-meta {
        font-size: 0.85rem;
        color: #6c757d;
        margin-top: 5px;
    }
    
    .success-icon {
        font-size: 2.5rem;
        color: #1cc88a;
        margin-bottom: 20px;
    }
    
    .cleanup-message {
        text-align: center;
        margin-top: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 5px;
        display: none;
    }
    
    .btn-cleanup {
        background-color: #dc3545;
        color: white;
        border: none;
        padding: 8px 15px;
        border-radius: 4px;
        cursor: pointer;
    }
    
    .btn-cleanup:hover {
        background-color: #c82333;
    }
    
    .btn-delete {
        background-color: #6c757d;
        color: white;
        border: none;
        padding: 8px 12px;
        border-radius: 4px;
        cursor: pointer;
    }
    
    .btn-delete:hover {
        background-color: #5a6268;
    }
    
    .btn-rename {
        background-color: #17a2b8;
        color: white;
        border: none;
        padding: 8px 12px;
        border-radius: 4px;
        cursor: pointer;
    }
    
    .btn-rename:hover {
        background-color: #138496;
    }
    
    .file-size-badge {
        background-color: #e8f0fe;
        color: #4e73df;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .cleanup-info {
        background-color: #f8f9fa;
        border-left: 4px solid #ffc107;
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    #countdown-timer {
        font-weight: bold;
        color: #dc3545;
    }
    
    .file-item {
        transition: opacity 0.5s ease;
    }
    
    .no-files {
        text-align: center;
        padding: 40px;
        color: #6c757d;
        font-style: italic;
    }
    
    /* Modal styles for delete confirmation */
    .modal-overlay {
        display: none;
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.7);
        z-index: 9999;
        justify-content: center;
        align-items: center;
    }
    
    .modal-content {
        background-color: white;
        border-radius: 10px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        text-align: center;
        box-shadow: 0 5px 25px rgba(0, 0, 0, 0.3);
    }
    
    .modal-title {
        color: #dc3545;
        margin-bottom: 15px;
    }
    
    .modal-message {
        margin-bottom: 25px;
        line-height: 1.6;
    }
    
    .countdown-display {
        font-size: 1.5rem;
        font-weight: bold;
        color: #dc3545;
        margin: 15px 0;
    }
    
    .modal-buttons {
        display: flex;
        justify-content: center;
        gap: 15px;
        margin-top: 20px;
    }
    
    .btn-confirm-delete {
        background-color: #dc3545;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
    }
    
    .btn-confirm-delete:hover {
        background-color: #c82333;
    }
    
    .btn-cancel-delete {
        background-color: #6c757d;
        color: white;
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        cursor: pointer;
    }
    
    .btn-cancel-delete:hover {
        background-color: #5a6268;
    }
    
    /* Rename modal styles */
    .rename-modal-content {
        background-color: white;
        border-radius: 10px;
        padding: 30px;
        max-width: 500px;
        width: 90%;
        text-align: center;
        box-shadow: 0 5px 25px rgba(0, 0, 0, 0.3);
    }
    
    .rename-input {
        width: 100%;
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        margin: 15px 0;
        font-size: 1rem;
    }
    
    .rename-input:focus {
        outline: none;
        border-color: #4e73df;
        box-shadow: 0 0 0 2px rgba(78, 115, 223, 0.25);
    }
    
    /* Centered message popup */
    #centered-message {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 10000;
        padding: 20px 30px;
        border-radius: 8px;
        box-shadow: 0 5px 25px rgba(0, 0, 0, 0.3);
        display: none;
        min-width: 300px;
        text-align: center;
    }
    
    /* Button container styling */
    .button-container {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        justify-content: center;
        margin-top: 20px;
    }
    
    @media (max-width: 768px) {
        .file-info {
            flex-direction: column;
            align-items: flex-start;
        }
        
        .file-actions {
            width: 100%;
            flex-direction: column;
            align-items: flex-start;
        }
        
        .cleanup-info {
            flex-direction: column;
            gap: 15px;
            text-align: center;
        }
        
        .modal-buttons {
            flex-direction: column;
        }
        
        .button-container {
            flex-direction: column;
            align-items: center;
        }
    }
</style>
{% endblock %}

{% block content %}
<div class="container py-5">
    <!-- Centered message popup -->
    <div id="centered-message"></div>
    
    <!-- Delete Confirmation Modal -->
    <div id="deleteModal" class="modal-overlay">
        <div class="modal-content">
            <h3 class="modal-title">Delete Confirmation</h3>
            <p class="modal-message">Are you sure you want to delete and clear server data?</p>
            <div class="countdown-display">
                <span id="modal-countdown">5</span> seconds
            </div>
            <div class="modal-buttons">
                <button id="confirmDeleteBtn" class="btn-confirm-delete">Yes, Delete Now</button>
                <button id="cancelDeleteBtn" class="btn-cancel-delete">Cancel</button>
            </div>
        </div>
    </div>
    
    <!-- Rename File Modal -->
    <div id="renameModal" class="modal-overlay">
        <div class="rename-modal-content">
            <h3 class="modal-title">Rename File</h3>
            <p class="modal-message">Enter a new name for the file:</p>
            <input type="text" id="rename-input" class="rename-input" placeholder="Enter new filename">
            <div class="modal-buttons">
                <button id="confirmRenameBtn" class="btn-confirm-delete">Rename</button>
                <button id="cancelRenameBtn" class="btn-cancel-delete">Cancel</button>
            </div>
        </div>
    </div>

    <div class="download-container centered-content">
        <div>
            <div class="success-icon">
                <i class="fas fa-check-circle"></i>
            </div>
            <h1 class="mb-3">Processing Complete</h1>
            <p class="lead">{{ message }}</p>
        </div>

        {% if files %}
        <div class="cleanup-info" id="cleanup-info-section">
            <div>
                <p>Files will be automatically removed from the server in: 
                   <span id="countdown-timer">30m 00s</span>
                </p>
            </div>
            <button id="cleanup-all-btn" class="btn btn-cleanup">
                <i class="fas fa-trash me-1"></i> Clear All Files Now
            </button>
        </div>

        <div class="mt-4" style="width: 100%;">
            <h3 class="mb-4 text-center">Your Processed Files</h3>
            
            {% for file in files %}
            <div class="file-card file-item" id="file-{{ file.name | replace('.', '_') }}">
                <div class="file-info">
                    <div class="file-details">
                        <h5 class="file-name" id="display-name-{{ file.name | replace('.', '_') }}">{{ file.display_name }}</h5>
                        <div class="file-meta">
                            <span class="file-size-badge">{{ file.size }}</span>
                            <span class="ms-2">Processed with: {{ tool_name }}</span>
                        </div>
                        <div class="file-meta mt-1">
                            <i class="fas fa-clock me-1"></i> Processed on: {{ file.processed_time }}
                        </div>
                    </div>
                    
                    <div class="file-actions">
                        <a href="{{ file.url }}" 
                           class="btn btn-primary download-btn" download="{{ file.display_name }}">
                            <i class="fas fa-download me-1"></i> Download
                        </a>
                        <button class="btn btn-rename rename-file-btn" 
                                data-filename="{{ file.name }}" 
                                data-displayname="{{ file.display_name }}">
                            <i class="fas fa-edit me-1"></i> Rename
                        </button>
                        <button class="btn btn-delete delete-file-btn" 
                                data-filename="{{ file.name }}" 
                                data-displayname="{{ file.display_name }}">
                            <i class="fas fa-times me-1"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <div class="alert alert-warning mt-4 text-center" role="alert">
            <i class="fas fa-exclamation-triangle me-2"></i> No processed files available.
        </div>
        {% endif %}

        <div class="button-container">
            {% if tool_id %}
            <a href="{{ url_for('tool_page', tool_id=tool_id) }}" class="btn btn-secondary">
                <i class="fas fa-arrow-left me-1"></i> Back to {{ tool_name }}
            </a>
            {% endif %}
            <a href="{{ url_for('home') }}#tools" class="btn btn-secondary">
                <i class="fas fa-th-large me-1"></i> All Tools
            </a>
            {% if files %}
            <button id="cleanup-data-btn" class="btn btn-cleanup">
                <i class="fas fa-broom me-1"></i> Clear Server Data
            </button>
            {% endif %}
        </div>

        <div id="cleanupMessage" class="cleanup-message text-center">
            <i class="fas fa-check-circle text-success me-2"></i>
            <span>All your temporary files have been successfully cleared.</span>
        </div>

        <div class="mt-4 text-muted small text-center">
            Current Time: <span id="current-time"></span>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script>
    document.addEventListener('DOMContentLoaded', function() {
        // Check if we need to clear files on page load
        const urlParams = new URLSearchParams(window.location.search);
        const clearFiles = urlParams.get('clear_files');
        
        // Store the current files in session storage to show them after refresh
        if (!clearFiles && {% if files %}true{% else %}false{% endif %}) {
            const filesData = {
                files: [
                    {% for file in files %}
                    {
                        name: "{{ file.name }}",
                        display_name: "{{ file.display_name }}",
                        url: "{{ file.url }}",
                        size: "{{ file.size }}",
                        processed_time: "{{ file.processed_time }}"
                    }{% if not loop.last %},{% endif %}
                    {% endfor %}
                ],
                tool_name: "{{ tool_name }}",
                message: "{{ message }}",
                tool_id: "{{ tool_id }}"
            };
            sessionStorage.setItem('processedFiles', JSON.stringify(filesData));
        }
        
        if (clearFiles === 'true') {
            // Clear server files via API call
            fetch('/cleanup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    console.log('Server files cleared on page load');
                    
                    // Clear session storage
                    sessionStorage.removeItem('processedFiles');
                    
                    // Remove the clear_files parameter from URL without refreshing
                    const url = new URL(window.location);
                    url.searchParams.delete('clear_files');
                    window.history.replaceState({}, document.title, url);
                }
            })
            .catch(error => {
                console.error('Error clearing files:', error);
            });
        }
        
        // Update current time
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleString();
        }
        updateTime();
        setInterval(updateTime, 1000);
        
        // Set the expiration time (30 minutes from now)
        const expirationTime = new Date();
        expirationTime.setMinutes(expirationTime.getMinutes() + 30);
        
        // Update the countdown every second
        const countdownElement = document.getElementById('countdown-timer');
        let countdownInterval;
        
        if (countdownElement) {
            countdownInterval = setInterval(updateCountdown, 1000);
        }
        
        function updateCountdown() {
            const now = new Date();
            const timeRemaining = expirationTime - now;
            
            if (timeRemaining <= 0) {
                clearInterval(countdownInterval);
                if (countdownElement) {
                    countdownElement.textContent = 'Files have been automatically removed';
                }
                // Optionally, trigger automatic cleanup
                triggerCleanup();
            } else {
                const minutes = Math.floor(timeRemaining / 60000);
                const seconds = Math.floor((timeRemaining % 60000) / 1000);
                if (countdownElement) {
                    countdownElement.textContent = `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
                }
            }
        }
        
        // Manual cleanup button handler (Clear All Files)
        const cleanupAllBtn = document.getElementById('cleanup-all-btn');
        if (cleanupAllBtn) {
            cleanupAllBtn.addEventListener('click', function() {
                showCenteredMessage('Are you sure you want to remove all files from the server?', 'confirm', function() {
                    triggerCleanup();
                });
            });
        }
        
        // Cleanup data button handler (Clear Server Data)
        const cleanupDataBtn = document.getElementById('cleanup-data-btn');
        if (cleanupDataBtn) {
            cleanupDataBtn.addEventListener('click', function() {
                showCenteredMessage('Are you sure you want to clear all server data?', 'confirm', function() {
                    triggerCleanup();
                });
            });
        }
        
        // Modal functionality for delete confirmation
        const deleteModal = document.getElementById('deleteModal');
        const modalCountdown = document.getElementById('modal-countdown');
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
        let countdownTimer;
        
        // Rename modal functionality
        const renameModal = document.getElementById('renameModal');
        const renameInput = document.getElementById('rename-input');
        const confirmRenameBtn = document.getElementById('confirmRenameBtn');
        const cancelRenameBtn = document.getElementById('cancelRenameBtn');
        let currentRenameFile = null;
        
        function showDeleteModal() {
            // Reset and show the modal
            deleteModal.style.display = 'flex';
            let countdownValue = 5;
            modalCountdown.textContent = countdownValue;
            
            // Start countdown
            countdownTimer = setInterval(function() {
                countdownValue--;
                modalCountdown.textContent = countdownValue;
                
                if (countdownValue <= 0) {
                    clearInterval(countdownTimer);
                    hideDeleteModal();
                }
            }, 1000);
        }
        
        function hideDeleteModal() {
            clearInterval(countdownTimer);
            deleteModal.style.display = 'none';
        }
        
        function showRenameModal(filename, displayName) {
            currentRenameFile = {
                filename: filename,
                displayName: displayName
            };
            
            renameInput.value = displayName.replace('.pdf', '');
            renameModal.style.display = 'flex';
            renameInput.focus();
        }
        
        function hideRenameModal() {
            renameModal.style.display = 'none';
            currentRenameFile = null;
        }
        
        // Individual file rename buttons
        document.querySelectorAll('.rename-file-btn').forEach(button => {
            button.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                const displayName = this.getAttribute('data-displayname');
                showRenameModal(filename, displayName);
            });
        });
        
        // Confirm rename button
        confirmRenameBtn.addEventListener('click', function() {
            const newName = renameInput.value.trim();
            if (!newName) {
                showCenteredMessage('Please enter a filename', 'error');
                return;
            }
            
            renameFile(currentRenameFile.filename, newName);
            hideRenameModal();
        });
        
        // Cancel rename button
        cancelRenameBtn.addEventListener('click', function() {
            hideRenameModal();
        });
        
        // Individual file delete buttons
        document.querySelectorAll('.delete-file-btn').forEach(button => {
            button.addEventListener('click', function() {
                const filename = this.getAttribute('data-filename');
                const displayName = this.getAttribute('data-displayname');
                
                showCenteredMessage(`Are you sure you want to delete "${displayName}"?`, 'confirm', function() {
                    deleteSingleFile(filename, button);
                });
            });
        });
        
        // In your extra_js block, replace the triggerCleanup function with this:

function triggerCleanup() {
    fetch('/cleanup', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Show centered success message
            showCenteredMessage('Files have been removed from the server: ' + data.message, 'success');
            
            // Hide the countdown timer and cleanup info section
            const cleanupInfoSection = document.getElementById('cleanup-info-section');
            if (cleanupInfoSection) {
                cleanupInfoSection.style.display = 'none';
            }
            
            // Hide the Clear Server Data button
            const cleanupDataBtn = document.getElementById('cleanup-data-btn');
            if (cleanupDataBtn) {
                cleanupDataBtn.style.display = 'none';
            }
            
            // Hide the Clean All Files button
            const cleanupAllBtn = document.getElementById('cleanup-all-btn');
            if (cleanupAllBtn) {
                cleanupAllBtn.style.display = 'none';
            }
            
            // Clear the countdown interval
            if (countdownInterval) {
                clearInterval(countdownInterval);
            }
            
            // Show the cleanup message
            const cleanupMessage = document.getElementById('cleanupMessage');
            if (cleanupMessage) {
                cleanupMessage.style.display = 'block';
            }
            
            // Remove all file items from the UI with animation
            document.querySelectorAll('.file-item').forEach(item => {
                item.style.opacity = '0';
                setTimeout(() => item.remove(), 500);
            });
            
            // Update the no files message
            const noFilesAlert = document.querySelector('.alert.alert-warning');
            if (noFilesAlert) {
                noFilesAlert.style.display = 'block';
            }
            
            // Clear any remaining files from the server by refreshing with clear parameter
            setTimeout(() => {
                const url = new URL(window.location.href);
                url.searchParams.set('clear_files', 'true');
                window.location.href = url.toString();
            }, 1000);
        } else {
            showCenteredMessage('Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showCenteredMessage('An error occurred during cleanup', 'error');
    });
}
        
        function deleteSingleFile(filename, buttonElement) {
    fetch(`/cleanup/file/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Remove the file item from the UI
            const fileItem = buttonElement.closest('.file-item');
            fileItem.style.opacity = '0';
            setTimeout(() => fileItem.remove(), 500);
            
            // Check if all files are deleted
            const remainingFiles = document.querySelectorAll('.file-item').length;
            if (remainingFiles === 0) {
                // Hide the countdown timer and cleanup info section
                const cleanupInfoSection = document.getElementById('cleanup-info-section');
                if (cleanupInfoSection) {
                    cleanupInfoSection.style.display = 'none';
                }
                
                // Hide the Clear Server Data button
                const cleanupDataBtn = document.getElementById('cleanup-data-btn');
                if (cleanupDataBtn) {
                    cleanupDataBtn.style.display = 'none';
                }
                
                // Hide the Clean All Files button
                const cleanupAllBtn = document.getElementById('cleanup-all-btn');
                if (cleanupAllBtn) {
                    cleanupAllBtn.style.display = 'none';
                }
                
                // Clear the countdown interval
                if (countdownInterval) {
                    clearInterval(countdownInterval);
                }
                
                // Show the cleanup message
                const cleanupMessage = document.getElementById('cleanupMessage');
                if (cleanupMessage) {
                    cleanupMessage.style.display = 'block';
                }
                
                // Update the no files message
                const noFilesAlert = document.querySelector('.alert.alert-warning');
                if (noFilesAlert) {
                    noFilesAlert.style.display = 'block';
                }
                
                // Refresh to ensure server files are cleared
                setTimeout(() => {
                    const url = new URL(window.location.href);
                    url.searchParams.set('clear_files', 'true');
                    window.location.href = url.toString();
                }, 1000);
            }
            
            // Show success message
            showCenteredMessage('File has been deleted: ' + data.message, 'success');
        } else {
            showCenteredMessage('Error: ' + data.error, 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showCenteredMessage('An error occurred while deleting the file', 'error');
    });
}
        
        function renameFile(filename, newName) {
            fetch(`/rename/file/${encodeURIComponent(filename)}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ new_name: newName })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update the UI with the new filename
                    const fileElement = document.getElementById(`file-${filename.replace('.', '_')}`);
                    const displayNameElement = document.getElementById(`display-name-${filename.replace('.', '_')}`);
                    const downloadButton = fileElement.querySelector('.download-btn');
                    
                    if (displayNameElement) {
                        displayNameElement.textContent = data.new_name;
                    }
                    
                    if (downloadButton) {
                        downloadButton.setAttribute('download', data.new_name);
                        downloadButton.setAttribute('href', data.new_url);
                    }
                    
                    // Update the button data attributes
                    const renameButton = fileElement.querySelector('.rename-file-btn');
                    const deleteButton = fileElement.querySelector('.delete-file-btn');
                    
                    if (renameButton) {
                        renameButton.setAttribute('data-displayname', data.new_name);
                    }
                    
                    if (deleteButton) {
                        deleteButton.setAttribute('data-displayname', data.new_name);
                    }
                    
                    // Show success message
                    showCenteredMessage('File has been renamed: ' + data.message, 'success');
                } else {
                    showCenteredMessage('Error: ' + data.error, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showCenteredMessage('An error occurred while renaming the file', 'error');
            });
        }
        
        // Function to show centered messages
        function showCenteredMessage(message, type, callback) {
            const messageEl = document.getElementById('centered-message');
            
            // Set message content and styling
            messageEl.textContent = message;
            
            if (type === 'success') {
                messageEl.className = 'alert alert-success';
                messageEl.style.display = 'block';
                
                // Hide after 3 seconds
                setTimeout(() => {
                    messageEl.style.display = 'none';
                }, 3000);
            } 
            else if (type === 'error') {
                messageEl.className = 'alert alert-danger';
                messageEl.style.display = 'block';
                
                // Hide after 5 seconds
                setTimeout(() => {
                    messageEl.style.display = 'none';
                }, 5000);
            }
            else if (type === 'confirm') {
                messageEl.className = 'alert alert-warning';
                messageEl.innerHTML = `
                    <p>${message}</p>
                    <div class="mt-3">
                        <button id="confirm-yes" class="btn btn-sm btn-danger me-2">Yes</button>
                        <button id="confirm-no" class="btn btn-sm btn-secondary">Cancel</button>
                    </div>
                `;
                messageEl.style.display = 'block';
                
                // Add event listeners to buttons
                document.getElementById('confirm-yes').addEventListener('click', function() {
                    messageEl.style.display = 'none';
                    if (callback) callback();
                });
                
                document.getElementById('confirm-no').addEventListener('click', function() {
                    messageEl.style.display = 'none';
                });
            }
        }
        
        // Initial countdown update
        if (countdownElement) {
            updateCountdown();
        }
        
        // Check if we need to redirect to clear files on refresh
        window.addEventListener('beforeunload', function() {
            const clearFilesOnLoad = sessionStorage.getItem('clearFilesOnLoad');
            if (clearFilesOnLoad === 'true') {
                // Remove the flag
                sessionStorage.removeItem('clearFilesOnLoad');
                
                // Set a URL parameter to trigger cleanup on next load
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('clear_files', 'true');
                window.location.href = currentUrl.toString();
            }
        });
    });
</script>
{% endblock %}