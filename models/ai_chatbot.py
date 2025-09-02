from odoo import models, fields, api, http
import json
import logging
import requests
import os
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

_logger = logging.getLogger(__name__)


class AIChatbot(models.Model):
    _name = 'ai.chatbot'
    _description = 'AI Chatbot Service'
    _order = 'create_date desc'

    name = fields.Char('Chat Session', default='Chat Session')
    user_id = fields.Many2one('res.users', 'User', default=lambda self: self.env.user)
    messages = fields.One2many('ai.chatbot.message', 'chat_id', 'Messages')
    active = fields.Boolean('Active', default=True)
    session_data = fields.Text('Session Data', help='JSON data for chat session')

    @api.model
    def send_message(self, message, session_id=None, model='claude'):
        """Process user message and return AI response"""
        try:
            # Find or create chat session
            if session_id:
                chat = self.browse(int(session_id))
            else:
                chat = self.create({
                    'name': f'Chat {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                    'user_id': self.env.user.id
                })

            # Create user message record
            user_message = self.env['ai.chatbot.message'].create({
                'chat_id': chat.id,
                'message': message,
                'is_user': True,
                'timestamp': fields.Datetime.now()
            })

            # Generate AI response using selected model
            ai_response = self._generate_ai_response(message, chat.id, model)

            # No charts - text-based analysis only

            # Create AI response record
            ai_message = self.env['ai.chatbot.message'].create({
                'chat_id': chat.id,
                'message': ai_response,
                'is_user': False,
                'timestamp': fields.Datetime.now()
            })

            return {
                'success': True,
                'response': ai_response,
                'session_id': chat.id,
                'message_id': ai_message.id,
                'timestamp': fields.Datetime.now().strftime('%H:%M:%S')
            }

        except Exception as e:
            _logger.error(f"Chatbot error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'response': 'I apologize, but I encountered an error processing your request.'
            }

    def _generate_ai_response(self, message, chat_id, model='claude'):
        """Generate AI response using Claude API with real Odoo data"""
        try:
            # Get actual data from Odoo based on the query
            odoo_data = self._get_relevant_odoo_data(message, model)
            
            return self._call_claude_api(message, chat_id, odoo_data)

        except Exception as e:
            _logger.error(f"Error calling Claude API: {str(e)}")
            # Get data without AI analysis for fallback
            try:
                odoo_data = self._get_comprehensive_overview()
            except:
                odoo_data = f"Current Date: {fields.Date.today()}\nError accessing ERP data."
            return self._generate_fallback_response_with_data(message, odoo_data)
    
    def _call_claude_api(self, message, chat_id, odoo_data):
        """Call Claude API for AI response"""
        try:
            # Get Claude API key from system parameters
            claude_api_key = self.env['ir.config_parameter'].sudo().get_param('ai_analytics.claude_api_key') or os.getenv('CLAUDE_API_KEY')
            
            if not claude_api_key:
                return "Claude API key not configured. Please set the 'ai_analytics.claude_api_key' system parameter."

            # Prepare the API request
            headers = {
                'x-api-key': claude_api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }

            # Get conversation history for context
            conversation_history = self._get_conversation_history(chat_id)

            # Get real database schema information
            schema_info = self._get_available_models()

            # Build messages for Claude API with comprehensive business data context
            system_prompt = f"""You are a comprehensive business intelligence analyst for the kpak-17 ERP system. You provide ACCURATE, FACTUAL analysis based on real business data.

**YOUR MISSION:**
Analyze real business data from the kpak-17 Odoo ERP system and provide actionable insights for any business question.

**AVAILABLE DATA SOURCES:**
{schema_info}

**LIVE BUSINESS DATA:**
{odoo_data}

**ANALYSIS APPROACH:**
1. **UNDERSTAND THE INTENT**: What business insight does the user need?
2. **ANALYZE THE DATA**: What real data is available? What patterns exist?
3. **PROVIDE INSIGHTS**: Give comprehensive, data-driven analysis with specific numbers
4. **BE ACCURATE**: Use only actual data from the system - no assumptions or estimates

**CAPABILITIES:**
✅ Customer Analysis: Rankings, trends, comparisons, revenue analysis
✅ Product Performance: Best-sellers, sales data, inventory analysis  
✅ Sales Analytics: Revenue trends, order analysis, growth metrics
✅ Financial Reporting: Invoice analysis, payment tracking, financial insights
✅ Comparative Analysis: Year-over-year, period comparisons, growth analysis
✅ Inventory Management: Stock levels, product availability, movement analysis
✅ Partner Analysis: Customer/vendor relationships, performance metrics

**RESPONSE GUIDELINES:**
- Provide specific numbers, names, and dates from actual data
- Include percentages, trends, and comparative analysis when relevant  
- Show year-over-year growth, rankings, and performance metrics
- Reference actual table/model names when explaining data sources
- Give actionable business recommendations based on the analysis

**EXAMPLES OF EXPECTED RESPONSES:**
- "Top 10 customers by revenue with exact amounts and growth percentages"
- "Best-selling products with quantities, revenue, and market share"
- "Year-over-year sales comparison with specific growth metrics"
- "Customer segmentation analysis with actual customer counts and values"

Analyze the user's question and provide comprehensive business intelligence using the real data available."""

            messages = []
            
            # Add conversation history
            for msg in conversation_history[-4:]:  # Last 4 messages for context
                role = "user" if msg['is_user'] else "assistant"
                messages.append({
                    "role": role,
                    "content": msg['message']
                })

            # Add current message with data context
            enhanced_message = f"User Query: {message}\n\nCurrent Odoo Data: {odoo_data}\n\nPlease analyze this real data and provide insights."
            messages.append({
                "role": "user",
                "content": enhanced_message
            })
            
            # Debug logging for Claude
            _logger.info(f"Claude API: Sending {len(enhanced_message)} chars of data context")
            _logger.info(f"Claude API: Data includes {odoo_data.count('kpak-17')} kpak-17 references")

            # Make API call to Claude - NO temperature for consistency
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1024,
                "temperature": 0,  # Zero temperature for deterministic responses
                "system": system_prompt,
                "messages": messages
            }

            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'content' in data and len(data['content']) > 0:
                    return data['content'][0]['text']
                else:
                    _logger.error(f"Claude API unexpected response format: {data}")
                    return self._generate_fallback_response_with_data(message, odoo_data)
            else:
                _logger.error(f"Claude API error: {response.status_code} - {response.text}")
                return self._generate_fallback_response_with_data(message, odoo_data)

        except Exception as e:
            _logger.error(f"Error calling Claude API: {str(e)}")
            return self._generate_fallback_response_with_data(message, odoo_data)

    def _get_conversation_history(self, chat_id):
        """Get conversation history for context"""
        messages = self.env['ai.chatbot.message'].search([
            ('chat_id', '=', chat_id)
        ], order='timestamp asc')
        
        return [{
            'message': msg.message,
            'is_user': msg.is_user,
            'timestamp': msg.timestamp
        } for msg in messages]

    def _get_relevant_odoo_data(self, message, model='claude'):
        """Get relevant Odoo data based on user query using AI-driven intent analysis"""
        try:
            current_date = fields.Date.today()
            
            # Initialize context
            data_context = f"Current Date: {current_date}\n"
            data_context += f"Company: {self.env.company.name}\n"
            data_context += f"Currency: {self.env.company.currency_id.name}\n"
            data_context += f"Database: Odoo ERP - Full System Access\n\n"
            
            # Use AI to determine what data sources to query
            return self._intelligently_fetch_data(message, model)
            
        except Exception as e:
            _logger.error(f"Error getting relevant data: {str(e)}")
            return f"Current Date: {fields.Date.today()}\nNote: Error accessing data - {str(e)}"
    
    def _get_consistent_accounting_data(self):
        """Get comprehensive accounting data - ALWAYS RETURNS THE SAME DATA for consistency"""
        try:
            current_date = fields.Date.today()
            thirty_days_ago = current_date - timedelta(days=30)
            current_year = current_date.year
            
            # ALWAYS fetch the same comprehensive accounting data
            result = "=== COMPREHENSIVE ACCOUNTING DATA ===\n\n"
            
            # Account Moves (Journal Entries) - ALWAYS SAME QUERY
            try:
                moves = self.env['account.move'].search([])
                total_moves = len(moves)
                
                # Posted vs Draft
                posted_moves = moves.filtered(lambda m: m.state == 'posted')
                draft_moves = moves.filtered(lambda m: m.state == 'draft')
                
                # Invoice types
                invoices = moves.filtered(lambda m: m.move_type in ['out_invoice', 'in_invoice'])
                customer_invoices = moves.filtered(lambda m: m.move_type == 'out_invoice')
                vendor_bills = moves.filtered(lambda m: m.move_type == 'in_invoice')
                
                # Recent activity (last 30 days)
                recent_moves = moves.filtered(lambda m: m.date and m.date >= thirty_days_ago)
                
                # This year's data
                this_year_moves = moves.filtered(lambda m: m.date and m.date.year == current_year)
                
                # Amounts
                total_invoice_amount = sum(inv.amount_total for inv in invoices if inv.amount_total)
                customer_invoice_total = sum(inv.amount_total for inv in customer_invoices if inv.amount_total)
                vendor_bill_total = sum(bill.amount_total for bill in vendor_bills if bill.amount_total)
                
                result += f"JOURNAL ENTRIES (account_move):\n"
                result += f"• Total Entries: {total_moves:,}\n"
                result += f"• Posted: {len(posted_moves):,} | Draft: {len(draft_moves):,}\n"
                result += f"• Customer Invoices: {len(customer_invoices):,} (${customer_invoice_total:,.2f})\n"
                result += f"• Vendor Bills: {len(vendor_bills):,} (${vendor_bill_total:,.2f})\n"
                result += f"• Recent (30 days): {len(recent_moves):,}\n"
                result += f"• This Year ({current_year}): {len(this_year_moves):,}\n\n"
                
            except Exception as e:
                result += f"JOURNAL ENTRIES: Error accessing data - {str(e)}\n\n"
            
            # Account Move Lines - ALWAYS SAME QUERY
            try:
                move_lines = self.env['account.move.line'].search([])
                total_lines = len(move_lines)
                
                # Debits and Credits
                total_debit = sum(line.debit for line in move_lines if line.debit)
                total_credit = sum(line.credit for line in move_lines if line.credit)
                net_balance = total_debit - total_credit
                
                # Reconciled lines
                reconciled_lines = move_lines.filtered(lambda l: l.reconciled)
                unreconciled_lines = move_lines.filtered(lambda l: not l.reconciled and l.account_id.reconcile)
                
                # Recent lines
                recent_lines = move_lines.filtered(lambda l: l.date and l.date >= thirty_days_ago)
                
                result += f"JOURNAL ENTRY LINES (account_move_line):\n"
                result += f"• Total Lines: {total_lines:,}\n"
                result += f"• Total Debits: ${total_debit:,.2f}\n"
                result += f"• Total Credits: ${total_credit:,.2f}\n"
                result += f"• Net Balance: ${net_balance:,.2f}\n"
                result += f"• Reconciled: {len(reconciled_lines):,}\n"
                result += f"• Unreconciled: {len(unreconciled_lines):,}\n"
                result += f"• Recent Lines (30 days): {len(recent_lines):,}\n\n"
                
            except Exception as e:
                result += f"JOURNAL ENTRY LINES: Error accessing data - {str(e)}\n\n"
            
            # Add data timestamp
            result += f"Data Retrieved: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            result += f"Data Source: account_move and account_move_line tables only\n"
            
            _logger.info(f"Generated consistent accounting data: {len(result)} characters")
            return result
            
        except Exception as e:
            _logger.error(f"Error generating consistent accounting data: {str(e)}")
            return f"ACCOUNTING DATA: Error accessing tables - {str(e)}"
    
    def _intelligently_fetch_data(self, message, model='claude'):
        """Use AI to determine what accounting data to fetch from allowed tables only"""
        try:
            # Let LLM decide if this is a system test request instead of hardcoded matching
            
            # Analyze user intent using AI
            intent_analysis = self._ai_analyze_intent(message, model)
            
            # Based on intent, identify relevant models and data using pure LLM reasoning
            data_sources = self._identify_data_sources(intent_analysis, message, model)
            
            _logger.info(f"Identified data sources: {[s.get('name') for s in data_sources]}")
            
            # Fetch data from LLM-identified sources
            combined_data = ""
            for source in data_sources:
                try:
                    # Check if this is a special action or a model query
                    if source.get('action') in ['comprehensive_overview', 'accounting_overview']:
                        source_data = self._get_comprehensive_overview()
                        combined_data += f"\n{source.get('name', 'Overview')} Data:\n{source_data}\n"
                    else:
                        # This is a model-based query decided by LLM
                        source_data = self._fetch_from_llm_source(source, message)
                        if source_data:
                            reasoning = source.get('reasoning', 'LLM selected this data source')
                            combined_data += f"\n{source['name']} Data:\n"
                            combined_data += f"Reasoning: {reasoning}\n"
                            combined_data += f"{source_data}\n"
                except Exception as e:
                    _logger.warning(f"Could not fetch from {source.get('name', 'unknown')}: {str(e)}")
                    combined_data += f"\n{source.get('name', 'Unknown')} Data: Error accessing - {str(e)}\n"
            
            if not combined_data.strip():
                combined_data = self._get_comprehensive_overview()
            
            return combined_data
            
        except Exception as e:
            _logger.error(f"Error in intelligent data fetching: {str(e)}")
            return self._get_comprehensive_overview()
    
    def _ai_analyze_intent(self, message, model='claude'):
        """Use AI to analyze user intent without hardcoded keywords"""
        try:
            return self._claude_analyze_intent(message)
        except Exception as e:
            _logger.error(f"Error in AI intent analysis: {str(e)}")
            return {'intent': 'general', 'area': 'business', 'action': 'overview'}
    
    def _claude_analyze_intent(self, message):
        """Use Claude to analyze user intent"""
        try:
            claude_api_key = self.env['ir.config_parameter'].sudo().get_param('ai_analytics.claude_api_key') or os.getenv('CLAUDE_API_KEY')
            if not claude_api_key:
                return {'intent': 'general', 'confidence': 0.5}
            
            headers = {
                'x-api-key': claude_api_key,
                'Content-Type': 'application/json',
                'anthropic-version': '2023-06-01'
            }
            
            # AI prompt to analyze intent for comprehensive business analysis
            system_prompt = """You are an AI intent analyzer for a comprehensive Odoo ERP system. Analyze the user's business question and determine their needs.

Available business areas in this system:
- Sales & Revenue: Customer analysis, sales orders, revenue trends, top customers
- Products & Inventory: Product performance, inventory levels, best-selling products  
- Customers & Partners: Customer data, partner relationships, customer rankings
- Financial & Accounting: Invoices, payments, journal entries, financial reports
- Purchasing: Vendor analysis, purchase orders, supplier performance
- Human Resources: Employee data, payroll, performance metrics
- Operations: General business operations and reporting

Analyze the user's question and identify:
1. Primary business area (sales, products, customers, finance, purchasing, hr, operations)
2. Specific action requested (analysis, comparison, ranking, reporting, etc.)
3. Time frame (current, historical, specific periods, year-over-year, etc.)
4. Data scope (summary, detailed, top N, specific criteria, etc.)

EXAMPLES:
- "top 10 customers 2023 vs 2024" → {"intent": "customer_analysis", "area": "customers", "action": "ranking_comparison", "timeframe": "2023_2024", "scope": "top_10"}
- "best selling products" → {"intent": "product_analysis", "area": "products", "action": "performance_ranking", "timeframe": "current", "scope": "top_performers"}
- "sales trends this year" → {"intent": "sales_analysis", "area": "sales", "action": "trend_analysis", "timeframe": "current_year", "scope": "summary"}

Respond in JSON format with: {"intent": "primary_intent", "area": "business_area", "action": "specific_action", "timeframe": "time_scope", "scope": "data_scope"}"""
            
            messages = [
                {"role": "user", "content": f"Analyze this user query: {message}"}
            ]
            
            payload = {
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 200,
                "system": system_prompt,
                "messages": messages
            }
            
            response = requests.post('https://api.anthropic.com/v1/messages',
                                   headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                content = result['content'][0]['text'].strip()
                try:
                    return json.loads(content)
                except:
                    return {'intent': content, 'area': 'general', 'action': 'analyze'}
            else:
                _logger.warning(f"Claude API error for intent analysis: {response.status_code}")
                return {'intent': 'general', 'area': 'business', 'action': 'overview'}
                
        except Exception as e:
            _logger.error(f"Error in Claude intent analysis: {str(e)}")
            return {'intent': 'general', 'area': 'business', 'action': 'overview'}
    
    def _identify_data_sources(self, intent_analysis, original_message, model='claude'):
        """Use LLM to intelligently identify which data sources to query - NO hardcoded logic"""
        try:
            # Let the LLM decide what data sources to use based on pure intent reasoning
            return self._llm_identify_data_sources(intent_analysis, original_message, model)
            
        except Exception as e:
            _logger.error(f"Error in LLM data source identification: {str(e)}")
            # Only fallback to accounting overview if LLM fails
            return [{'name': 'Accounting Overview', 'action': 'accounting_overview'}]
    
    def _llm_identify_data_sources(self, intent_analysis, original_message, model='claude'):
        """Let LLM intelligently decide what data sources to query with reasoning steps"""
        try:
            # Use Claude for data source identification
            return self._claude_identify_data_sources(intent_analysis, original_message)
                
        except Exception as e:
            _logger.error(f"Error in LLM data source identification: {str(e)}")
            return [{'name': 'Accounting Overview', 'action': 'accounting_overview'}]
    

    def _claude_identify_data_sources(self, intent_analysis, original_message):
        """Use Claude to identify data sources - restricted to accounting tables only"""
        try:
            claude_api_key = self.env["ir.config_parameter"].sudo().get_param("ai_analytics.claude_api_key")
            if not claude_api_key:
                return [{"name": "Accounting Overview", "action": "accounting_overview"}]
            
            # Get available models dynamically
            available_models = self._get_available_models()
            
            # Create intelligent prompt for data source identification
            prompt = f"""You are a data analyst for a comprehensive Odoo ERP system. Based on the user's query, intelligently identify which data sources to query.

USER'S INTENT ANALYSIS:
{intent_analysis}

ORIGINAL USER MESSAGE: 
{original_message}

AVAILABLE ODOO MODELS AND FIELDS:
{available_models}

INSTRUCTIONS:
1. Analyze the user's request carefully
2. Identify which Odoo models contain the relevant data
3. For customer analysis queries (like "top customers"), you should use:
   - res.partner (customer information)
   - account.move (invoices with customer data via partner_id) 
   - sale.order (sales orders if available)
4. For date-based analysis, use appropriate date fields (date, invoice_date, date_order, etc.)
5. Select the most relevant fields for the analysis

Return a JSON array with data sources needed:
[
  {{
    "name": "Human-readable description",
    "model": "odoo.model.name", 
    "fields": ["field1", "field2", "field3"],
    "reasoning": "Why this model is relevant for the query"
  }}
]

EXAMPLES:
- For "top 10 customers 2023 vs 2024": Use account.move with partner_id, amount_total, invoice_date
- For "sales analysis": Use sale.order with partner_id, amount_total, date_order
- For "product performance": Use product.product, sale.order.line, account.move.line
- For "inventory status": Use stock.quant, product.product

Be intelligent - select the models that actually contain the data needed to answer the question."""

            headers = {
                "x-api-key": claude_api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            }

            data = {
                "model": "claude-3-haiku-20240307",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }

            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=data,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                claude_response = result['content'][0]['text'].strip()
                _logger.info(f"Claude data source identification response: {claude_response}")
                
                # Try to parse JSON response
                try:
                    sources = json.loads(claude_response)
                    # Process AI-recommended data sources
                    converted_sources = []
                    for source in sources:
                        model_name = source.get('model', source.get('table', ''))
                        
                        # Validate that the model exists in this Odoo instance
                        if model_name and self._validate_model_access(model_name):
                            converted_sources.append({
                                'name': source.get('name', model_name),
                                'model': model_name,
                                'fields': source.get('fields', ['id', 'name']),
                                'reasoning': source.get('reasoning', 'AI-selected data source')
                            })
                            _logger.info(f"Added data source: {model_name} for analysis")
                        else:
                            _logger.warning(f"Model {model_name} not accessible or doesn't exist")
                            
                    return converted_sources
                except json.JSONDecodeError:
                    _logger.warning("Failed to parse JSON from Claude response, using fallback")
                    
            else:
                _logger.error(f"Claude API error: {response.status_code} - {response.text}")
            
        except Exception as e:
            _logger.error(f"Error in Claude data source identification: {str(e)}")
        
        # Fallback
        return [{"name": "Business Overview", "action": "comprehensive_overview"}]
    
    def _validate_model_access(self, model_name):
        """Validate that a model exists and is accessible"""
        try:
            # Check if model exists
            if model_name in self.env.registry:
                # Try to access the model - this will raise an exception if no access
                model = self.env[model_name]
                model.check_access_rights('read')
                return True
            return False
        except Exception as e:
            _logger.debug(f"Cannot access model {model_name}: {str(e)}")
            return False

    def _fetch_from_llm_source(self, source, original_message):
        """Fetch data from AI-selected source with intelligent filtering"""
        try:
            model_name = source.get('model')
            fields = source.get('fields', ['name'])
            source_name = source.get('name', model_name)
            
            # Model access was already validated in _validate_model_access
            _logger.info(f"Fetching data from model: {model_name}")
            
            # Apply intelligent filtering based on the query
            domain = self._build_intelligent_domain(original_message, model_name)
            
            # Try to access the model and get relevant records
            try:
                records = self.env[model_name].search(domain, limit=1000)  # Reasonable limit
                _logger.info(f"Successfully accessed {model_name}, found {len(records)} records")
            except Exception as e:
                _logger.error(f"Error accessing model {model_name}: {str(e)}")
                return f"Model {model_name} not accessible: {str(e)}"
            
            if not records:
                return f"No {source_name.lower()} found matching the criteria."
            
            # Generic data extraction with intelligent analysis
            return self._extract_data_intelligently(records, source_name, fields, model_name, original_message)
            
        except Exception as e:
            _logger.error(f"Error fetching data from {source.get('name')}: {str(e)}")
            return f"Could not retrieve {source.get('name', 'data')}: {str(e)}"
    
    def _build_intelligent_domain(self, message, model_name):
        """Build intelligent search domain based on user query and model"""
        domain = []
        
        try:
            # Extract years from message if present (for date filtering)
            import re
            years = re.findall(r'\b(20\d{2})\b', message)
            
            # Date filtering for models with date fields
            if years and model_name in ['account.move', 'sale.order', 'purchase.order']:
                date_field = 'invoice_date' if model_name == 'account.move' else 'date_order'
                
                if date_field in self.env[model_name]._fields:
                    if len(years) >= 2:
                        # Range of years
                        start_year = min([int(y) for y in years])
                        end_year = max([int(y) for y in years])
                        domain.extend([
                            (date_field, '>=', f'{start_year}-01-01'),
                            (date_field, '<=', f'{end_year}-12-31')
                        ])
                    else:
                        # Single year
                        year = years[0]
                        domain.extend([
                            (date_field, '>=', f'{year}-01-01'),
                            (date_field, '<=', f'{year}-12-31')
                        ])
            
            # Customer/partner filtering based on model
            if 'partner_id' in self.env[model_name]._fields:
                # For customer queries, focus on customer invoices/orders
                if model_name == 'account.move':
                    domain.append(('move_type', '=', 'out_invoice'))  # Customer invoices only
                
            # Status filtering for posted/confirmed records
            if model_name == 'account.move' and 'state' in self.env[model_name]._fields:
                domain.append(('state', '=', 'posted'))  # Only posted invoices
            elif 'state' in self.env[model_name]._fields and model_name == 'sale.order':
                domain.append(('state', 'in', ['sale', 'done']))  # Confirmed sales orders
            
        except Exception as e:
            _logger.warning(f"Error building domain: {str(e)}")
            
        _logger.info(f"Built domain for {model_name}: {domain}")
        return domain
    
    def _extract_data_intelligently(self, records, source_name, fields, model_name, original_message):
        """Extract and analyze data intelligently based on the query context"""
        try:
            result = f"=== {source_name.upper()} ANALYSIS ===\n"
            result += f"Model: {model_name}\n"
            result += f"Records Found: {len(records)}\n\n"
            
            if not records:
                return result + "No records found.\n"
            
            # Route to specific analysis based on model type and data structure
            if model_name == 'account.move' and 'partner_id' in records._fields:
                # Customer analysis via invoice data
                return self._analyze_customer_data(records, original_message, model_name)
            
            elif model_name == 'sale.order.line' and 'product_id' in records._fields:
                # Product analysis via sales order lines
                return self._analyze_product_data(records, original_message, model_name)
            
            elif model_name == 'sale.order':
                # Sales order analysis
                return self._analyze_sales_data(records, original_message)
            
            elif model_name == 'account.move':
                # Invoice/financial analysis
                return self._analyze_invoice_data(records, original_message)
                
            elif model_name == 'product.product':
                # Product catalog analysis
                return self._analyze_product_data(records, original_message, model_name)
                
            elif model_name in ['crm.lead', 'crm.stage', 'crm.team', 'crm.team.member', 'crm.tag', 'crm.lost.reason']:
                # CRM analysis - leads, stages, teams, tags, etc.
                return self._analyze_crm_data(records, original_message, model_name)
                
            elif model_name in ['hr.employee', 'hr.department', 'hr.job', 'hr.employee.category', 'hr.work.location']:
                # HR analysis - employees, departments, jobs, etc.
                return self._analyze_hr_data(records, original_message, model_name)
                
            elif model_name in ['stock.quant', 'stock.move', 'stock.move.line', 'stock.picking', 'stock.warehouse', 'stock.location', 'stock.lot']:
                # Inventory/warehouse analysis
                return self._analyze_inventory_data(records, original_message, model_name)
                
            elif model_name in ['purchase.order', 'purchase.order.line']:
                # Purchase analysis
                return self._analyze_purchase_data(records, original_message, model_name)
                
            elif model_name in ['mrp.production', 'mrp.bom', 'mrp.bom.line', 'mrp.workcenter', 'mrp.workorder']:
                # Manufacturing analysis
                return self._analyze_manufacturing_data(records, original_message, model_name)
                
            elif model_name in ['account.payment', 'account.bank.statement', 'account.bank.statement.line', 'account.tax']:
                # Additional financial analysis
                return self._analyze_financial_data(records, original_message, model_name)
                
            elif model_name in ['res.partner', 'res.partner.category', 'res.partner.industry']:
                # Partner/customer analysis (enhanced)
                return self._analyze_partner_data(records, original_message, model_name)
                
            elif model_name in ['product.template', 'product.category', 'product.attribute', 'product.tag', 'product.pricelist']:
                # Enhanced product analysis
                return self._analyze_product_data(records, original_message, model_name)
                
            elif model_name in ['res.users', 'calendar.event', 'mail.message']:
                # System and communication analysis
                return self._analyze_system_data(records, original_message, model_name)
            
            # Generic analysis for other models
            else:
                return self._analyze_generic_data(records, source_name, fields, model_name)
                
        except Exception as e:
            _logger.error(f"Error in intelligent data extraction: {str(e)}")
            return f"Error analyzing {source_name}: {str(e)}"
    
    def _analyze_customer_data(self, records, message, model_name):
        """Analyze customer-related data with year-over-year comparison"""
        try:
            result = "=== CUSTOMER ANALYSIS ===\n\n"
            
            # Group by customer (partner_id)
            from collections import defaultdict
            customer_data = defaultdict(lambda: {'name': '', 'total_2023': 0, 'total_2024': 0, 'records_2023': 0, 'records_2024': 0})
            
            for record in records:
                if not record.partner_id:
                    continue
                    
                customer_id = record.partner_id.id
                customer_name = record.partner_id.name
                customer_data[customer_id]['name'] = customer_name
                
                # Get amount field
                amount_field = 'amount_total' if hasattr(record, 'amount_total') else 'price_total'
                amount = getattr(record, amount_field, 0) if hasattr(record, amount_field) else 0
                
                # Get date field
                date_field = getattr(record, 'invoice_date', None) or getattr(record, 'date_order', None) or getattr(record, 'date', None)
                
                if date_field:
                    year = date_field.year
                    if year == 2023:
                        customer_data[customer_id]['total_2023'] += amount
                        customer_data[customer_id]['records_2023'] += 1
                    elif year == 2024:
                        customer_data[customer_id]['total_2024'] += amount
                        customer_data[customer_id]['records_2024'] += 1
            
            # Sort customers by combined total (2023 + 2024)
            sorted_customers = sorted(
                customer_data.items(), 
                key=lambda x: x[1]['total_2023'] + x[1]['total_2024'], 
                reverse=True
            )
            
            # Get top 10 customers
            top_customers = sorted_customers[:10]
            
            result += f"TOP {len(top_customers)} CUSTOMERS (2023 vs 2024 Comparison)\n"
            result += "=" * 60 + "\n\n"
            
            for i, (customer_id, data) in enumerate(top_customers, 1):
                total_combined = data['total_2023'] + data['total_2024']
                change = data['total_2024'] - data['total_2023']
                change_pct = (change / data['total_2023'] * 100) if data['total_2023'] > 0 else 0
                
                result += f"{i}. {data['name']}\n"
                result += f"   2023: ${data['total_2023']:,.2f} ({data['records_2023']} transactions)\n"
                result += f"   2024: ${data['total_2024']:,.2f} ({data['records_2024']} transactions)\n"
                result += f"   Change: ${change:,.2f} ({change_pct:+.1f}%)\n"
                result += f"   Total: ${total_combined:,.2f}\n\n"
            
            # Summary statistics
            total_2023 = sum(data['total_2023'] for _, data in sorted_customers)
            total_2024 = sum(data['total_2024'] for _, data in sorted_customers)
            total_change = total_2024 - total_2023
            total_change_pct = (total_change / total_2023 * 100) if total_2023 > 0 else 0
            
            result += "SUMMARY:\n"
            result += f"Total Revenue 2023: ${total_2023:,.2f}\n"
            result += f"Total Revenue 2024: ${total_2024:,.2f}\n"  
            result += f"Year-over-Year Change: ${total_change:,.2f} ({total_change_pct:+.1f}%)\n"
            result += f"Total Customers Analyzed: {len(customer_data)}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in customer analysis: {str(e)}")
            return f"Error analyzing customer data: {str(e)}"
    
    def _analyze_product_data(self, records, message, model_name):
        """Analyze product performance and sales data"""
        try:
            result = "=== PRODUCT ANALYSIS ===\n\n"
            
            if not records:
                return result + "No product data found.\n"
            
            if model_name == 'sale.order.line':
                # Sales order lines analysis for top selling products
                from collections import defaultdict
                product_data = defaultdict(lambda: {'name': '', 'qty_sold': 0, 'revenue': 0, 'orders': 0})
                
                for line in records:
                    if line.product_id:
                        product_id = line.product_id.id
                        product_data[product_id]['name'] = line.product_id.name
                        product_data[product_id]['qty_sold'] += line.product_uom_qty or 0
                        product_data[product_id]['revenue'] += line.price_subtotal or 0
                        product_data[product_id]['orders'] += 1
                
                # Use AI to determine sorting criteria
                sort_by_quantity = self._analyze_with_ai(
                    f"Should I sort products by quantity or revenue for this query: '{message}'? Reply with only 'quantity' or 'revenue'."
                ).lower().strip()
                
                if 'quantity' in sort_by_quantity:
                    sorted_products = sorted(product_data.items(), key=lambda x: x[1]['qty_sold'], reverse=True)
                    sort_criteria = "quantity sold"
                else:
                    sorted_products = sorted(product_data.items(), key=lambda x: x[1]['revenue'], reverse=True)
                    sort_criteria = "revenue"
                
                # Get top 10 products
                top_products = sorted_products[:10]
                
                result += f"TOP {len(top_products)} SELLING PRODUCTS (by {sort_criteria})\n"
                result += "=" * 60 + "\n\n"
                
                total_revenue = sum(data['revenue'] for _, data in sorted_products)
                total_qty = sum(data['qty_sold'] for _, data in sorted_products)
                
                for i, (product_id, data) in enumerate(top_products, 1):
                    revenue_pct = (data['revenue'] / total_revenue * 100) if total_revenue > 0 else 0
                    qty_pct = (data['qty_sold'] / total_qty * 100) if total_qty > 0 else 0
                    
                    result += f"{i}. {data['name']}\n"
                    result += f"   Revenue: ${data['revenue']:,.2f} ({revenue_pct:.1f}% of total)\n"
                    result += f"   Quantity Sold: {data['qty_sold']:,.0f} units ({qty_pct:.1f}% of total)\n"
                    result += f"   Orders: {data['orders']} orders\n"
                    
                    if data['orders'] > 0:
                        avg_qty_per_order = data['qty_sold'] / data['orders']
                        avg_revenue_per_order = data['revenue'] / data['orders']
                        result += f"   Average per order: {avg_qty_per_order:.1f} units, ${avg_revenue_per_order:,.2f}\n"
                    result += "\n"
                
                result += "SUMMARY:\n"
                result += f"Total Products Analyzed: {len(product_data)}\n"
                result += f"Total Revenue: ${total_revenue:,.2f}\n"
                result += f"Total Quantity Sold: {total_qty:,.0f} units\n"
                result += f"Total Orders: {sum(data['orders'] for _, data in sorted_products)}\n"
                
            elif model_name == 'product.product':
                # Product catalog analysis
                result += f"PRODUCT CATALOG ANALYSIS\n"
                result += f"Total Products: {len(records)}\n\n"
                
                # Price analysis
                products_with_price = [p for p in records if p.list_price > 0]
                if products_with_price:
                    avg_price = sum(p.list_price for p in products_with_price) / len(products_with_price)
                    max_price = max(p.list_price for p in products_with_price)
                    min_price = min(p.list_price for p in products_with_price)
                    
                    result += f"PRICING ANALYSIS:\n"
                    result += f"Average Price: ${avg_price:,.2f}\n"
                    result += f"Price Range: ${min_price:,.2f} - ${max_price:,.2f}\n"
                    result += f"Products with Pricing: {len(products_with_price)}\n\n"
                
                # Category breakdown if available
                if hasattr(records[0], 'categ_id'):
                    from collections import Counter
                    categories = [p.categ_id.name for p in records if p.categ_id]
                    category_counts = Counter(categories)
                    
                    result += "TOP PRODUCT CATEGORIES:\n"
                    for category, count in category_counts.most_common(10):
                        result += f"  {category}: {count} products\n"
                
            return result
            
        except Exception as e:
            _logger.error(f"Error in product analysis: {str(e)}")
            return f"Error analyzing product data: {str(e)}"
    
    def _analyze_crm_data(self, records, message, model_name):
        """Analyze CRM leads/opportunities data"""
        try:
            result = "=== CRM ANALYSIS ===\n\n"
            
            if not records:
                return result + "No CRM data found.\n"
            
            result += f"Total Leads/Opportunities: {len(records)}\n\n"
            
            # Lead type analysis
            from collections import defaultdict, Counter
            
            # Type breakdown (leads vs opportunities)
            if hasattr(records[0], 'type'):
                type_counts = Counter([r.type for r in records if r.type])
                result += "LEAD TYPE BREAKDOWN:\n"
                for lead_type, count in type_counts.most_common():
                    result += f"  {lead_type.title()}: {count} records\n"
                result += "\n"
            
            # Stage analysis
            if hasattr(records[0], 'stage_id'):
                stage_data = defaultdict(lambda: {'count': 0, 'revenue': 0})
                for record in records:
                    if record.stage_id:
                        stage_name = record.stage_id.name
                        stage_data[stage_name]['count'] += 1
                        if hasattr(record, 'expected_revenue') and record.expected_revenue:
                            stage_data[stage_name]['revenue'] += record.expected_revenue
                
                if stage_data:
                    result += "PIPELINE STAGE ANALYSIS:\n"
                    for stage_name, data in stage_data.items():
                        avg_revenue = data['revenue'] / data['count'] if data['count'] > 0 else 0
                        result += f"  {stage_name}: {data['count']} leads, ${data['revenue']:,.2f} potential (avg: ${avg_revenue:,.2f})\n"
                    result += "\n"
            
            # Team performance
            if hasattr(records[0], 'team_id'):
                team_data = defaultdict(lambda: {'count': 0, 'revenue': 0})
                for record in records:
                    if record.team_id:
                        team_name = record.team_id.name
                        team_data[team_name]['count'] += 1
                        if hasattr(record, 'expected_revenue') and record.expected_revenue:
                            team_data[team_name]['revenue'] += record.expected_revenue
                
                if team_data:
                    result += "TEAM PERFORMANCE:\n"
                    sorted_teams = sorted(team_data.items(), key=lambda x: x[1]['revenue'], reverse=True)
                    for team_name, data in sorted_teams:
                        avg_revenue = data['revenue'] / data['count'] if data['count'] > 0 else 0
                        result += f"  {team_name}: {data['count']} leads, ${data['revenue']:,.2f} potential (avg: ${avg_revenue:,.2f})\n"
                    result += "\n"
            
            # User/Salesperson performance
            if hasattr(records[0], 'user_id'):
                user_data = defaultdict(lambda: {'count': 0, 'revenue': 0})
                for record in records:
                    if record.user_id:
                        user_name = record.user_id.name
                        user_data[user_name]['count'] += 1
                        if hasattr(record, 'expected_revenue') and record.expected_revenue:
                            user_data[user_name]['revenue'] += record.expected_revenue
                
                if user_data:
                    result += "TOP SALES PERFORMERS:\n"
                    sorted_users = sorted(user_data.items(), key=lambda x: x[1]['revenue'], reverse=True)[:10]
                    for user_name, data in sorted_users:
                        avg_revenue = data['revenue'] / data['count'] if data['count'] > 0 else 0
                        result += f"  {user_name}: {data['count']} leads, ${data['revenue']:,.2f} potential (avg: ${avg_revenue:,.2f})\n"
                    result += "\n"
            
            # Revenue analysis
            revenue_records = [r for r in records if hasattr(r, 'expected_revenue') and r.expected_revenue]
            if revenue_records:
                total_revenue = sum(r.expected_revenue for r in revenue_records)
                avg_revenue = total_revenue / len(revenue_records)
                max_revenue = max(r.expected_revenue for r in revenue_records)
                
                result += "REVENUE ANALYSIS:\n"
                result += f"  Total Expected Revenue: ${total_revenue:,.2f}\n"
                result += f"  Average Deal Size: ${avg_revenue:,.2f}\n"
                result += f"  Largest Opportunity: ${max_revenue:,.2f}\n"
                result += f"  Records with Revenue Data: {len(revenue_records)}\n\n"
            
            # Probability analysis (if available)
            if hasattr(records[0], 'probability'):
                prob_records = [r for r in records if r.probability is not None]
                if prob_records:
                    avg_probability = sum(r.probability for r in prob_records) / len(prob_records)
                    high_prob = [r for r in prob_records if r.probability >= 70]
                    result += f"PROBABILITY ANALYSIS:\n"
                    result += f"  Average Probability: {avg_probability:.1f}%\n"
                    result += f"  High Probability (≥70%): {len(high_prob)} leads\n\n"
            
            # Recent activity analysis
            if hasattr(records[0], 'create_date'):
                from datetime import datetime, timedelta
                current_date = fields.Date.today()
                thirty_days_ago = current_date - timedelta(days=30)
                recent_leads = [r for r in records if r.create_date and r.create_date.date() >= thirty_days_ago]
                
                result += f"ACTIVITY SUMMARY:\n"
                result += f"  Recent Leads (last 30 days): {len(recent_leads)}\n"
                result += f"  Total Active Leads: {len([r for r in records if r.active])}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in CRM analysis: {str(e)}")
            return f"Error analyzing CRM data: {str(e)}"
    
    def _analyze_hr_data(self, records, message, model_name):
        """Analyze HR-related data"""
        try:
            result = f"=== HR ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No HR data found.\n"
            
            if model_name == 'hr.employee':
                result += f"Total Employees: {len(records)}\n\n"
                
                # Department distribution
                if hasattr(records[0], 'department_id'):
                    from collections import Counter
                    dept_counts = Counter([r.department_id.name for r in records if r.department_id])
                    
                    result += "DEPARTMENT DISTRIBUTION:\n"
                    for dept_name, count in dept_counts.most_common():
                        result += f"  {dept_name}: {count} employees\n"
                    result += "\n"
                
                # Job position distribution
                if hasattr(records[0], 'job_id'):
                    job_counts = Counter([r.job_id.name for r in records if r.job_id])
                    
                    result += "JOB POSITION DISTRIBUTION:\n"
                    for job_name, count in job_counts.most_common(10):  # Top 10
                        result += f"  {job_name}: {count} employees\n"
                    result += "\n"
                
                # Active vs inactive
                active_count = len([r for r in records if r.active])
                inactive_count = len(records) - active_count
                result += f"EMPLOYEE STATUS:\n"
                result += f"  Active: {active_count} employees\n"
                result += f"  Inactive: {inactive_count} employees\n\n"
                
            elif model_name == 'hr.department':
                result += f"Total Departments: {len(records)}\n\n"
                
                # Manager analysis
                if hasattr(records[0], 'manager_id'):
                    managed_depts = len([r for r in records if r.manager_id])
                    result += f"Departments with Managers: {managed_depts}\n"
                    result += f"Departments without Managers: {len(records) - managed_depts}\n\n"
                
            elif model_name == 'hr.job':
                result += f"Total Job Positions: {len(records)}\n\n"
                
                # Recruitment analysis
                if hasattr(records[0], 'no_of_recruitment'):
                    total_openings = sum(r.no_of_recruitment for r in records if r.no_of_recruitment)
                    active_jobs = len([r for r in records if getattr(r, 'state', '') == 'open'])
                    result += f"RECRUITMENT ANALYSIS:\n"
                    result += f"  Total Open Positions: {total_openings}\n"
                    result += f"  Active Job Postings: {active_jobs}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in HR analysis: {str(e)}")
            return f"Error analyzing HR data: {str(e)}"
    
    def _analyze_sales_data(self, records, message):
        """Analyze sales order data"""
        try:
            result = "=== SALES ANALYSIS ===\n\n"
            
            if not records:
                return result + "No sales orders found.\n"
            
            total_amount = sum(record.amount_total for record in records if record.amount_total)
            result += f"Total Sales Value: ${total_amount:,.2f}\n"
            result += f"Number of Orders: {len(records)}\n"
            result += f"Average Order Value: ${total_amount / len(records):,.2f}\n\n"
            
            # Year-wise breakdown
            from collections import defaultdict
            yearly_data = defaultdict(lambda: {'count': 0, 'total': 0.0})
            
            for record in records:
                if record.date_order:
                    year = record.date_order.year
                    yearly_data[year]['count'] += 1
                    yearly_data[year]['total'] += record.amount_total or 0
            
            if yearly_data:
                result += "YEAR-WISE BREAKDOWN:\n"
                for year in sorted(yearly_data.keys()):
                    data = yearly_data[year]
                    avg_amount = data['total'] / data['count'] if data['count'] > 0 else 0
                    result += f"  {year}: {data['count']} orders, ${data['total']:,.2f} (avg: ${avg_amount:,.2f})\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in sales analysis: {str(e)}")
            return f"Error analyzing sales data: {str(e)}"
    
    def _analyze_invoice_data(self, records, message):
        """Analyze invoice data"""
        try:
            result = "=== INVOICE ANALYSIS ===\n\n"
            
            if not records:
                return result + "No invoices found.\n"
            
            total_amount = sum(record.amount_total for record in records if record.amount_total)
            result += f"Total Invoice Value: ${total_amount:,.2f}\n"
            result += f"Number of Invoices: {len(records)}\n"
            result += f"Average Invoice Value: ${total_amount / len(records):,.2f}\n\n"
            
            # Invoice type breakdown
            from collections import Counter
            invoice_types = Counter([record.move_type for record in records])
            
            result += "INVOICE TYPE BREAKDOWN:\n"
            for inv_type, count in invoice_types.most_common():
                type_total = sum(r.amount_total for r in records if r.move_type == inv_type and r.amount_total)
                result += f"  {inv_type}: {count} invoices, ${type_total:,.2f}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in invoice analysis: {str(e)}")
            return f"Error analyzing invoice data: {str(e)}"
    
    def _analyze_inventory_data(self, records, message, model_name):
        """Analyze inventory/stock-related data"""
        try:
            result = f"=== INVENTORY ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No inventory data found.\n"
            
            if model_name == 'stock.quant':
                result += f"Total Stock Quantities: {len(records)}\n\n"
                
                # Product quantity analysis
                from collections import defaultdict
                product_data = defaultdict(lambda: {'name': '', 'total_qty': 0, 'total_value': 0, 'locations': 0})
                location_data = defaultdict(lambda: {'name': '', 'total_qty': 0, 'products': 0})
                
                for record in records:
                    if record.product_id:
                        product_id = record.product_id.id
                        product_data[product_id]['name'] = record.product_id.name
                        product_data[product_id]['total_qty'] += record.quantity or 0
                        product_data[product_id]['total_value'] += record.value or 0
                        product_data[product_id]['locations'] += 1
                    
                    if record.location_id:
                        location_name = record.location_id.name
                        location_data[location_name]['name'] = location_name
                        location_data[location_name]['total_qty'] += record.quantity or 0
                        location_data[location_name]['products'] += 1
                
                # Top products by quantity
                sorted_products = sorted(product_data.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:10]
                
                result += "TOP 10 PRODUCTS BY STOCK QUANTITY:\n"
                for i, (product_id, data) in enumerate(sorted_products, 1):
                    result += f"{i}. {data['name']}: {data['total_qty']:,.2f} units (${data['total_value']:,.2f} value)\n"
                result += "\n"
                
                # Stock locations analysis
                sorted_locations = sorted(location_data.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:10]
                
                result += "TOP 10 LOCATIONS BY STOCK QUANTITY:\n"
                for i, (location_name, data) in enumerate(sorted_locations, 1):
                    result += f"{i}. {location_name}: {data['total_qty']:,.2f} units ({data['products']} different products)\n"
                
            elif model_name == 'stock.move':
                result += f"Total Stock Movements: {len(records)}\n\n"
                
                # Movement state analysis
                from collections import Counter
                state_counts = Counter([r.state for r in records if r.state])
                
                result += "MOVEMENT STATUS BREAKDOWN:\n"
                for state, count in state_counts.most_common():
                    result += f"  {state.title()}: {count} movements\n"
                result += "\n"
                
                # Recent movements
                recent_moves = [r for r in records if r.date]
                if recent_moves:
                    recent_moves = sorted(recent_moves, key=lambda x: x.date, reverse=True)[:10]
                    result += "RECENT MOVEMENTS:\n"
                    for move in recent_moves:
                        product_name = move.product_id.name if move.product_id else 'Unknown Product'
                        result += f"  {move.date.date()}: {product_name} - {move.product_uom_qty} units ({move.state})\n"
            
            elif model_name == 'stock.picking':
                result += f"Total Transfers/Deliveries: {len(records)}\n\n"
                
                # Transfer state analysis
                state_counts = Counter([r.state for r in records if r.state])
                
                result += "TRANSFER STATUS BREAKDOWN:\n"
                for state, count in state_counts.most_common():
                    result += f"  {state.title()}: {count} transfers\n"
                result += "\n"
                
                # Partner analysis
                partner_counts = Counter([r.partner_id.name for r in records if r.partner_id])
                
                if partner_counts:
                    result += "TOP PARTNERS (Transfers):\n"
                    for partner, count in partner_counts.most_common(10):
                        result += f"  {partner}: {count} transfers\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in inventory analysis: {str(e)}")
            return f"Error analyzing inventory data: {str(e)}"
    
    def _analyze_purchase_data(self, records, message, model_name):
        """Analyze purchase-related data"""
        try:
            result = f"=== PURCHASE ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No purchase data found.\n"
            
            if model_name == 'purchase.order':
                total_amount = sum(record.amount_total for record in records if record.amount_total)
                result += f"Total Purchase Value: ${total_amount:,.2f}\n"
                result += f"Number of Purchase Orders: {len(records)}\n"
                result += f"Average Order Value: ${total_amount / len(records):,.2f}\n\n"
                
                # Purchase state analysis
                from collections import Counter
                state_counts = Counter([r.state for r in records if r.state])
                
                result += "PURCHASE ORDER STATUS:\n"
                for state, count in state_counts.most_common():
                    state_total = sum(r.amount_total for r in records if r.state == state and r.amount_total)
                    result += f"  {state.title()}: {count} orders, ${state_total:,.2f}\n"
                result += "\n"
                
                # Vendor analysis
                vendor_data = defaultdict(lambda: {'orders': 0, 'total': 0})
                for record in records:
                    if record.partner_id:
                        vendor_name = record.partner_id.name
                        vendor_data[vendor_name]['orders'] += 1
                        vendor_data[vendor_name]['total'] += record.amount_total or 0
                
                sorted_vendors = sorted(vendor_data.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
                
                result += "TOP 10 VENDORS BY VALUE:\n"
                for i, (vendor_name, data) in enumerate(sorted_vendors, 1):
                    avg_order = data['total'] / data['orders'] if data['orders'] > 0 else 0
                    result += f"{i}. {vendor_name}: {data['orders']} orders, ${data['total']:,.2f} (avg: ${avg_order:,.2f})\n"
                
            elif model_name == 'purchase.order.line':
                result += f"Total Purchase Order Lines: {len(records)}\n\n"
                
                # Product analysis
                product_data = defaultdict(lambda: {'name': '', 'qty': 0, 'total': 0, 'orders': 0})
                
                for record in records:
                    if record.product_id:
                        product_id = record.product_id.id
                        product_data[product_id]['name'] = record.product_id.name
                        product_data[product_id]['qty'] += record.product_qty or 0
                        product_data[product_id]['total'] += record.price_subtotal or 0
                        product_data[product_id]['orders'] += 1
                
                sorted_products = sorted(product_data.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
                
                result += "TOP 10 PURCHASED PRODUCTS BY VALUE:\n"
                for i, (product_id, data) in enumerate(sorted_products, 1):
                    avg_price = data['total'] / data['qty'] if data['qty'] > 0 else 0
                    result += f"{i}. {data['name']}: {data['qty']:,.0f} units, ${data['total']:,.2f} (avg: ${avg_price:,.2f}/unit)\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in purchase analysis: {str(e)}")
            return f"Error analyzing purchase data: {str(e)}"
    
    def _analyze_manufacturing_data(self, records, message, model_name):
        """Analyze manufacturing-related data"""
        try:
            result = f"=== MANUFACTURING ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No manufacturing data found.\n"
            
            if model_name == 'mrp.production':
                result += f"Total Manufacturing Orders: {len(records)}\n\n"
                
                # Production state analysis
                from collections import Counter
                state_counts = Counter([r.state for r in records if r.state])
                
                result += "PRODUCTION ORDER STATUS:\n"
                for state, count in state_counts.most_common():
                    result += f"  {state.title()}: {count} orders\n"
                result += "\n"
                
                # Product analysis
                product_data = defaultdict(lambda: {'name': '', 'total_qty': 0, 'orders': 0})
                
                for record in records:
                    if record.product_id:
                        product_id = record.product_id.id
                        product_data[product_id]['name'] = record.product_id.name
                        product_data[product_id]['total_qty'] += record.product_qty or 0
                        product_data[product_id]['orders'] += 1
                
                sorted_products = sorted(product_data.items(), key=lambda x: x[1]['total_qty'], reverse=True)[:10]
                
                result += "TOP 10 MANUFACTURED PRODUCTS:\n"
                for i, (product_id, data) in enumerate(sorted_products, 1):
                    avg_qty = data['total_qty'] / data['orders'] if data['orders'] > 0 else 0
                    result += f"{i}. {data['name']}: {data['total_qty']:,.2f} units ({data['orders']} orders, avg: {avg_qty:.2f})\n"
                
            elif model_name == 'mrp.bom':
                result += f"Total Bills of Materials: {len(records)}\n\n"
                
                # BOM type analysis
                type_counts = Counter([r.type for r in records if r.type])
                
                result += "BOM TYPE BREAKDOWN:\n"
                for bom_type, count in type_counts.most_common():
                    result += f"  {bom_type.title()}: {count} BOMs\n"
                
            elif model_name == 'mrp.workcenter':
                result += f"Total Work Centers: {len(records)}\n\n"
                
                # Active work centers
                active_centers = len([r for r in records if r.active])
                result += f"Active Work Centers: {active_centers}\n"
                result += f"Inactive Work Centers: {len(records) - active_centers}\n\n"
                
                # Efficiency analysis if available
                efficiency_records = [r for r in records if hasattr(r, 'time_efficiency') and r.time_efficiency]
                if efficiency_records:
                    avg_efficiency = sum(r.time_efficiency for r in efficiency_records) / len(efficiency_records)
                    result += f"EFFICIENCY ANALYSIS:\n"
                    result += f"  Average Time Efficiency: {avg_efficiency:.1f}%\n"
                    result += f"  Work Centers with Efficiency Data: {len(efficiency_records)}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in manufacturing analysis: {str(e)}")
            return f"Error analyzing manufacturing data: {str(e)}"
    
    def _analyze_financial_data(self, records, message, model_name):
        """Analyze additional financial data"""
        try:
            result = f"=== FINANCIAL ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No financial data found.\n"
            
            if model_name == 'account.payment':
                total_amount = sum(record.amount for record in records if record.amount)
                result += f"Total Payment Value: ${total_amount:,.2f}\n"
                result += f"Number of Payments: {len(records)}\n"
                result += f"Average Payment: ${total_amount / len(records):,.2f}\n\n"
                
                # Payment type analysis
                from collections import Counter
                type_counts = Counter([r.payment_type for r in records if r.payment_type])
                
                result += "PAYMENT TYPE BREAKDOWN:\n"
                for payment_type, count in type_counts.most_common():
                    type_total = sum(r.amount for r in records if r.payment_type == payment_type and r.amount)
                    result += f"  {payment_type.title()}: {count} payments, ${type_total:,.2f}\n"
                result += "\n"
                
                # Payment state analysis
                state_counts = Counter([r.state for r in records if r.state])
                
                result += "PAYMENT STATUS:\n"
                for state, count in state_counts.most_common():
                    result += f"  {state.title()}: {count} payments\n"
                
            elif model_name == 'account.bank.statement.line':
                result += f"Total Bank Statement Lines: {len(records)}\n\n"
                
                # Transaction analysis
                total_amount = sum(record.amount for record in records if record.amount)
                positive_amount = sum(record.amount for record in records if record.amount and record.amount > 0)
                negative_amount = sum(record.amount for record in records if record.amount and record.amount < 0)
                
                result += f"TRANSACTION SUMMARY:\n"
                result += f"  Total Amount: ${total_amount:,.2f}\n"
                result += f"  Inflows: ${positive_amount:,.2f}\n"
                result += f"  Outflows: ${abs(negative_amount):,.2f}\n"
                result += f"  Net Position: ${total_amount:,.2f}\n"
                
            elif model_name == 'account.tax':
                result += f"Total Tax Configurations: {len(records)}\n\n"
                
                # Tax type analysis
                type_counts = Counter([r.type_tax_use for r in records if r.type_tax_use])
                
                result += "TAX TYPE BREAKDOWN:\n"
                for tax_type, count in type_counts.most_common():
                    result += f"  {tax_type.title()}: {count} taxes\n"
                result += "\n"
                
                # Active vs inactive
                active_count = len([r for r in records if r.active])
                result += f"Active Taxes: {active_count}\n"
                result += f"Inactive Taxes: {len(records) - active_count}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in financial analysis: {str(e)}")
            return f"Error analyzing financial data: {str(e)}"
    
    def _analyze_partner_data(self, records, message, model_name):
        """Analyze partner/customer data"""
        try:
            result = f"=== PARTNER ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No partner data found.\n"
            
            if model_name == 'res.partner':
                result += f"Total Partners: {len(records)}\n\n"
                
                # Partner type analysis
                customers = len([r for r in records if r.customer_rank and r.customer_rank > 0])
                suppliers = len([r for r in records if r.supplier_rank and r.supplier_rank > 0])
                companies = len([r for r in records if r.is_company])
                individuals = len(records) - companies
                
                result += f"PARTNER TYPE BREAKDOWN:\n"
                result += f"  Customers: {customers}\n"
                result += f"  Suppliers: {suppliers}\n"
                result += f"  Companies: {companies}\n"
                result += f"  Individuals: {individuals}\n\n"
                
                # Geographic analysis
                if hasattr(records[0], 'country_id'):
                    from collections import Counter
                    country_counts = Counter([r.country_id.name for r in records if r.country_id])
                    
                    result += "TOP COUNTRIES:\n"
                    for country, count in country_counts.most_common(10):
                        result += f"  {country}: {count} partners\n"
                
            elif model_name == 'res.partner.category':
                result += f"Total Partner Categories: {len(records)}\n\n"
                
                # Active categories
                active_count = len([r for r in records if r.active])
                result += f"Active Categories: {active_count}\n"
                result += f"Inactive Categories: {len(records) - active_count}\n"
                
            elif model_name == 'res.partner.industry':
                result += f"Total Industries: {len(records)}\n\n"
                
                # Active industries
                active_count = len([r for r in records if r.active])
                result += f"Active Industries: {active_count}\n"
                result += f"Inactive Industries: {len(records) - active_count}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in partner analysis: {str(e)}")
            return f"Error analyzing partner data: {str(e)}"
    
    def _analyze_system_data(self, records, message, model_name):
        """Analyze system and communication data"""
        try:
            result = f"=== SYSTEM ANALYSIS ({model_name.upper()}) ===\n\n"
            
            if not records:
                return result + "No system data found.\n"
            
            if model_name == 'res.users':
                result += f"Total Users: {len(records)}\n\n"
                
                # Active users
                active_count = len([r for r in records if r.active])
                result += f"Active Users: {active_count}\n"
                result += f"Inactive Users: {len(records) - active_count}\n\n"
                
                # Recent login analysis
                recent_users = [r for r in records if r.login_date]
                if recent_users:
                    from datetime import datetime, timedelta
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    recent_active = [r for r in recent_users if r.login_date >= thirty_days_ago]
                    result += f"Users logged in last 30 days: {len(recent_active)}\n"
                
            elif model_name == 'calendar.event':
                result += f"Total Calendar Events: {len(records)}\n\n"
                
                # Event analysis
                active_events = len([r for r in records if r.active])
                all_day_events = len([r for r in records if r.allday])
                
                result += f"Active Events: {active_events}\n"
                result += f"All-day Events: {all_day_events}\n"
                result += f"Timed Events: {len(records) - all_day_events}\n"
                
            elif model_name == 'mail.message':
                result += f"Total Messages: {len(records)}\n\n"
                
                # Message type analysis
                from collections import Counter
                type_counts = Counter([r.message_type for r in records if r.message_type])
                
                result += "MESSAGE TYPE BREAKDOWN:\n"
                for msg_type, count in type_counts.most_common():
                    result += f"  {msg_type.title()}: {count} messages\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in system analysis: {str(e)}")
            return f"Error analyzing system data: {str(e)}"

    def _analyze_generic_data(self, records, source_name, fields, model_name):
        """Generic data analysis for any model"""
        try:
            result = f"=== {source_name.upper()} DATA ===\n\n"
            result += f"Total Records: {len(records)}\n\n"
            
            if not records:
                return result + "No records found.\n"
            
            # Sample first few records
            sample_size = min(10, len(records))
            result += f"SAMPLE DATA (showing {sample_size} of {len(records)} records):\n\n"
            
            for i, record in enumerate(records[:sample_size], 1):
                result += f"{i}. "
                # Try to get meaningful fields
                if hasattr(record, 'name') and record.name:
                    result += f"Name: {record.name}"
                if hasattr(record, 'display_name') and record.display_name:
                    result += f" ({record.display_name})"
                if hasattr(record, 'amount_total') and record.amount_total:
                    result += f" - Amount: ${record.amount_total:,.2f}"
                if hasattr(record, 'date') and record.date:
                    result += f" - Date: {record.date}"
                result += "\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in generic analysis: {str(e)}")
            return f"Error analyzing {source_name}: {str(e)}"
    
    def _extract_data_generically(self, records, source_name, requested_fields, model_name):
        """Extract data from any model/fields combination without hardcoded logic"""
        try:
            result = f"=== {source_name.upper()} DATA FROM kpak-17 ===\n"
            result += f"Model: {model_name}\n"
            result += f"Total Records: {len(records)}\n\n"
            
            if not records:
                return result + "No records found.\n"
            
            # Get sample of records for analysis (limit for performance)
            sample_size = min(50, len(records))  
            sample_records = records[:sample_size]
            
            # Validate and process requested fields
            available_fields = []
            for field_name in requested_fields:
                if hasattr(records[0], field_name):
                    available_fields.append(field_name)
                else:
                    _logger.warning(f"Field {field_name} not found on model {model_name}")
            
            if not available_fields:
                # Fallback to common fields if requested fields don't exist
                common_fields = ['name', 'id', 'create_date', 'write_date']
                for field_name in common_fields:
                    if hasattr(records[0], field_name):
                        available_fields.append(field_name)
                        
            result += f"Available Fields: {', '.join(available_fields)}\n\n"
            
            # Extract data from sample records
            result += "SAMPLE DATA:\n"
            for i, record in enumerate(sample_records[:10]):  # Show first 10 records
                result += f"\nRecord {i+1}:\n"
                for field_name in available_fields:
                    try:
                        field_value = getattr(record, field_name)
                        
                        # Handle different field types
                        if hasattr(field_value, 'name'):  # Many2one field
                            display_value = field_value.name
                        elif hasattr(field_value, 'strftime'):  # Date/Datetime field
                            display_value = field_value.strftime('%Y-%m-%d %H:%M:%S')
                        elif isinstance(field_value, (int, float)):
                            if field_name in ['amount_total', 'price', 'cost', 'value'] and field_value > 0:
                                display_value = f"${field_value:,.2f}"
                            else:
                                display_value = str(field_value)
                        else:
                            display_value = str(field_value) if field_value else 'None'
                            
                        result += f"  {field_name}: {display_value}\n"
                    except Exception as e:
                        result += f"  {field_name}: Error accessing ({str(e)})\n"
            
            # Add aggregate statistics for numeric fields
            result += "\nAGGREGATE STATISTICS:\n"
            for field_name in available_fields:
                try:
                    # Check if it's a numeric field by trying to sum
                    numeric_values = []
                    for record in records[:100]:  # Check first 100 records
                        try:
                            value = getattr(record, field_name)
                            if isinstance(value, (int, float)) and value is not False:
                                numeric_values.append(value)
                        except:
                            continue
                    
                    if numeric_values and len(numeric_values) > 1:
                        total = sum(numeric_values)
                        avg = total / len(numeric_values)
                        max_val = max(numeric_values)
                        min_val = min(numeric_values)
                        
                        if field_name in ['amount_total', 'price', 'cost', 'value']:
                            result += f"  {field_name}: Total=${total:,.2f}, Avg=${avg:,.2f}, Max=${max_val:,.2f}, Min=${min_val:,.2f}\n"
                        else:
                            result += f"  {field_name}: Total={total:,.0f}, Avg={avg:,.1f}, Max={max_val}, Min={min_val}\n"
                            
                except Exception as e:
                    continue
            
            # Add record distribution info
            result += f"\nRECORD DISTRIBUTION:\n"
            result += f"  Showing {min(10, len(sample_records))} of {len(records)} total records\n"
            
            # Add timestamp for data freshness
            result += f"\nData extracted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in generic data extraction: {str(e)}")
            return f"Error extracting data from {source_name}: {str(e)}"
    
    def _get_db_connection_params(self):
        """Extract database connection parameters from Odoo configuration"""
        try:
            # Get database parameters from Odoo's environment
            db_name = self.env.cr.dbname
            
            # Get connection parameters from Odoo's config
            import odoo
            config = odoo.tools.config
            
            return {
                'host': config.get('db_host') or 'localhost',
                'port': config.get('db_port') or 5432,
                'database': db_name,
                'user': config.get('db_user') or 'odoo',
                'password': config.get('db_password') or ''
            }
        except Exception as e:
            _logger.error(f"Error getting DB connection params: {str(e)}")
            # Fallback to default values
            return {
                'host': 'localhost',
                'port': 5432,
                'database': 'kpak',
                'user': 'hamid',
                'password': ''
            }
    
    def _extract_postgres_schema(self):
        """Extract real PostgreSQL database schema information using Odoo's database connection"""
        try:
            _logger.info("Extracting PostgreSQL schema using Odoo's database connection")
            
            # Use Odoo's existing database cursor
            cursor = self.env.cr
            
            # Query to get table information with column details
            schema_query = """
            SELECT 
                t.table_name,
                t.table_type,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default,
                CASE 
                    WHEN pk.column_name IS NOT NULL THEN 'PRIMARY KEY'
                    WHEN fk.column_name IS NOT NULL THEN 'FOREIGN KEY'
                    ELSE ''
                END as key_type,
                fk.foreign_table_name,
                fk.foreign_column_name
            FROM information_schema.tables t
            LEFT JOIN information_schema.columns c ON t.table_name = c.table_name
            LEFT JOIN (
                SELECT ku.table_name, ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku 
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.table_name = pk.table_name AND c.column_name = pk.column_name
            LEFT JOIN (
                SELECT 
                    ku1.table_name,
                    ku1.column_name,
                    ku2.table_name as foreign_table_name,
                    ku2.column_name as foreign_column_name
                FROM information_schema.referential_constraints rc
                JOIN information_schema.key_column_usage ku1 
                    ON rc.constraint_name = ku1.constraint_name
                JOIN information_schema.key_column_usage ku2 
                    ON rc.unique_constraint_name = ku2.constraint_name
            ) fk ON c.table_name = fk.table_name AND c.column_name = fk.column_name
            WHERE t.table_schema = 'public' 
                AND t.table_type = 'BASE TABLE'
                AND t.table_name NOT LIKE 'pg_%'
                AND t.table_name NOT LIKE 'sql_%'
            ORDER BY t.table_name, c.ordinal_position;
            """
            
            cursor.execute(schema_query)
            rows = cursor.fetchall()
            
            # Organize schema information
            tables = {}
            for row in rows:
                table_name = row[0]  # table_name
                column_name = row[2]  # column_name
                data_type = row[3]    # data_type
                is_nullable = row[4]  # is_nullable
                column_default = row[5]  # column_default
                key_type = row[6]     # key_type
                foreign_table_name = row[7]  # foreign_table_name
                foreign_column_name = row[8]  # foreign_column_name
                
                if table_name not in tables:
                    tables[table_name] = {
                        'columns': [],
                        'primary_keys': [],
                        'foreign_keys': [],
                        'record_count': 0
                    }
                
                column_info = {
                    'name': column_name,
                    'type': data_type,
                    'nullable': is_nullable == 'YES',
                    'default': column_default
                }
                
                if key_type == 'PRIMARY KEY':
                    tables[table_name]['primary_keys'].append(column_name)
                elif key_type == 'FOREIGN KEY':
                    tables[table_name]['foreign_keys'].append({
                        'column': column_name,
                        'references_table': foreign_table_name,
                        'references_column': foreign_column_name
                    })
                
                tables[table_name]['columns'].append(column_info)
            
            # Get record counts for each table
            for table_name in tables.keys():
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    result = cursor.fetchone()
                    tables[table_name]['record_count'] = result[0]
                except Exception as e:
                    _logger.warning(f"Could not get count for table {table_name}: {str(e)}")
                    tables[table_name]['record_count'] = 0
            
            _logger.info(f"Successfully extracted schema for {len(tables)} tables")
            return tables
            
        except Exception as e:
            _logger.error(f"Error extracting PostgreSQL schema: {str(e)}")
            return {}
    
    def _get_available_models(self):
        """Get comprehensive information about available Odoo models"""
        try:
            return self._get_comprehensive_schema()
                
        except Exception as e:
            _logger.error(f"Error in _get_available_models: {str(e)}")
            return self._get_basic_schema_fallback()
    
    def _get_comprehensive_schema(self):
        """Get comprehensive schema information based on actual kpak-17 database structure"""
        try:
            schema_info = "COMPLETE KPAK-17 DATABASE SCHEMA FOR COMPREHENSIVE BUSINESS ANALYSIS:\n\n"
            
            # COMPLETE BUSINESS MODELS FROM KPAK_SCHEMA.SQL - 818 TABLES TOTAL
            all_models = [
                # ===== CRM & SALES PIPELINE =====
                ('crm.lead', 'CRM Leads/Opportunities', 
                 ['id', 'name', 'partner_id', 'active', 'email_from', 'website', 'team_id', 'description', 'contact_name', 'partner_name', 'type', 'priority', 'date_closed', 'stage_id', 'user_id', 'date_open', 'day_open', 'day_close', 'date_last_stage_update', 'date_conversion', 'expected_revenue', 'probability', 'phone', 'mobile', 'function', 'company_name', 'street', 'city', 'state_id', 'country_id', 'zip', 'title']),
                
                ('crm.stage', 'CRM Pipeline Stages', 
                 ['id', 'name', 'sequence', 'requirements', 'team_id', 'fold', 'is_won', 'probability', 'on_change']),
                
                ('crm.team', 'CRM Sales Teams', 
                 ['id', 'name', 'active', 'company_id', 'user_id', 'color', 'use_opportunities', 'invoiced_target', 'sequence', 'use_leads', 'assignment_optout', 'assignment_domain', 'alias_id', 'member_ids']),
                
                ('crm.team.member', 'CRM Team Members',
                 ['id', 'crm_team_id', 'user_id', 'active', 'assignment_optout', 'assignment_max', 'assignment_domain']),
                
                ('crm.tag', 'CRM Tags', 
                 ['id', 'name', 'color']),
                
                ('crm.lost.reason', 'CRM Lost Reasons', 
                 ['id', 'name', 'active']),
                
                ('crm.recurring.plan', 'CRM Recurring Plans',
                 ['id', 'name', 'active', 'number_of_months', 'unit', 'extra_recurring']),
                
                # ===== CUSTOMER & PARTNER MANAGEMENT =====
                ('res.partner', 'Customers/Partners/Vendors', 
                 ['id', 'name', 'complete_name', 'date', 'title', 'parent_id', 'ref', 'lang', 'tz', 'user_id', 'email', 'phone', 'mobile', 'website', 'customer_rank', 'supplier_rank', 'is_company', 'street', 'street2', 'city', 'state_id', 'zip', 'country_id', 'category_id', 'industry_id', 'comment', 'credit_limit', 'active', 'employee', 'function', 'create_date', 'write_date']),
                
                ('res.partner.category', 'Partner Categories', 
                 ['id', 'name', 'color', 'parent_id', 'active']),
                
                ('res.partner.industry', 'Partner Industries', 
                 ['id', 'name', 'full_name', 'active']),
                
                ('res.partner.title', 'Partner Titles',
                 ['id', 'name', 'shortcut', 'domain']),
                
                ('res.partner.bank', 'Partner Bank Accounts',
                 ['id', 'acc_number', 'acc_holder_name', 'partner_id', 'bank_id', 'sequence', 'currency_id', 'company_id']),
                
                # ===== SALES & REVENUE =====
                ('sale.order', 'Sales Orders', 
                 ['id', 'name', 'partner_id', 'partner_invoice_id', 'partner_shipping_id', 'amount_total', 'amount_untaxed', 'amount_tax', 'date_order', 'validity_date', 'state', 'currency_id', 'user_id', 'team_id', 'company_id', 'pricelist_id', 'payment_term_id', 'fiscal_position_id', 'require_signature', 'require_payment', 'confirmation_date', 'commitment_date', 'expected_date', 'opportunity_id', 'client_order_ref', 'origin', 'note', 'invoice_status', 'campaign_id', 'medium_id', 'source_id']),
                
                ('sale.order.line', 'Sales Order Lines (Product Sales)', 
                 ['id', 'order_id', 'product_id', 'name', 'product_uom_qty', 'qty_delivered', 'qty_invoiced', 'qty_to_invoice', 'price_unit', 'price_subtotal', 'price_total', 'price_tax', 'discount', 'product_uom', 'customer_lead', 'invoice_status', 'sequence', 'analytic_distribution', 'is_expense', 'is_service', 'product_updatable', 'product_template_id']),
                
                ('sale.order.template', 'Sales Order Templates',
                 ['id', 'name', 'active', 'note', 'number_of_days', 'require_signature', 'require_payment', 'mail_template_id']),
                
                ('sale.order.template.line', 'Sales Order Template Lines',
                 ['id', 'sale_order_template_id', 'sequence', 'product_id', 'name', 'product_uom_qty', 'product_uom_id', 'discount']),
                
                # ===== PRODUCTS & INVENTORY =====
                ('product.product', 'Products (Variants)', 
                 ['id', 'product_tmpl_id', 'default_code', 'barcode', 'active', 'weight', 'volume', 'combination_indices']),
                
                ('product.template', 'Product Templates', 
                 ['id', 'name', 'sequence', 'description', 'detailed_type', 'type', 'categ_id', 'list_price', 'standard_price', 'volume', 'weight', 'sale_ok', 'purchase_ok', 'uom_id', 'uom_po_id', 'company_id', 'active', 'color', 'currency_id', 'cost_method', 'valuation', 'tracking', 'description_sale', 'description_purchase', 'default_location_id', 'responsible_id']),
                
                ('product.category', 'Product Categories', 
                 ['id', 'name', 'complete_name', 'parent_id', 'parent_path', 'child_id', 'product_count', 'removal_strategy_id', 'packaging_reserve_method', 'property_account_income_categ_id', 'property_account_expense_categ_id', 'property_stock_account_input_categ_id', 'property_stock_account_output_categ_id', 'property_stock_valuation_account_id']),
                
                ('product.attribute', 'Product Attributes',
                 ['id', 'name', 'sequence', 'create_variant', 'display_type', 'visibility']),
                
                ('product.attribute.value', 'Product Attribute Values',
                 ['id', 'name', 'attribute_id', 'sequence', 'color', 'is_used_on_products']),
                
                ('product.tag', 'Product Tags',
                 ['id', 'name', 'color']),
                
                ('product.pricelist', 'Product Pricelists',
                 ['id', 'name', 'active', 'item_ids', 'currency_id', 'company_id', 'sequence', 'discount_policy']),
                
                ('product.pricelist.item', 'Pricelist Items',
                 ['id', 'pricelist_id', 'applied_on', 'categ_id', 'product_tmpl_id', 'product_id', 'min_quantity', 'fixed_price', 'percent_price', 'base', 'base_pricelist_id', 'price_discount', 'price_round', 'price_surcharge', 'price_min_margin', 'price_max_margin', 'company_id', 'currency_id', 'date_start', 'date_end', 'compute_price']),
                
                ('product.supplierinfo', 'Product Suppliers',
                 ['id', 'partner_id', 'product_id', 'product_tmpl_id', 'product_name', 'product_code', 'sequence', 'min_qty', 'price', 'company_id', 'currency_id', 'date_start', 'date_end', 'delay']),
                
                # ===== STOCK & WAREHOUSE MANAGEMENT =====
                ('stock.quant', 'Stock/Inventory Quantities', 
                 ['id', 'product_id', 'location_id', 'lot_id', 'package_id', 'owner_id', 'quantity', 'available_quantity', 'reserved_quantity', 'value', 'accounting_date', 'company_id', 'in_date', 'create_date', 'write_date']),
                
                ('stock.move', 'Stock Movements/Transfers', 
                 ['id', 'name', 'sequence', 'priority', 'create_date', 'date', 'company_id', 'product_id', 'description_picking', 'product_qty', 'product_uom_qty', 'product_uom', 'location_id', 'location_dest_id', 'partner_id', 'move_line_ids', 'state', 'scrapped', 'to_refund', 'value', 'remaining_qty', 'remaining_value', 'price_unit', 'origin', 'procure_method', 'warehouse_id', 'picking_id', 'inventory_id', 'rule_id', 'push_rule_id']),
                
                ('stock.move.line', 'Stock Move Lines',
                 ['id', 'move_id', 'picking_id', 'product_id', 'product_uom_id', 'product_qty', 'qty_done', 'package_id', 'package_level_id', 'result_package_id', 'lot_id', 'lot_name', 'owner_id', 'location_id', 'location_dest_id', 'date', 'reference', 'state', 'company_id']),
                
                ('stock.picking', 'Stock Transfers/Deliveries',
                 ['id', 'name', 'sequence', 'priority', 'backorder_id', 'move_type', 'state', 'group_id', 'partner_id', 'date', 'scheduled_date', 'date_done', 'location_id', 'location_dest_id', 'picking_type_id', 'company_id', 'move_lines', 'note', 'origin', 'weight_bulk', 'weight', 'carrier_id', 'carrier_tracking_ref', 'number_of_packages']),
                
                ('stock.picking.type', 'Operation Types',
                 ['id', 'name', 'color', 'sequence', 'sequence_code', 'default_location_src_id', 'default_location_dest_id', 'code', 'return_picking_type_id', 'show_entire_packs', 'warehouse_id', 'active', 'use_create_lots', 'use_existing_lots', 'print_label', 'show_operations', 'show_reserved', 'reservation_method', 'reservation_days_before', 'reservation_days_before_priority', 'auto_show_reception_report', 'auto_print_delivery_slip', 'auto_print_reception_report', 'count_picking_ready', 'count_picking_draft', 'count_picking_waiting', 'count_picking_late', 'barcode_nomenclature_id']),
                
                ('stock.warehouse', 'Warehouses',
                 ['id', 'name', 'active', 'partner_id', 'view_location_id', 'lot_stock_id', 'code', 'company_id', 'reception_steps', 'delivery_steps', 'wh_input_stock_loc_id', 'wh_qc_stock_loc_id', 'wh_output_stock_loc_id', 'wh_pack_stock_loc_id', 'mto_pull_id', 'pick_type_id', 'pack_type_id', 'out_type_id', 'in_type_id', 'int_type_id', 'crossdock_route_id', 'reception_route_id', 'delivery_route_id', 'route_ids']),
                
                ('stock.location', 'Inventory Locations',
                 ['id', 'name', 'complete_name', 'active', 'usage', 'location_id', 'parent_path', 'child_ids', 'comment', 'posx', 'posy', 'posz', 'company_id', 'scrap_location', 'return_location', 'removal_strategy_id', 'putaway_rule_ids', 'barcode', 'cyclic_inventory_frequency']),
                
                ('stock.warehouse.orderpoint', 'Reordering Rules',
                 ['id', 'name', 'active', 'warehouse_id', 'location_id', 'product_id', 'product_min_qty', 'product_max_qty', 'qty_multiple', 'group_id', 'company_id', 'rule_ids']),
                
                ('stock.lot', 'Lots/Serial Numbers',
                 ['id', 'name', 'ref', 'product_id', 'product_qty', 'create_date', 'use_date', 'removal_date', 'alert_date', 'company_id', 'note', 'product_uom_id']),
                
                # ===== FINANCIAL & ACCOUNTING =====
                ('account.move', 'Invoices/Journal Entries', 
                 ['id', 'name', 'ref', 'state', 'move_type', 'partner_id', 'commercial_partner_id', 'date', 'invoice_date', 'invoice_date_due', 'currency_id', 'company_id', 'amount_untaxed', 'amount_tax', 'amount_total', 'amount_residual', 'payment_state', 'invoice_payment_term_id', 'journal_id', 'auto_post', 'to_check', 'posted_before', 'invoice_origin', 'invoice_cash_rounding_id', 'invoice_vendor_bill_id', 'invoice_source_email', 'invoice_partner_bank_id', 'fiscal_position_id', 'invoice_incoterm_id', 'invoice_payment_ref', 'payment_reference', 'reversed_entry_id', 'tax_totals', 'invoice_has_outstanding', 'is_move_sent']),
                
                ('account.move.line', 'Invoice/Accounting Lines', 
                 ['id', 'move_id', 'company_id', 'company_currency_id', 'account_id', 'partner_id', 'name', 'date', 'debit', 'credit', 'balance', 'amount_currency', 'currency_id', 'reconciled', 'blocked', 'date_maturity', 'analytic_distribution', 'product_id', 'quantity', 'price_unit', 'price_subtotal', 'price_total', 'discount', 'tax_ids', 'tax_line_id', 'tax_group_id', 'tax_base_amount', 'tax_repartition_line_id', 'exclude_from_invoice_tab', 'is_rounding_line', 'display_type', 'purchase_line_id', 'sale_line_ids']),
                
                ('account.journal', 'Accounting Journals', 
                 ['id', 'name', 'code', 'type', 'active', 'sequence', 'currency_id', 'company_id', 'default_account_id', 'suspense_account_id', 'restrict_mode_hash_table', 'check_chronology', 'color', 'show_on_dashboard', 'journal_group_ids', 'secure_sequence_id', 'refund_sequence', 'payment_debit_account_id', 'payment_credit_account_id', 'bank_account_id', 'bank_statements_source', 'bank_acc_number', 'bank_id', 'post_at', 'alias_id']),
                
                ('account.account', 'Chart of Accounts', 
                 ['id', 'name', 'code', 'deprecated', 'used', 'user_type_id', 'internal_type', 'internal_group', 'reconcile', 'tax_ids', 'note', 'company_id', 'currency_id', 'current_balance', 'allowed_journal_ids', 'opening_debit', 'opening_credit', 'opening_balance', 'related_taxes_amount', 'tag_ids', 'group_id', 'root_id', 'is_off_balance']),
                
                ('account.analytic.account', 'Analytic Accounts',
                 ['id', 'name', 'code', 'active', 'partner_id', 'company_id', 'currency_id', 'balance', 'debit', 'credit']),
                
                ('account.analytic.line', 'Analytic Lines',
                 ['id', 'name', 'date', 'amount', 'unit_amount', 'account_id', 'partner_id', 'user_id', 'tag_ids', 'company_id', 'currency_id', 'group_id', 'ref', 'move_id', 'product_id', 'product_uom_id', 'general_account_id', 'code', 'validated', 'project_id', 'task_id', 'category', 'so_line', 'holiday_id']),
                
                ('account.payment', 'Payments',
                 ['id', 'name', 'date', 'amount', 'currency_id', 'payment_type', 'partner_type', 'partner_id', 'destination_account_id', 'journal_id', 'company_id', 'hide_payment_method', 'payment_method_line_id', 'payment_token_id', 'payment_transaction_id', 'state', 'is_reconciled', 'is_matched', 'partner_bank_id', 'communication', 'qr_code', 'payment_reference', 'message_main_attachment_id']),
                
                ('account.bank.statement', 'Bank Statements',
                 ['id', 'name', 'reference', 'date', 'balance_start', 'balance_end_real', 'company_id', 'journal_id', 'currency_id', 'accounting_date', 'is_valid_balance_start', 'previous_statement_id', 'state']),
                
                ('account.bank.statement.line', 'Bank Statement Lines',
                 ['id', 'statement_id', 'sequence', 'account_number', 'partner_name', 'transaction_type', 'payment_ref', 'amount', 'foreign_currency_id', 'amount_currency', 'date', 'partner_id', 'narration', 'ref', 'internal_index', 'move_id', 'is_reconciled', 'country_code']),
                
                ('account.tax', 'Taxes',
                 ['id', 'name', 'type_tax_use', 'tax_scope', 'amount_type', 'active', 'company_id', 'sequence', 'amount', 'description', 'price_include', 'include_base_amount', 'analytic', 'tag_ids', 'tax_group_id', 'hide_tax_exigibility', 'tax_exigibility', 'cash_basis_transition_account_id', 'invoice_repartition_line_ids', 'refund_repartition_line_ids', 'country_id', 'country_code']),
                
                # ===== PURCHASING =====
                ('purchase.order', 'Purchase Orders', 
                 ['id', 'name', 'partner_id', 'partner_ref', 'currency_id', 'state', 'date_order', 'date_approve', 'date_planned', 'company_id', 'amount_untaxed', 'amount_tax', 'amount_total', 'notes', 'invoice_status', 'reception_count', 'invoice_count', 'user_id', 'origin', 'group_id', 'payment_term_id', 'fiscal_position_id', 'incoterm_id', 'receipt_reminder_email', 'reminder_date_before_receipt', 'mail_reminder_confirmed', 'mail_receipt_confirmed', 'dest_address_id', 'default_location_dest_id_usage', 'picking_count', 'picking_ids']),
                
                ('purchase.order.line', 'Purchase Order Lines', 
                 ['id', 'name', 'sequence', 'product_id', 'product_qty', 'qty_received', 'qty_invoiced', 'product_uom', 'price_unit', 'price_subtotal', 'price_total', 'price_tax', 'date_planned', 'order_id', 'company_id', 'state', 'invoice_lines', 'move_ids', 'orderpoint_id', 'account_analytic_id', 'analytic_tag_ids', 'move_dest_ids', 'product_packaging_qty', 'product_packaging_id', 'taxes_id', 'partner_id', 'currency_id', 'date_order', 'display_type', 'propagate_cancel']),
                
                # ===== HUMAN RESOURCES =====
                ('hr.employee', 'Employees', 
                 ['id', 'resource_id', 'name', 'active', 'country_id', 'gender', 'marital', 'birthday', 'ssnid', 'identification_id', 'passport_id', 'bank_account_id', 'address_id', 'work_phone', 'mobile_phone', 'work_email', 'personal_email', 'work_location', 'department_id', 'job_id', 'parent_id', 'coach_id', 'user_id', 'company_id', 'employee_type', 'resource_calendar_id', 'tz', 'color', 'pin', 'barcode', 'certificate', 'study_field', 'study_school', 'emergency_contact', 'emergency_phone', 'km_home_work', 'google_drive_link', 'job_title', 'work_contact_id', 'private_car_plate', 'spouse_complete_name', 'spouse_birthdate', 'children', 'place_of_birth', 'country_of_birth', 'visa_no', 'permit_no', 'visa_expire', 'additional_note', 'private_email']),
                
                ('hr.department', 'HR Departments', 
                 ['id', 'name', 'complete_name', 'active', 'company_id', 'parent_id', 'manager_id', 'note', 'color', 'master_department_id', 'member_ids', 'total_employee', 'jobs_ids', 'absence_of_today', 'allocation_to_approve_count', 'leave_to_approve_count', 'expense_to_approve_count', 'timesheet_to_approve_count', 'holidays_count']),
                
                ('hr.job', 'Job Positions', 
                 ['id', 'name', 'expected_employees', 'no_of_employee', 'no_of_recruitment', 'no_of_hired_employee', 'description', 'requirements', 'department_id', 'company_id', 'state', 'website_published', 'is_favorite', 'address_id', 'hr_responsible_id', 'contract_type_id', 'sequence', 'application_count', 'application_ids', 'survey_id', 'alias_id', 'color']),
                
                ('hr.employee.category', 'Employee Tags',
                 ['id', 'name', 'color', 'employee_ids']),
                
                ('hr.departure.reason', 'Departure Reasons',
                 ['id', 'name', 'sequence']),
                
                ('hr.work.location', 'Work Locations',
                 ['id', 'name', 'active', 'address_id', 'company_id', 'location_number']),
                
                # ===== MANUFACTURING (MRP) =====
                ('mrp.production', 'Manufacturing Orders',
                 ['id', 'name', 'origin', 'product_id', 'product_tmpl_id', 'product_qty', 'product_uom_id', 'product_uom_qty', 'bom_id', 'routing_id', 'location_src_id', 'location_dest_id', 'date_planned_start', 'date_planned_finished', 'date_start', 'date_finished', 'state', 'availability', 'reserve_visible', 'user_id', 'company_id', 'move_raw_ids', 'move_finished_ids', 'finished_move_line_ids', 'workorder_ids', 'analytic_account_id', 'picking_type_id', 'procurement_group_id', 'orderpoint_id', 'propagate_cancel', 'scrap_ids', 'scrap_count', 'priority', 'is_locked', 'show_final_lots', 'production_location_id', 'picking_ids', 'delivery_count', 'lot_producing_id', 'components_availability_state', 'reservation_state', 'json_popover', 'show_lots', 'consumption']),
                
                ('mrp.bom', 'Bills of Materials',
                 ['id', 'active', 'sequence', 'product_tmpl_id', 'product_id', 'product_qty', 'product_uom_id', 'type', 'company_id', 'consumption', 'routing_id', 'ready_to_produce', 'picking_type_id', 'bom_line_ids', 'byproduct_ids', 'operation_ids', 'version', 'code']),
                
                ('mrp.bom.line', 'Bill of Materials Lines',
                 ['id', 'product_id', 'product_tmpl_id', 'company_id', 'product_qty', 'product_uom_id', 'sequence', 'routing_workcenter_id', 'bom_id', 'possible_bom_product_template_attribute_value_ids', 'bom_product_template_attribute_value_ids', 'operation_id', 'child_bom_id', 'child_line_ids', 'attachments_count', 'allowed_operation_ids']),
                
                ('mrp.workcenter', 'Work Centers',
                 ['id', 'name', 'active', 'sequence', 'color', 'working_state', 'blocked_time', 'productive_time', 'oee', 'oee_target', 'performance', 'availability', 'quality', 'capacity', 'time_efficiency', 'resource_calendar_id', 'company_id', 'resource_id', 'costs_hour', 'time_start', 'time_stop', 'alternative_workcenter_ids', 'tag_ids', 'operation_ids', 'order_ids', 'check_ids']),
                
                ('mrp.workorder', 'Work Orders',
                 ['id', 'name', 'workcenter_id', 'working_state', 'production_id', 'product_id', 'product_uom_id', 'qty_production', 'qty_producing', 'qty_remaining', 'qty_produced', 'state', 'leave_id', 'date_planned_start', 'date_planned_finished', 'date_start', 'date_finished', 'duration_expected', 'duration', 'duration_unit', 'duration_percent', 'progress', 'operation_id', 'worksheet', 'worksheet_type', 'worksheet_google_slide', 'operation_note', 'next_work_order_id', 'scrap_ids', 'scrap_count', 'production_date', 'json_popover', 'costs_hour', 'employee_ids', 'employee_costs_hour']),
                
                # ===== ADDITIONAL CORE BUSINESS TABLES =====
                ('res.users', 'System Users',
                 ['id', 'partner_id', 'login', 'password', 'new_password', 'signature', 'active', 'action_id', 'groups_id', 'log_ids', 'login_date', 'share', 'companies_count', 'tz_offset', 'company_id', 'company_ids', 'notification_type', 'odoobot_state', 'odoobot_failed', 'sel_groups_1_9_10', 'in_group_1', 'in_group_2', 'in_group_3', 'in_group_4', 'in_group_5', 'in_group_6', 'in_group_7', 'in_group_8', 'in_group_9', 'in_group_10']),
                
                ('res.company', 'Companies',
                 ['id', 'name', 'partner_id', 'currency_id', 'sequence', 'create_date', 'parent_id', 'child_ids', 'report_header', 'report_footer', 'logo', 'font', 'primary_color', 'secondary_color', 'color', 'layout_background', 'external_report_layout_id', 'base_onboarding_company_state', 'paperformat_id', 'company_registry', 'email', 'phone', 'website', 'vat', 'company_details', 'nomenclature_id', 'po_lead', 'security_lead', 'manufacturing_lead']),
                
                ('mail.message', 'Messages/Communications', 
                 ['id', 'subject', 'date', 'body', 'attachment_ids', 'author_id', 'email_from', 'reply_to', 'record_name', 'model', 'res_id', 'parent_id', 'message_type', 'subtype_id', 'is_internal', 'website_published', 'starred_partner_ids', 'needaction', 'needaction_partner_ids', 'has_error', 'mail_activity_type_id', 'mail_server_id', 'moderation_status', 'moderator_id', 'email_layout_xmlid', 'add_sign', 'message_id', 'reply_to_force_new', 'is_note']),
                
                ('ir.attachment', 'File Attachments',
                 ['id', 'name', 'description', 'res_name', 'res_model', 'res_field', 'res_id', 'company_id', 'type', 'url', 'public', 'access_token', 'db_datas', 'store_fname', 'file_size', 'checksum', 'mimetype', 'index_content', 'create_date', 'create_uid', 'write_date', 'write_uid', 'original_id', 'thumbnail']),
                
                ('calendar.event', 'Calendar Events',
                 ['id', 'name', 'active', 'user_id', 'partner_ids', 'categ_ids', 'attendee_ids', 'description', 'privacy', 'show_as', 'location', 'videocall_location', 'start', 'stop', 'allday', 'start_date', 'stop_date', 'duration', 'rrule', 'rrule_type', 'event_tz', 'end_type', 'interval', 'count', 'mo', 'tu', 'we', 'th', 'fr', 'sa', 'su', 'month_by', 'day', 'weekday', 'byday', 'until', 'alarm_ids', 'recurrency', 'recurrent_id', 'recurrent_id_date', 'follow_recurrence', 'invalid_email_partner_ids', 'message_main_attachment_id']),
                
                # ===== UTILITY/REFERENCE TABLES =====
                ('res.country', 'Countries',
                 ['id', 'name', 'code', 'address_format', 'address_view_id', 'currency_id', 'image', 'phone_code', 'country_group_ids', 'name_position', 'vat_label', 'state_required', 'zip_required', 'state_ids', 'enforce_cities']),
                
                ('res.country.state', 'Country States',
                 ['id', 'country_id', 'name', 'code']),
                
                ('res.currency', 'Currencies',
                 ['id', 'name', 'symbol', 'rate', 'rate_ids', 'rounding', 'decimal_places', 'active', 'position', 'date', 'currency_unit_label', 'currency_subunit_label', 'is_current_company_currency', 'full_name']),
                
                ('uom.uom', 'Units of Measure',
                 ['id', 'name', 'category_id', 'factor', 'factor_inv', 'rounding', 'active', 'uom_type', 'measure_type', 'ratio']),
                
                ('uom.category', 'UoM Categories',
                 ['id', 'name', 'measure_type']),
            ]
            
            for model_name, description, fields in all_models:
                try:
                    if model_name in self.env.registry:
                        record_count = self.env[model_name].search_count([])
                        schema_info += f"📊 {model_name} ({description}): {record_count:,} records\n"
                        # Show key fields (first 10 for readability)
                        key_fields = fields[:10]
                        schema_info += f"   Key Fields: {', '.join(key_fields)}{'...' if len(fields) > 10 else ''}\n\n"
                    else:
                        schema_info += f"❌ {model_name} ({description}): Module not installed\n\n"
                        
                except Exception as e:
                    schema_info += f"⚠️  {model_name} ({description}): Access restricted\n\n"
            
            schema_info += """
🎯 INTELLIGENT QUERY ROUTING EXAMPLES:
• CRM Analysis: "leads by stage" → crm.lead + crm.stage, "team performance" → crm.team + crm.lead
• Customer Analysis: "top customers" → res.partner + account.move/sale.order, "customer segments" → res.partner + res.partner.category  
• Product Performance: "best sellers" → sale.order.line + product.product, "inventory levels" → stock.quant + product.template
• Sales Analytics: "sales trends" → sale.order, "product sales" → sale.order.line + product.template
• Financial Analysis: "revenue by period" → account.move, "payment analysis" → account.move.line
• HR Analytics: "employee distribution" → hr.employee + hr.department, "job positions" → hr.job + hr.employee
• Communication Analysis: "message activity" → mail.message filtered by model/res_id

🔍 RELATIONSHIP PATTERNS:
• Partners → sale.order, account.move, crm.lead (via partner_id)
• Products → sale.order.line, purchase.order.line, stock.quant, account.move.line (via product_id)  
• CRM → crm.lead.stage_id → crm.stage, crm.lead.team_id → crm.team
• Sales → sale.order.partner_id → res.partner, sale.order.user_id → res.users
• HR → hr.employee.department_id → hr.department, hr.employee.job_id → hr.job
"""
            
            return schema_info
            
        except Exception as e:
            _logger.error(f"Error getting comprehensive schema: {str(e)}")
            return self._get_basic_schema_fallback()
    
    def _get_basic_schema_fallback(self):
        """Basic schema information as fallback"""
        return """AVAILABLE ODOO MODELS:

- res.partner (Customers/Vendors): Customer and vendor information
  Key fields: id, name, email, customer_rank, supplier_rank

- account.move (Invoices): Customer invoices and financial transactions  
  Key fields: id, name, partner_id, amount_total, invoice_date, move_type, state

- sale.order (Sales Orders): Sales order information
  Key fields: id, name, partner_id, amount_total, date_order, state

- product.product (Products): Product information
  Key fields: id, name, list_price, categ_id

Use these models to provide comprehensive business analysis."""
    
    def _get_accounting_schema_only(self):
        """Return schema information for only the two allowed accounting tables"""
        try:
            schema_info = "AVAILABLE ACCOUNTING TABLES:\n\n"
            
            # Check account_move table
            try:
                move_count = self.env['account.move'].search_count([])
                schema_info += f"- account_move (Journal Entries): {move_count:,} records\n"
                schema_info += "  Key fields: id, name, ref, date, journal_id, partner_id, amount_total, amount_tax, amount_untaxed, state, move_type, invoice_date, payment_state\n"
                schema_info += "  Financial fields: currency_id, company_id, fiscal_position_id, payment_reference\n\n"
            except Exception as e:
                schema_info += f"- account_move: Access error - {str(e)}\n\n"
            
            # Check account_move_line table  
            try:
                line_count = self.env['account.move.line'].search_count([])
                schema_info += f"- account_move_line (Journal Entry Lines): {line_count:,} records\n"
                schema_info += "  Key fields: id, name, move_id, account_id, partner_id, debit, credit, balance, amount_currency\n"
                schema_info += "  Additional fields: product_id, quantity, date, tax_line_id, analytic_distribution, reconciled\n"
            except Exception as e:
                schema_info += f"- account_move_line: Access error - {str(e)}\n"
            
            return schema_info
            
        except Exception as e:
            _logger.error(f"Error getting accounting schema: {str(e)}")
            return "Accounting tables: account_move (journal entries) and account_move_line (journal entry lines)"
    
    def _format_schema_for_llm(self, pg_schema):
        """Format PostgreSQL schema information for LLM consumption"""
        try:
            model_descriptions = []
            
            # Filter and prioritize important tables
            important_prefixes = ['sale_', 'purchase_', 'stock_', 'account_', 'product_', 
                                'res_partner', 'hr_', 'project_', 'mrp_', 'quality_']
            
            # Sort tables by importance and record count
            sorted_tables = sorted(pg_schema.items(), 
                                 key=lambda x: (
                                     any(x[0].startswith(prefix) for prefix in important_prefixes),
                                     x[1]['record_count']
                                 ), reverse=True)
            
            for table_name, table_info in sorted_tables[:50]:  # Limit to top 50 tables
                # Skip system tables
                if table_name.startswith(('ir_', 'base_', 'mail_')) and table_info['record_count'] == 0:
                    continue
                
                # Get main columns (skip internal Odoo fields)
                main_columns = []
                for col in table_info['columns']:
                    if col['name'] not in ['id', 'create_date', 'create_uid', 'write_date', 'write_uid']:
                        main_columns.append(f"{col['name']} ({col['type']})")
                
                if main_columns:
                    # Create readable description
                    description = self._get_table_description(table_name)
                    record_count = table_info['record_count']
                    
                    model_descriptions.append(
                        f"- {description}: {table_name} ({record_count:,} records)\n"
                        f"  Key columns: {', '.join(main_columns[:10])}"  # Show first 10 columns
                    )
            
            result = "\n".join(model_descriptions)
            _logger.info(f"Formatted schema for {len(model_descriptions)} tables")
            
            return result if result else "No accessible tables found in database schema."
            
        except Exception as e:
            _logger.error(f"Error formatting schema for LLM: {str(e)}")
            return "Error formatting database schema."
    
    def _get_table_description(self, table_name):
        """Generate human-readable description for database table"""
        descriptions = {
            'sale_order': 'Sales Orders',
            'sale_order_line': 'Sales Order Lines',
            'purchase_order': 'Purchase Orders', 
            'purchase_order_line': 'Purchase Order Lines',
            'stock_move': 'Inventory Movements',
            'stock_quant': 'Inventory Stock Levels',
            'stock_picking': 'Warehouse Pickings/Deliveries',
            'product_product': 'Product Variants',
            'product_template': 'Product Templates',
            'res_partner': 'Customers/Vendors/Partners',
            'account_move': 'Accounting Journal Entries',
            'account_move_line': 'Accounting Journal Entry Lines',
            'hr_employee': 'Employees',
            'project_project': 'Projects',
            'project_task': 'Project Tasks',
            'mrp_production': 'Manufacturing Orders',
            'mrp_bom': 'Bills of Materials',
            'quality_check': 'Quality Control Checks',
            'maintenance_request': 'Maintenance Requests',
            'fleet_vehicle': 'Fleet Vehicles'
        }
        
        return descriptions.get(table_name, table_name.replace('_', ' ').title())
    
    def _fallback_model_discovery(self):
        """Fallback method using Odoo model discovery when PostgreSQL fails"""
        try:
            # Common Odoo models to check
            models_to_check = [
                ('sale.order', 'Sales Orders', ['name', 'partner_id', 'amount_total', 'state', 'date_order']),
                ('res.partner', 'Customers/Partners', ['name', 'customer_rank', 'supplier_rank', 'country_id', 'email']),
                ('product.product', 'Products', ['name', 'categ_id', 'qty_available', 'standard_price', 'list_price']),
                ('stock.quant', 'Inventory Stock', ['product_id', 'location_id', 'quantity', 'lot_id']),
                ('stock.move', 'Stock Movements', ['name', 'product_id', 'product_uom_qty', 'state', 'date']),
                ('account.move', 'Accounting Moves', ['name', 'partner_id', 'amount_total', 'state', 'date', 'move_type']),
                ('purchase.order', 'Purchase Orders', ['name', 'partner_id', 'amount_total', 'state', 'date_order']),
                ('mrp.production', 'Manufacturing Orders', ['name', 'product_id', 'product_qty', 'state', 'date_start']),
                ('mrp.bom', 'Bills of Materials', ['product_tmpl_id', 'product_qty', 'type']),
                ('stock.picking', 'Delivery/Receipts', ['name', 'partner_id', 'state', 'scheduled_date', 'picking_type_id']),
                ('hr.employee', 'Employees', ['name', 'job_id', 'department_id', 'work_email']),
                ('project.project', 'Projects', ['name', 'partner_id', 'user_id', 'stage_id']),
                ('quality.check', 'Quality Checks', ['name', 'product_id', 'lot_id', 'quality_state']),
            ]
            
            available_models = []
            
            for model_name, description, suggested_fields in models_to_check:
                try:
                    # Try to access the model
                    records = self.env[model_name].search([], limit=1)
                    record_count = self.env[model_name].search_count([])
                    
                    # Validate suggested fields
                    valid_fields = []
                    if records:
                        for field in suggested_fields:
                            if hasattr(records[0], field):
                                valid_fields.append(field)
                    else:
                        # If no records, assume basic fields exist
                        valid_fields = ['name', 'id', 'create_date']
                    
                    model_info = {
                        'model': model_name,
                        'description': description,
                        'record_count': record_count,
                        'available_fields': valid_fields
                    }
                    available_models.append(model_info)
                    
                    _logger.info(f"Model {model_name}: {record_count} records, fields: {valid_fields}")
                    
                except Exception as e:
                    _logger.warning(f"Model {model_name} not accessible: {str(e)}")
                    continue
            
            # Format for LLM consumption
            model_descriptions = []
            for model in available_models:
                field_list = ', '.join(model['available_fields'])
                model_descriptions.append(
                    f"- {model['description']}: {model['model']} ({model['record_count']} records)\n"
                    f"  Available fields: {field_list}"
                )
            
            result = "\n".join(model_descriptions)
            _logger.info(f"Discovered {len(available_models)} accessible models in kpak-17")
            
            return result if result else "No accessible models found in kpak-17 installation."
            
        except Exception as e:
            _logger.error(f"Error in fallback model discovery: {str(e)}")
            return "Error discovering available models. Using comprehensive overview."
    
    def _analyze_sales_data(self, records, query):
        """Comprehensive sales analysis from kpak-17"""
        try:
            result = "=== SALES ANALYSIS FROM kpak-17 ===\n"
            result += f"Total Sales Orders: {len(records)}\n"
            
            # Calculate totals
            total_amount = sum(record.amount_total for record in records if record.amount_total)
            result += f"Total Sales Value: ${total_amount:,.2f}\n"
            
            # Always provide comprehensive year-wise breakdown - let LLM decide relevance
            from collections import defaultdict
            yearly_data = defaultdict(lambda: {'count': 0, 'total': 0.0})
            
            for record in records:
                if record.date_order:
                    year = record.date_order.year
                    yearly_data[year]['count'] += 1
                    yearly_data[year]['total'] += record.amount_total or 0.0
            
            if yearly_data:
                result += "\nYear-wise Breakdown:\n"
                for year in sorted(yearly_data.keys()):
                    data = yearly_data[year]
                    result += f"- {year}: {data['count']} orders, ${data['total']:,.2f}\n"
            
            # Recent orders
            recent_orders = records.filtered(lambda r: r.date_order).sorted('date_order', reverse=True)[:5]
            if recent_orders:
                result += "\nRecent Orders:\n"
                for order in recent_orders:
                    partner_name = order.partner_id.name if order.partner_id else "Unknown"
                    result += f"- {order.name}: {partner_name} - ${order.amount_total:,.2f} ({order.date_order.strftime('%Y-%m-%d')})\n"
            
            return result
            
        except Exception as e:
            return f"Error analyzing sales data: {str(e)}"
    
    def _analyze_product_data(self, records, query):
        """Product catalog analysis from kpak-17"""
        try:
            result = "=== PRODUCT CATALOG FROM kpak-17 ===\n"
            result += f"Total Products: {len(records)}\n"
            
            # Available products
            available = records.filtered(lambda p: p.qty_available > 0)
            result += f"Products in Stock: {len(available)}\n"
            
            # Categories
            categories = records.mapped('categ_id.name')
            unique_categories = list(set([cat for cat in categories if cat]))
            result += f"Product Categories: {', '.join(unique_categories[:10])}\n"
            
            # High-value products
            high_value = records.filtered(lambda p: p.standard_price > 100).sorted('standard_price', reverse=True)[:5]
            if high_value:
                result += "\nTop Value Products:\n"
                for product in high_value:
                    result += f"- {product.name}: ${product.standard_price:,.2f} (Stock: {product.qty_available})\n"
                    
            return result
            
        except Exception as e:
            return f"Error analyzing product data: {str(e)}"
    
    def _analyze_customer_data(self, records, query):
        """Customer analysis from kpak-17"""
        try:
            result = "=== CUSTOMER DATA FROM kpak-17 ===\n"
            
            customers = records.filtered(lambda p: p.customer_rank > 0)
            suppliers = records.filtered(lambda p: p.supplier_rank > 0)
            
            result += f"Total Customers: {len(customers)}\n"
            result += f"Total Suppliers: {len(suppliers)}\n"
            
            # Recent customers
            recent_customers = customers.sorted('create_date', reverse=True)[:5]
            if recent_customers:
                result += "\nRecent Customers:\n"
                for customer in recent_customers:
                    result += f"- {customer.name} ({customer.country_id.name if customer.country_id else 'No Country'})\n"
                    
            return result
            
        except Exception as e:
            return f"Error analyzing customer data: {str(e)}"
    
    def _analyze_manufacturing_data(self, records, query):
        """Manufacturing analysis from kpak-17"""
        try:
            result = "=== MANUFACTURING DATA FROM kpak-17 ===\n"
            result += f"Total Production Orders: {len(records)}\n"
            
            # Status breakdown
            states = records.mapped('state')
            from collections import Counter
            state_counts = Counter(states)
            
            result += "\nProduction Status:\n"
            for state, count in state_counts.most_common():
                result += f"- {state.title()}: {count}\n"
            
            # Recent productions
            recent = records.sorted('create_date', reverse=True)[:5]
            if recent:
                result += "\nRecent Production Orders:\n"
                for prod in recent:
                    product_name = prod.product_id.name if prod.product_id else "Unknown Product"
                    result += f"- {prod.name}: {product_name} (Qty: {prod.product_qty}) - {prod.state}\n"
                    
            return result
            
        except Exception as e:
            return f"Error analyzing manufacturing data: {str(e)}"
    
    def _analyze_inventory_data(self, records, query):
        """Inventory analysis from kpak-17"""
        try:
            result = "=== INVENTORY DATA FROM kpak-17 ===\n"
            result += f"Total Stock Records: {len(records)}\n"
            
            # Total quantities
            total_qty = sum(record.quantity for record in records if record.quantity > 0)
            result += f"Total Stock Quantity: {total_qty:,.0f}\n"
            
            # Top stock items
            high_stock = records.filtered(lambda r: r.quantity > 0).sorted('quantity', reverse=True)[:10]
            if high_stock:
                result += "\nTop Stock Items:\n"
                for item in high_stock:
                    product_name = item.product_id.name if item.product_id else "Unknown"
                    location_name = item.location_id.name if item.location_id else "Unknown Location"
                    result += f"- {product_name}: {item.quantity:,.0f} @ {location_name}\n"
                    
            return result
            
        except Exception as e:
            return f"Error analyzing inventory data: {str(e)}"
    
    def _analyze_financial_data(self, records, query):
        """Financial data analysis from kpak-17"""
        try:
            result = "=== FINANCIAL DATA FROM kpak-17 ===\n"
            result += f"Total Account Moves: {len(records)}\n"
            
            # Invoice analysis
            invoices = records.filtered(lambda r: r.move_type in ['out_invoice', 'in_invoice'])
            if invoices:
                total_amount = sum(inv.amount_total for inv in invoices if inv.amount_total)
                result += f"Total Invoice Amount: ${total_amount:,.2f}\n"
                
                # Recent invoices
                recent_invoices = invoices.sorted('create_date', reverse=True)[:5]
                result += "\nRecent Invoices:\n"
                for inv in recent_invoices:
                    partner_name = inv.partner_id.name if inv.partner_id else "Unknown"
                    result += f"- {inv.name}: {partner_name} - ${inv.amount_total:,.2f} ({inv.state})\n"
                    
            return result
            
        except Exception as e:
            return f"Error analyzing financial data: {str(e)}"
    
    def _analyze_generic_data(self, records, source_name, fields):
        """Generic data analysis for other models"""
        try:
            result = f"=== {source_name.upper()} FROM kpak-17 ===\n"
            result += f"Total Records: {len(records)}\n"
            
            # Show sample data
            sample_data = []
            for record in records[:5]:
                record_info = []
                for field in fields:
                    if hasattr(record, field):
                        value = getattr(record, field)
                        if hasattr(value, 'name'):  # Many2one field
                            value = value.name
                        elif hasattr(value, 'strftime'):  # Date field
                            value = value.strftime('%Y-%m-%d')
                        record_info.append(f"{field}: {value}")
                if record_info:
                    sample_data.append(" | ".join(record_info))
            
            if sample_data:
                result += f"\nSample {source_name} Records:\n"
                result += "\n".join(f"- {data}" for data in sample_data)
                
            return result
            
        except Exception as e:
            return f"Error analyzing {source_name} data: {str(e)}"
    
    def _get_comprehensive_overview(self):
        """Get comprehensive business overview from all available data sources"""
        try:
            overview = "=== COMPREHENSIVE BUSINESS OVERVIEW ===\n\n"
            
            # Current date and context
            current_date = fields.Date.today()
            overview += f"📅 Current Date: {current_date}\n"
            overview += f"🏢 System: Odoo ERP - Complete Business System\n"
            overview += f"💱 Currency: {self.env.company.currency_id.name}\n\n"
            
            # Add available business data modules
            business_modules = []
            
            # Customers & Partners
            try:
                partners = self.env['res.partner'].search([])
                customers = partners.filtered(lambda p: p.customer_rank > 0)
                suppliers = partners.filtered(lambda p: p.supplier_rank > 0)
                business_modules.append(f"👥 CUSTOMERS & PARTNERS: {len(partners):,} total ({len(customers)} customers, {len(suppliers)} suppliers)")
            except:
                business_modules.append("👥 CUSTOMERS & PARTNERS: Access not available")
            
            # Sales Orders  
            try:
                sales = self.env['sale.order'].search([])
                sales_total = sum(order.amount_total for order in sales if order.amount_total)
                business_modules.append(f"💰 SALES ORDERS: {len(sales):,} orders, ${sales_total:,.2f} total value")
            except:
                business_modules.append("💰 SALES ORDERS: Access not available")
            
            # Products
            try:
                products = self.env['product.product'].search([])
                business_modules.append(f"📦 PRODUCTS: {len(products):,} products available")
            except:
                business_modules.append("📦 PRODUCTS: Access not available")
            
            # Financial Data
            try:
                moves = self.env['account.move'].search([])
                total_invoices = moves.filtered(lambda m: m.move_type in ['out_invoice', 'in_invoice'])
                total_invoice_amount = sum(move.amount_total for move in total_invoices if move.amount_total)
                business_modules.append(f"🧾 FINANCIAL DATA: {len(moves):,} transactions, ${total_invoice_amount:,.2f} invoice value")
            except:
                business_modules.append("🧾 FINANCIAL DATA: Access not available")
            
            # Purchase Orders
            try:
                purchases = self.env['purchase.order'].search([])  
                purchase_total = sum(order.amount_total for order in purchases if order.amount_total)
                business_modules.append(f"🛒 PURCHASE ORDERS: {len(purchases):,} orders, ${purchase_total:,.2f} total value")
            except:
                business_modules.append("🛒 PURCHASE ORDERS: Access not available")
            
            # Inventory
            try:
                inventory = self.env['stock.quant'].search([])
                business_modules.append(f"📊 INVENTORY: {len(inventory):,} stock records")
            except:
                business_modules.append("📊 INVENTORY: Access not available")
            
            overview += "\n".join(business_modules) + "\n\n"
            
            overview += "💡 ANALYSIS CAPABILITIES:\n"
            overview += "• Customer Analysis: Top customers, customer trends, year-over-year comparisons\n"
            overview += "• Product Analysis: Best-selling products, product performance, inventory levels\n" 
            overview += "• Sales Analysis: Sales trends, revenue analysis, order patterns\n"
            overview += "• Financial Analysis: Invoice analysis, payment tracking, accounting reports\n"
            overview += "• Comparative Analysis: Year-over-year, period comparisons, growth analysis\n\n"
            
            # Journal Entry Lines
            try:
                _logger.info("Fetching journal entry lines for analysis")
                move_lines = self.env['account.move.line'].search([])
                _logger.info(f"Retrieved {len(move_lines)} journal entry lines")
                
                # Calculate totals
                total_debit = sum(line.debit for line in move_lines if line.debit)
                total_credit = sum(line.credit for line in move_lines if line.credit) 
                total_balance = sum(line.balance for line in move_lines if line.balance)
                
                # Recent lines
                from datetime import timedelta
                thirty_days_ago = fields.Date.today() - timedelta(days=30)
                recent_lines = move_lines.filtered(lambda l: l.date and l.date >= thirty_days_ago)
                
                # Lines with reconciliation info
                reconciled_lines = move_lines.filtered(lambda l: l.reconciled)
                
                overview += f"📋 JOURNAL ENTRY LINES:\n"
                overview += f"   • Total Entry Lines: {len(move_lines):,} lines\n"
                overview += f"   • Total Debits: ${total_debit:,.2f}\n"
                overview += f"   • Total Credits: ${total_credit:,.2f}\n"
                overview += f"   • Net Balance: ${total_balance:,.2f}\n"
                overview += f"   • Last 30 Days: {len(recent_lines):,} lines\n"
                overview += f"   • Reconciled Lines: {len(reconciled_lines):,}\n\n"
                    
            except Exception as e:
                _logger.error(f"Error accessing journal entry lines: {str(e)}")
                overview += f"📋 JOURNAL LINES: Access error - {str(e)}\n\n"
                
            # Add data freshness indicator
            overview += f"🎯 ACCOUNTING DATA STATUS:\n"
            overview += f"   • Data Timestamp: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            overview += f"   • System Status: Online & Active\n"
            overview += f"   • Database: Live Odoo Accounting Data\n"
            overview += f"   • Continuous Updates: Available\n\n"
            
            overview += "🚀 COMPREHENSIVE BUSINESS ANALYSIS READY:\n"
            overview += "   • Customer Analysis: Top customers, revenue trends, comparisons\n"
            overview += "   • Product Performance: Best-sellers, sales analytics, inventory\n"
            overview += "   • Sales Intelligence: Order trends, revenue analysis, forecasting\n"
            overview += "   • Financial Reporting: Invoice analysis, payment tracking, profitability\n"
            overview += "   • Operational Insights: Inventory, purchasing, employee performance\n\n"
            
            overview += "Ask me any business question about customers, products, sales,\n"
            overview += "finances, inventory, or any other aspect of your kpak-17 system!\n"
            
            # Log data size for debugging
            data_size = len(overview)
            _logger.info(f"Generated accounting overview for AI: {data_size} characters of accounting data")
            
            return overview
            
        except Exception as e:
            _logger.error(f"Error generating accounting overview: {str(e)}")
            return "Accounting system overview temporarily unavailable. The system has access to accounting data (journal entries and line items) for financial analysis. Please ask specific questions about your accounting and financial data."
    
    def _generate_fallback_response_with_data(self, message, data_context):
        """Generate fallback response when API is unavailable but we have data"""
        try:
            if not data_context or data_context.strip() == "":
                return "I'm sorry, I'm currently unable to access the AI service and no local data is available. Please try again later or check your API configuration."
            
            # Provide basic response with available data
            response = f"I have some information about your query, though my AI analysis service is temporarily unavailable:\n\n"
            response += data_context
            response += "\n\nFor more detailed analysis, please ensure the Claude API key is properly configured in System Parameters."
            
            return response
            
        except Exception as e:
            _logger.error(f"Error in fallback response: {str(e)}")
            return "I'm experiencing technical difficulties. Please check the system configuration and try again."
    
    def _test_model_access(self):
        """Test method to verify model access and permissions"""
        test_results = "=== MODEL ACCESS TEST ===\n\n"
        
        models_to_test = [
            'sale.order',
            'product.product', 
            'res.partner',
            'account.move',
            'mrp.production',
            'stock.quant'
        ]
        
        for model_name in models_to_test:
            try:
                records = self.env[model_name].search([], limit=1)
                test_results += f"✅ {model_name}: Accessible ({self.env[model_name].search_count([])} records)\n"
            except Exception as e:
                test_results += f"❌ {model_name}: Error - {str(e)}\n"
                
        test_results += f"\nCurrent User: {self.env.user.name} (ID: {self.env.user.id})\n"
        test_results += f"User Groups: {', '.join([g.name for g in self.env.user.groups_id])}\n"
        
        return test_results


class AIChatbotMessage(models.Model):
    _name = 'ai.chatbot.message'
    _description = 'AI Chatbot Message'
    _order = 'timestamp desc'

    chat_id = fields.Many2one('ai.chatbot', 'Chat Session', required=True, ondelete='cascade')
    message = fields.Text('Message', required=True)
    is_user = fields.Boolean('Is User Message', default=False)
    timestamp = fields.Datetime('Timestamp', default=fields.Datetime.now)
    tokens_used = fields.Integer('Tokens Used', default=0)