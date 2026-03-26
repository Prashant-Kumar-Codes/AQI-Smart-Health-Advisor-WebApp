/**
 * Unified Message Manager
 * Handles both Flask flash messages and JavaScript messages
 * Prevents conflicts and ensures consistent UX
 */

// Only create if not already defined (prevents duplicate errors)
if (typeof window.MessageManager === 'undefined') {
    
    window.MessageManager = {
        // Configuration
        MESSAGE_DURATION: 4000,
        MAX_MESSAGES: 3,
        
        // Message queue
        messageQueue: [],
        activeMessages: 0,
        
        /**
         * Show a message
         * @param {string} text - Message text
         * @param {string} type - Message type (success, error, warning, info)
         * @param {number} duration - Display duration in ms (optional)
         */
        show(text, type = 'info', duration = null) {
            // Prevent duplicate messages
            if (this.isDuplicate(text)) {
                console.log('Skipping duplicate message:', text);
                return;
            }
            
            const message = {
                id: Date.now() + Math.random(),
                text: text,
                type: type,
                duration: duration || this.MESSAGE_DURATION
            };
            
            this.messageQueue.push(message);
            this.processQueue();
        },
        
        /**
         * Check if message is duplicate
         * @param {string} text - Message text
         * @returns {boolean}
         */
        isDuplicate(text) {
            const existing = document.querySelectorAll('.message-toast');
            for (let el of existing) {
                if (el.textContent.includes(text)) {
                    return true;
                }
            }
            return false;
        },
        
        /**
         * Process message queue
         */
        processQueue() {
            if (this.activeMessages >= this.MAX_MESSAGES || this.messageQueue.length === 0) {
                return;
            }
            
            const message = this.messageQueue.shift();
            this.displayMessage(message);
        },
        
        /**
         * Display a message
         * @param {Object} message - Message object
         */
        displayMessage(message) {
            this.activeMessages++;
            
            // Create container if it doesn't exist
            let container = document.getElementById('message-container');
            if (!container) {
                container = this.createContainer();
                document.body.appendChild(container);
            }
            
            // Create message element
            const messageEl = document.createElement('div');
            messageEl.className = `message-toast message-${message.type}`;
            messageEl.setAttribute('data-id', message.id);
            
            // Icon based on type
            const icon = this.getIcon(message.type);
            
            messageEl.innerHTML = `
                <div class="message-icon">${icon}</div>
                <div class="message-text">${message.text}</div>
                <button class="message-close" onclick="window.MessageManager.dismiss('${message.id}')">&times;</button>
            `;
            
            // Add to container
            container.appendChild(messageEl);
            
            // Trigger animation
            setTimeout(() => messageEl.classList.add('show'), 10);
            
            // Auto-dismiss
            setTimeout(() => {
                this.dismiss(message.id);
            }, message.duration);
        },
        
        /**
         * Dismiss a message
         * @param {string} messageId - Message ID
         */
        dismiss(messageId) {
            const messageEl = document.querySelector(`[data-id="${messageId}"]`);
            if (!messageEl) return;
            
            messageEl.classList.remove('show');
            messageEl.classList.add('hide');
            
            setTimeout(() => {
                messageEl.remove();
                this.activeMessages--;
                this.processQueue();
            }, 300);
        },
        
        /**
         * Get icon for message type
         * @param {string} type - Message type
         * @returns {string} - Icon HTML
         */
        getIcon(type) {
            const icons = {
                success: '✓',
                error: '✕',
                warning: '⚠',
                info: 'ℹ'
            };
            return icons[type] || icons.info;
        },
        
        /**
         * Create message container
         * @returns {HTMLElement}
         */
        createContainer() {
            const container = document.createElement('div');
            container.id = 'message-container';
            container.className = 'message-container';
            
            // Add styles if not present
            if (!document.getElementById('message-styles')) {
                this.injectStyles();
            }
            
            return container;
        },
        
        /**
         * Inject CSS styles
         */
        injectStyles() {
            const style = document.createElement('style');
            style.id = 'message-styles';
            style.textContent = `
                .message-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 2147483647; /* Maximum Z-Index */
                    display: flex;
                    flex-direction: column;
                    gap: 10px;
                    max-width: 400px;
                    pointer-events: none; /* Allows clicks to pass through empty space */
                }
                .message-toast {
                    background: #333;
                    color: #fff;
                    padding: 15px 20px;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                    opacity: 0;
                    transform: translateX(400px);
                    transition: all 0.3s ease-out;
                    pointer-events: auto;   /* Re-enable clicks on the specific message */
                }
                
                .message-toast.show {
                    opacity: 1;
                    transform: translateX(0);
                }
                
                .message-toast.hide {
                    opacity: 0;
                    transform: translateX(400px);
                }
                
                .message-success {
                    background: linear-gradient(135deg, #10b981, #059669);
                }
                
                .message-error {
                    background: linear-gradient(135deg, #ef4444, #dc2626);
                }
                
                .message-warning {
                    background: linear-gradient(135deg, #f59e0b, #d97706);
                }
                
                .message-info {
                    background: linear-gradient(135deg, #3b82f6, #2563eb);
                }
                
                .message-icon {
                    width: 24px;
                    height: 24px;
                    flex-shrink: 0;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 50%;
                    font-weight: bold;
                    font-size: 14px;
                }
                
                .message-text {
                    flex: 1;
                    line-height: 1.4;
                }
                
                .message-close {
                    background: none;
                    border: none;
                    color: white;
                    font-size: 24px;
                    line-height: 1;
                    cursor: pointer;
                    padding: 0;
                    width: 24px;
                    height: 24px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    opacity: 0.7;
                    transition: opacity 0.2s;
                }
                
                .message-close:hover {
                    opacity: 1;
                }
                
                @media (max-width: 768px) {
                    .message-container {
                        top: 10px;
                        right: 10px;
                        left: 10px;
                        max-width: none;
                    }
                    
                    .message-toast {
                        padding: 12px 16px;
                        font-size: 13px;
                    }
                }
            `;
            document.head.appendChild(style);
        },
        
        /**
         * Process Flask flash messages
         */
        processFlaskMessages() {
            const flashElements = document.querySelectorAll('.flash, .alert');
            
            flashElements.forEach(el => {
                // Extract message and type
                const text = el.textContent.trim();
                let type = 'info';
                
                if (el.classList.contains('success')) type = 'success';
                else if (el.classList.contains('error') || el.classList.contains('danger')) type = 'error';
                else if (el.classList.contains('warning')) type = 'warning';
                
                // Show as toast
                this.show(text, type);
                
                // Remove original element
                el.remove();
            });
            
            // Remove flash containers
            const containers = document.querySelectorAll('.flash-container, #flash-messages');
            containers.forEach(c => c.remove());
        },
        
        /**
         * Initialize message system
         */
        initialize() {
            // Process any existing Flask messages
            this.processFlaskMessages();
            
            // Override console methods to catch errors
            const originalError = console.error;
            console.error = (...args) => {
                // Check if it's a user-facing error
                const message = args.join(' ');
                if (message.includes('Error:') && !message.includes('webpack')) {
                    this.show(message, 'error');
                }
                originalError.apply(console, args);
            };
        }
    };
    
    // Auto-initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.MessageManager.initialize();
        });
    } else {
        window.MessageManager.initialize();
    }
    
    console.log('✅ MessageManager loaded');
} else {
    console.log('ℹ️ MessageManager already exists');
}