from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime
import pytz

_logger = logging.getLogger(__name__)


class ChatbotController(http.Controller):

    @http.route('/ai_analytics/chat', type='json', auth='user', methods=['POST'])
    def chat_message(self, message, session_id=None, model='claude'):
        """Handle chatbot messages from the web interface"""
        try:
            chatbot_model = request.env['ai.chatbot']
            result = chatbot_model.send_message(message, session_id, model)
            return result
        except Exception as e:
            _logger.error(f"Chat controller error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': 'An error occurred while processing your message.'
            }

    @http.route('/ai_analytics/recent_chats', type='json', auth='user', methods=['POST'])
    def get_recent_chats(self, **kwargs):
        """Get recent chat sessions for the current user"""
        try:
            chats = request.env['ai.chatbot'].search([
                ('user_id', '=', request.env.user.id)
            ], order='create_date desc', limit=20)
            
            chat_list = []
            for chat in chats:
                # Get the first user message as preview
                first_message = chat.messages.filtered(lambda m: m.is_user).sorted('timestamp')
                preview = first_message[0].message if len(first_message) > 0 else "New Chat"
                
                # Convert UTC to user timezone if needed
                
                # Get user timezone (default to UTC if not available)
                user_tz = request.env.user.tz or 'UTC'
                user_timezone = pytz.timezone(user_tz)
                
                # Convert chat creation time to user timezone with enhanced formatting
                if chat.create_date:
                    # Odoo stores dates in UTC
                    utc_time = chat.create_date.replace(tzinfo=pytz.UTC)
                    local_time = utc_time.astimezone(user_timezone)
                    
                    # Calculate time difference for smart formatting
                    now = datetime.now(user_timezone)
                    time_diff = now - local_time
                    
                    if time_diff.days == 0:
                        # Today - show time only
                        formatted_date = local_time.strftime('%I:%M %p')
                    elif time_diff.days == 1:
                        # Yesterday
                        formatted_date = f"Yesterday {local_time.strftime('%I:%M %p')}"
                    elif time_diff.days < 7:
                        # This week - show day
                        formatted_date = local_time.strftime('%A %I:%M %p')
                    elif time_diff.days < 365:
                        # This year - show month/day
                        formatted_date = local_time.strftime('%b %d, %I:%M %p')
                    else:
                        # Older - show full date
                        formatted_date = local_time.strftime('%b %d, %Y %I:%M %p')
                else:
                    formatted_date = 'Unknown'
                
                chat_list.append({
                    'id': chat.id,
                    'name': preview[:30] + '...' if len(preview) > 30 else preview,
                    'date': formatted_date,
                    'date_iso': chat.create_date.isoformat() if chat.create_date else None,
                    'message_count': len(chat.messages)
                })
            
            return {
                'success': True,
                'chats': chat_list
            }
        except Exception as e:
            _logger.error(f"Error getting recent chats: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'chats': []
            }

    @http.route('/ai_analytics/new_chat', type='json', auth='user', methods=['POST'])
    def create_new_chat(self, **kwargs):
        """Create a new chat session"""
        try:
            chat = request.env['ai.chatbot'].create({
                'name': f'Chat {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                'user_id': request.env.user.id
            })
            
            return {
                'success': True,
                'chat_id': chat.id
            }
        except Exception as e:
            _logger.error(f"Error creating new chat: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ai_analytics/load_chat', type='json', auth='user', methods=['POST'])
    def load_chat(self, chat_id, **kwargs):
        """Load messages from a specific chat session"""
        try:
            chat = request.env['ai.chatbot'].browse(int(chat_id))
            if not chat.exists() or chat.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'Chat not found or access denied'
                }
            
            messages = []
            for msg in chat.messages.sorted('timestamp'):
                message_data = {
                    'message': msg.message,
                    'is_user': msg.is_user,
                    'timestamp': msg.timestamp.strftime('%H:%M:%S'),
                    'enhanced': not msg.is_user
                }
                
                # Chart functionality removed - text-based responses only
                
                messages.append(message_data)
            
            return {
                'success': True,
                'messages': messages
            }
        except Exception as e:
            _logger.error(f"Error loading chat: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ai_analytics/delete_chat', type='json', auth='user', methods=['POST'])
    def delete_chat(self, chat_id, **kwargs):
        """Delete a chat session"""
        try:
            chat = request.env['ai.chatbot'].browse(int(chat_id))
            if not chat.exists() or chat.user_id.id != request.env.user.id:
                return {
                    'success': False,
                    'error': 'Chat not found or access denied'
                }
            
            chat.unlink()
            
            return {
                'success': True
            }
        except Exception as e:
            _logger.error(f"Error deleting chat: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }