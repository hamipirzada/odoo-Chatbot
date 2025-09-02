/** @odoo-module */

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class ChatbotWidget extends Component {
    static template = "ai_analytics.ChatbotWidget";

    setup() {
        this.rpc = useService("rpc");
        this.state = useState({
            messages: [],
            isTyping: false,
            sessionId: null,
            currentChatId: null,
            recentChats: [],
            sidebarCollapsed: false,
            selectedModel: 'claude',
        });
        
        this.messageInput = useRef("messageInput");
        this.messagesContainer = useRef("messagesContainer");
        this.modelSelect = useRef("modelSelect");

        onMounted(() => {
            this.loadRecentChats();
            this.addWelcomeMessage();
            
            // Chart functionality removed - text-based responses only
            
            // Initialize sidebar CSS classes and input field width
            setTimeout(() => {
                const container = document.querySelector('.ai-chatbot-container');
                if (container) {
                    if (this.state.sidebarCollapsed) {
                        container.classList.add('sidebar-collapsed');
                    } else {
                        container.classList.add('sidebar-visible');
                    }
                }
                
                // Set initial input field width
                this.adjustInputFieldWidth();
                
                // Add window resize handler
                window.addEventListener('resize', () => {
                    this.adjustInputFieldWidth();
                });
            }, 100);
        });
        
        // Chart bindings removed
    }
    
    // Chart functionality removed - text-based responses only

    addWelcomeMessage() {
        const welcomeMessage = {
            message: `Hello! I'm your AI Business Intelligence assistant.

I can help you analyze your business data, generate insights, and answer questions about your:
• Sales performance and revenue trends
• Customer behavior and analytics  
• Inventory levels and product performance
• Financial reports and business metrics

How can I assist you with your business analytics today?`,
            is_user: false,
            timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
        };
        
        this.state.messages.push(welcomeMessage);
    }

    async sendMessage() {
        const message = this.messageInput.el.value.trim();
        if (!message) return;

        // Add user message
        this.state.messages.push({
            message: message,
            is_user: true,
            timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})
        });

        // Clear input and show typing
        this.messageInput.el.value = '';
        this.state.isTyping = true;
        this.scrollToBottom();

        try {
            const response = await this.rpc("/ai_analytics/chat", {
                message: message,
                session_id: this.state.sessionId,
                model: this.state.selectedModel
            });

            this.state.isTyping = false;

            if (response.success) {
                this.state.sessionId = response.session_id;
                const botMessage = {
                    message: response.response,
                    is_user: false,
                    timestamp: response.timestamp,
                    enhanced: true,
                    model: this.state.selectedModel
                };
                this.state.messages.push(botMessage);
                
                // Chart functionality removed - text-based responses only
            } else {
                this.state.messages.push({
                    message: response.response || "Sorry, I couldn't process your request.",
                    is_user: false,
                    timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
                    error: true
                });
            }
        } catch (error) {
            this.state.isTyping = false;
            this.state.messages.push({
                message: "Connection error. Please try again.",
                is_user: false,
                timestamp: new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}),
                error: true
            });
        }

        this.scrollToBottom();
    }

    // Chart functionality removed - text-based responses only
    
    // Chart functionality removed - text-based responses only
    
    // Chart functionality removed - text-based responses only

    onKeyPress(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    onModelChange(event) {
        this.state.selectedModel = event.target.value;
    }


    scrollToBottom() {
        setTimeout(() => {
            if (this.messagesContainer.el) {
                this.messagesContainer.el.scrollTop = this.messagesContainer.el.scrollHeight;
            }
        }, 100);
    }

    clearCurrentChat() {
        this.state.messages = [];
        this.state.sessionId = null;
        this.addWelcomeMessage();
    }

    // Sidebar Management
    toggleSidebar() {
        this.state.sidebarCollapsed = !this.state.sidebarCollapsed;
        
        // Update CSS classes for responsive input field
        const container = document.querySelector('.ai-chatbot-container');
        if (container) {
            if (this.state.sidebarCollapsed) {
                container.classList.add('sidebar-collapsed');
                container.classList.remove('sidebar-visible');
            } else {
                container.classList.add('sidebar-visible');
                container.classList.remove('sidebar-collapsed');
            }
        }
        
        // Force input field to recalculate its width after sidebar transition
        setTimeout(() => {
            this.adjustInputFieldWidth();
        }, 300); // Wait for CSS transition to complete
    }
    
    adjustInputFieldWidth() {
        // Input field width is handled by CSS flexbox layout within ai-chatbot-main
        // No manual width adjustment needed
        console.log('Input field uses flexbox responsive layout');
    }

    // Chat Management
    async loadRecentChats() {
        try {
            const response = await this.rpc("/ai_analytics/recent_chats", {});
            if (response.success) {
                this.state.recentChats = response.chats;
            }
        } catch (error) {
            console.error('Error loading recent chats:', error);
        }
    }

    async startNewChat() {
        try {
            const response = await this.rpc("/ai_analytics/new_chat", {});
            if (response.success) {
                this.state.currentChatId = response.chat_id;
                this.state.sessionId = response.chat_id;
                this.state.messages = [];
                this.addWelcomeMessage();
                await this.loadRecentChats();
            }
        } catch (error) {
            console.error('Error starting new chat:', error);
        }
    }

    async loadChat(chatId) {
        try {
            const response = await this.rpc("/ai_analytics/load_chat", {
                chat_id: chatId
            });
            if (response.success) {
                this.state.currentChatId = chatId;
                this.state.sessionId = chatId;
                this.state.messages = response.messages;
                
                this.scrollToBottom();
                
                // Chart functionality removed - text-based responses only
            }
        } catch (error) {
            console.error('Error loading chat:', error);
        }
    }
    
    // Chart functionality removed - text-based responses only

    async deleteChat(chatId) {
        if (confirm('Are you sure you want to delete this chat?')) {
            try {
                const response = await this.rpc("/ai_analytics/delete_chat", {
                    chat_id: chatId
                });
                if (response.success) {
                    // If we're deleting the current chat, start a new one
                    if (this.state.currentChatId === chatId) {
                        await this.startNewChat();
                    }
                    await this.loadRecentChats();
                }
            } catch (error) {
                console.error('Error deleting chat:', error);
            }
        }
    }
    
    // Enhanced timestamp formatting
    formatTimestamp(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        // If it's today, show time
        if (diffDays === 0) {
            return date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
        }
        // If it's yesterday
        else if (diffDays === 1) {
            return `Yesterday ${date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            })}`;
        }
        // If it's within the last week
        else if (diffDays < 7) {
            const weekdays = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
            return `${weekdays[date.getDay()]} ${date.toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            })}`;
        }
        // Otherwise show full date
        else {
            return date.toLocaleDateString([], {
                month: 'short',
                day: 'numeric',
                year: diffDays > 365 ? 'numeric' : undefined,
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
        }
    }
    
    // Enhanced chat date formatting for sidebar
    formatChatDate(dateString) {
        if (!dateString || dateString === 'Unknown') return dateString;
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        // Just now (< 1 minute)
        if (diffMins < 1) {
            return 'Just now';
        }
        // Minutes ago (< 1 hour)
        else if (diffMins < 60) {
            return `${diffMins}m ago`;
        }
        // Hours ago (< 24 hours)
        else if (diffHours < 24) {
            return `${diffHours}h ago`;
        }
        // Days ago (< 7 days)
        else if (diffDays < 7) {
            return `${diffDays}d ago`;
        }
        // Weeks ago (< 30 days)
        else if (diffDays < 30) {
            const weeks = Math.floor(diffDays / 7);
            return `${weeks}w ago`;
        }
        // Months ago
        else {
            const months = Math.floor(diffDays / 30);
            return `${months}mo ago`;
        }
    }
}

registry.category("actions").add("ai_analytics.chatbot_action", ChatbotWidget);