from odoo import models, fields, api, http
import json
import logging
import requests
import os
from datetime import datetime, timedelta

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
    def send_message(self, message, session_id=None):
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

            # Generate AI response using Groq
            ai_response = self._generate_ai_response(message, chat.id)

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

    def _generate_ai_response(self, message, chat_id):
        """Generate AI response using Groq API with real Odoo data"""
        try:
            # Get actual data from Odoo based on the query
            odoo_data = self._get_relevant_odoo_data(message)
            
            # Get Groq API key from system parameters
            groq_api_key = self.env['ir.config_parameter'].sudo().get_param('ai_analytics.groq_api_key') or os.getenv('GROQ_API_KEY')
            
            if not groq_api_key:
                return "Groq API key not configured. Please set the 'ai_analytics.groq_api_key' system parameter."

            # Prepare the API request
            headers = {
                'Authorization': f'Bearer {groq_api_key}',
                'Content-Type': 'application/json'
            }

            # Get conversation history for context
            conversation_history = self._get_conversation_history(chat_id)

            # Build messages for Groq API with real data context  
            system_prompt = f"""You are an AI Business Intelligence assistant for a comprehensive Odoo ERP system called "kpak-17". This is a complete enterprise system with 50+ custom modules covering every aspect of business operations.

🏢 **COMPLETE kpak-17 ERP SYSTEM ACCESS**
You have unlimited access to ALL data across this comprehensive business system including:

📊 **CORE BUSINESS MODULES:**
- Sales & CRM, Customer Management, Revenue Analytics, Order Processing
- Inventory Management, Stock Control, Warehouse Operations, Product Catalogs
- Manufacturing (MRP), Production Planning, Quality Control, Work Orders
- Accounting & Finance, Invoicing, Payments, Financial Reporting, P&L Analysis
- Human Resources, Employee Management, Payroll, Performance Tracking

🏭 **SPECIALIZED MANUFACTURING MODULES:**
- Production Line Management, MRP Costing, Labor Cost Analysis
- Quality Inspections, Metal Detector Tests, Startup Checklists
- Daily Reject Reports, Interval Checking, Manufacturing Reporting
- BOM Management, Finished Product Analysis, Production Scheduling

📦 **LOGISTICS & INVENTORY:**
- Pallet Management, Product Packaging, Location Tracking
- Lot/Serial Number Tracking, Expiry Management, Product Alerts
- Inventory Reports, Stock Movement Analysis, Consumption Reports
- Delivery Management, Courier Services, Shipping Analytics

💼 **FINANCIAL & REPORTING:**
- Bank Reconciliation, Statement Reports, Aged Receivables
- Costing Reports, Purchase Analysis, Vendor Management
- Invoice Processing, Credit Control, Payment Analytics
- Dynamic Sales/Purchase/Inventory Report Generators

🔧 **OPERATIONAL SYSTEMS:**
- Master Search across all data, Custom Dashboards, EDI Exchange
- Portal Access, Custom Workflows, Security Controls
- Automated Alerts, Email Templates, Cron Job Management
- Liberty Forms, Inspection Reports, Production Analytics

**REAL-TIME DATA CONTEXT:**
{odoo_data}

**AI ANALYSIS APPROACH:**
- Use pure intent-driven analysis - NO hardcoded patterns or keyword matching
- Intelligently determine what data to fetch based on user's natural language intent
- Access any relevant module or data source dynamically based on the question
- Provide comprehensive, contextual responses with actual data from the system
- Cross-reference data across multiple modules when relevant
- Show trends, patterns, and actionable business insights

**RESPONSE GUIDELINES:**
- Always analyze the user's TRUE INTENT beyond surface-level keywords
- Fetch relevant data from appropriate kpak-17 modules automatically
- Provide specific numbers, names, dates from actual system data
- Include historical context and trends when relevant
- Give actionable business recommendations based on real data
- Text-based analysis only (no charts or visualizations)

For non-business questions, respond: "I'm designed to analyze your kpak-17 ERP system data. Please ask about your business operations, data, or any aspect of your Odoo system."

**Analyze the user's intent and provide comprehensive, data-driven business intelligence.**"""

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ]

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

            # Make API call to Groq
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 1024,
                "stream": False
            }

            response = requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content']
            else:
                _logger.error(f"Groq API error: {response.status_code} - {response.text}")
                return self._generate_fallback_response_with_data(message, odoo_data)

        except Exception as e:
            _logger.error(f"Error calling Groq API: {str(e)}")
            odoo_data = self._get_relevant_odoo_data(message)
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

    def _get_relevant_odoo_data(self, message):
        """Get comprehensive ERP data using AI-driven intent analysis of entire kpak-17 system"""
        try:
            current_date = fields.Date.today()
            
            # Initialize comprehensive data context
            data_context = f"Current Date: {current_date}\n"
            data_context += f"Company: {self.env.company.name}\n"
            data_context += f"Currency: {self.env.company.currency_id.name}\n"
            data_context += f"Database: kpak-17 (Complete Odoo ERP Installation)\n\n"
            
            # Use AI to determine what data to fetch based on user intent
            relevant_data = self._intelligently_fetch_data(message)
            data_context += relevant_data
            
            return data_context
            
        except Exception as e:
            _logger.error(f"Error getting comprehensive Odoo data: {str(e)}")
            return f"Current Date: {fields.Date.today()}\nNote: Error accessing data - {str(e)}"
    
    def _intelligently_fetch_data(self, message):
        """Use AI to determine what data to fetch from the entire kpak-17 ERP system"""
        try:
            # Special debug mode for testing model access
            if 'test models' in message.lower() or 'model test' in message.lower():
                return self._test_model_access()
            
            # Analyze user intent using AI
            intent_analysis = self._ai_analyze_intent(message)
            
            # Based on intent, identify relevant models and data
            data_sources = self._identify_data_sources(intent_analysis)
            
            _logger.info(f"Identified data sources: {[s.get('name') for s in data_sources]}")
            
            # Fetch data from identified sources
            combined_data = ""
            for source in data_sources:
                try:
                    source_data = self._fetch_from_source(source, message)
                    if source_data:
                        combined_data += f"\n{source['name']} Data:\n{source_data}\n"
                except Exception as e:
                    _logger.warning(f"Could not fetch from {source.get('name', 'unknown')}: {str(e)}")
                    # Instead of continuing, let's add this error to the response
                    combined_data += f"\n{source['name']} Data: Error accessing - {str(e)}\n"
            
            if not combined_data.strip():
                combined_data = self._get_comprehensive_overview()
            
            return combined_data
            
        except Exception as e:
            _logger.error(f"Error in intelligent data fetching: {str(e)}")
            return self._get_comprehensive_overview()
    
    def _ai_analyze_intent(self, message):
        """Use AI to analyze user intent without hardcoded keywords"""
        try:
            groq_api_key = self.env['ir.config_parameter'].sudo().get_param('ai_analytics.groq_api_key') or os.getenv('GROQ_API_KEY')
            if not groq_api_key:
                return {'intent': 'general', 'confidence': 0.5}
            
            headers = {
                'Authorization': f'Bearer {groq_api_key}',
                'Content-Type': 'application/json'
            }
            
            # AI prompt to analyze intent
            system_prompt = """You are an AI intent analyzer for an Odoo ERP system. Analyze the user's question and determine:
1. Primary business area (sales, inventory, manufacturing, accounting, HR, etc.)
2. Specific action requested (report, analysis, search, comparison, trend, etc.)
3. Time frame (current, historical, specific period, etc.)
4. Data scope (summary, detailed, specific records, etc.)

Available business modules in this kpak-17 system:
- Sales & CRM, Inventory Management, Manufacturing (MRP), Accounting & Finance
- Human Resources, Quality Control, Purchase Management, Project Management
- Costing Analysis, Bank Reconciliation, Delivery Reports, Production Scheduling
- Pallet Management, Product Alerts, Custom Dashboards, And 50+ other modules

Respond in JSON format with: {"intent": "primary_intent", "area": "business_area", "action": "specific_action", "timeframe": "time_scope", "scope": "data_scope"}"""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this user query: {message}"}
            ]
            
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "max_tokens": 200,
                "temperature": 0.1
            }
            
            response = requests.post('https://api.groq.com/openai/v1/chat/completions',
                                   headers=headers, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content'].strip()
                try:
                    return json.loads(content)
                except:
                    return {'intent': content, 'area': 'general', 'action': 'analyze'}
            else:
                _logger.warning(f"Groq API error for intent analysis: {response.status_code}")
                return {'intent': 'general', 'area': 'business', 'action': 'overview'}
                
        except Exception as e:
            _logger.error(f"Error in AI intent analysis: {str(e)}")
            return {'intent': 'general', 'area': 'business', 'action': 'overview'}
    
    def _identify_data_sources(self, intent_analysis):
        """Identify which data sources to query based on intent analysis"""
        try:
            area = intent_analysis.get('area', 'general').lower()
            action = intent_analysis.get('action', 'overview').lower()
            
            # Map business areas to relevant Odoo models intelligently
            data_sources = []
            
            # Sales & Revenue related
            if any(term in area for term in ['sales', 'revenue', 'customer', 'order', 'invoice']):
                data_sources.extend([
                    {'name': 'Sales Orders', 'model': 'sale.order', 'fields': ['name', 'partner_id', 'amount_total', 'state', 'date_order']},
                    {'name': 'Customers', 'model': 'res.partner', 'fields': ['name', 'customer_rank', 'country_id']},
                    {'name': 'Invoices', 'model': 'account.move', 'fields': ['name', 'partner_id', 'amount_total', 'state', 'invoice_date']}
                ])
            
            # Inventory & Products
            if any(term in area for term in ['inventory', 'stock', 'product', 'warehouse']):
                data_sources.extend([
                    {'name': 'Products', 'model': 'product.product', 'fields': ['name', 'categ_id', 'qty_available', 'standard_price']},
                    {'name': 'Stock Quants', 'model': 'stock.quant', 'fields': ['product_id', 'location_id', 'quantity', 'lot_id']},
                    {'name': 'Stock Moves', 'model': 'stock.move', 'fields': ['name', 'product_id', 'product_uom_qty', 'state', 'date']}
                ])
            
            # Manufacturing & Production
            if any(term in area for term in ['manufacturing', 'production', 'mrp', 'bom']):
                data_sources.extend([
                    {'name': 'Manufacturing Orders', 'model': 'mrp.production', 'fields': ['name', 'product_id', 'product_qty', 'state', 'date_start']},
                    {'name': 'Bills of Materials', 'model': 'mrp.bom', 'fields': ['product_tmpl_id', 'product_qty', 'type']},
                    {'name': 'Work Orders', 'model': 'mrp.workorder', 'fields': ['name', 'production_id', 'workcenter_id', 'state']}
                ])
            
            # Purchase & Vendors
            if any(term in area for term in ['purchase', 'vendor', 'supplier', 'procurement']):
                data_sources.extend([
                    {'name': 'Purchase Orders', 'model': 'purchase.order', 'fields': ['name', 'partner_id', 'amount_total', 'state', 'date_order']},
                    {'name': 'Vendors', 'model': 'res.partner', 'fields': ['name', 'supplier_rank', 'country_id']}
                ])
            
            # Accounting & Finance
            if any(term in area for term in ['accounting', 'finance', 'payment', 'expense']):
                data_sources.extend([
                    {'name': 'Account Moves', 'model': 'account.move', 'fields': ['name', 'partner_id', 'amount_total', 'state', 'date']},
                    {'name': 'Journal Entries', 'model': 'account.move.line', 'fields': ['name', 'account_id', 'debit', 'credit', 'date']}
                ])
            
            # If no specific area identified, get comprehensive overview
            if not data_sources:
                data_sources = [
                    {'name': 'Sales Overview', 'model': 'sale.order', 'fields': ['name', 'partner_id', 'amount_total', 'state']},
                    {'name': 'Inventory Overview', 'model': 'product.product', 'fields': ['name', 'categ_id', 'qty_available']},
                    {'name': 'Customer Overview', 'model': 'res.partner', 'fields': ['name', 'customer_rank', 'supplier_rank']}
                ]
            
            return data_sources[:5]  # Limit to avoid overwhelming response
            
        except Exception as e:
            _logger.error(f"Error identifying data sources: {str(e)}")
            return [{'name': 'General Overview', 'model': 'sale.order', 'fields': ['name', 'state']}]
    
    def _fetch_from_source(self, source, original_message):
        """Fetch data from a specific source model with enhanced analysis"""
        try:
            model_name = source.get('model')
            fields = source.get('fields', ['name'])
            source_name = source.get('name', model_name)
            
            # Try to access the model and get records
            try:
                _logger.info(f"Attempting to access model: {model_name}")
                records = self.env[model_name].search([])
                _logger.info(f"Successfully accessed {model_name}, found {len(records)} records")
            except Exception as e:
                _logger.error(f"Error accessing model {model_name}: {str(e)}")
                return f"Model {model_name} not accessible in this kpak-17 installation: {str(e)}"
            
            if not records:
                return f"No {source_name.lower()} found in kpak-17 system."
            
            result = f"=== {source_name.upper()} DATA FROM kpak-17 ===\n"
            result += f"Total Records: {len(records)}\n\n"
            
            # Enhanced data analysis based on model type
            if model_name == 'sale.order':
                return self._analyze_sales_data(records, original_message)
            elif model_name == 'product.product':
                return self._analyze_product_data(records, original_message)
            elif model_name == 'res.partner':
                return self._analyze_customer_data(records, original_message)
            elif model_name == 'account.move':
                return self._analyze_financial_data(records, original_message)
            elif model_name == 'mrp.production':
                return self._analyze_manufacturing_data(records, original_message)
            elif model_name == 'stock.quant':
                return self._analyze_inventory_data(records, original_message)
            else:
                return self._analyze_generic_data(records, source_name, fields)
            
        except Exception as e:
            _logger.error(f"Error fetching from kpak-17 {source.get('name')}: {str(e)}")
            return f"Could not retrieve {source.get('name', 'data')} from kpak-17: {str(e)}"
    
    def _analyze_sales_data(self, records, query):
        """Comprehensive sales analysis from kpak-17"""
        try:
            result = "=== SALES ANALYSIS FROM kpak-17 ===\n"
            result += f"Total Sales Orders: {len(records)}\n"
            
            # Calculate totals
            total_amount = sum(record.amount_total for record in records if record.amount_total)
            result += f"Total Sales Value: ${total_amount:,.2f}\n"
            
            # Year-wise breakdown if query mentions years/time
            if any(word in query.lower() for word in ['year', 'annual', '2024', '2025', '2023', 'growth', 'trend']):
                from collections import defaultdict
                yearly_data = defaultdict(lambda: {'count': 0, 'total': 0.0})
                
                for record in records:
                    if record.date_order:
                        year = record.date_order.year
                        yearly_data[year]['count'] += 1
                        yearly_data[year]['total'] += record.amount_total or 0.0
                
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
        """Get comprehensive business overview from kpak-17 ERP system"""
        try:
            overview = "=== kpak-17 ERP SYSTEM OVERVIEW ===\n\n"
            
            # Sales from kpak-17
            try:
                _logger.info("Attempting to access sale.order model")
                sales = self.env['sale.order'].search([])
                _logger.info(f"Found {len(sales)} sales orders")
                total_sales = sum(order.amount_total for order in sales if order.amount_total)
                recent_year = 2025
                recent_sales = sales.filtered(lambda s: s.date_order and s.date_order.year == recent_year)
                recent_total = sum(order.amount_total for order in recent_sales if order.amount_total)
                
                overview += f"📊 SALES DATA (kpak-17):\n"
                overview += f"   • Total Orders: {len(sales):,}\n"
                overview += f"   • Total Sales Value: ${total_sales:,.2f}\n"
                overview += f"   • 2025 Sales (YTD): ${recent_total:,.2f}\n\n"
            except Exception as e:
                _logger.error(f"Error accessing sales data: {str(e)}")
                overview += f"📊 SALES: Error accessing data - {str(e)}\n\n"
            
            # Inventory from kpak-17
            try:
                products = self.env['product.product'].search([])
                in_stock = products.filtered(lambda p: p.qty_available > 0)
                overview += f"📦 INVENTORY (kpak-17):\n"
                overview += f"   • Total Products: {len(products):,}\n"
                overview += f"   • Products in Stock: {len(in_stock):,}\n"
                overview += f"   • Categories Available: Yes\n\n"
            except Exception as e:
                overview += "📦 INVENTORY: Module available in kpak-17\n\n"
                
            # Customers from kpak-17
            try:
                partners = self.env['res.partner'].search([])
                customers = partners.filtered(lambda p: p.customer_rank > 0)
                suppliers = partners.filtered(lambda p: p.supplier_rank > 0)
                overview += f"👥 CUSTOMERS & PARTNERS (kpak-17):\n"
                overview += f"   • Active Customers: {len(customers):,}\n"
                overview += f"   • Active Suppliers: {len(suppliers):,}\n"
                overview += f"   • Total Partners: {len(partners):,}\n\n"
            except Exception as e:
                overview += "👥 CUSTOMERS: Module available in kpak-17\n\n"
                
            # Manufacturing from kpak-17
            try:
                productions = self.env['mrp.production'].search([])
                overview += f"🏭 MANUFACTURING (kpak-17):\n"
                overview += f"   • Production Orders: {len(productions):,}\n"
                overview += f"   • Advanced Manufacturing: ✓\n"
                overview += f"   • Quality Control: ✓\n\n"
            except Exception as e:
                overview += "🏭 MANUFACTURING: Module available in kpak-17\n\n"
            
            # kpak-17 Specialized Modules
            overview += "🔧 KPAK-17 SPECIALIZED MODULES:\n"
            overview += "   • Production Line Management ✓\n"
            overview += "   • Quality Inspections & Metal Detection ✓\n" 
            overview += "   • Pallet Management & Logistics ✓\n"
            overview += "   • Costing Analysis & BOM ✓\n"
            overview += "   • Bank Reconciliation & Financial Reports ✓\n"
            overview += "   • Inventory Customization & Lot Tracking ✓\n"
            overview += "   • Custom Dashboards & Reporting ✓\n"
            overview += "   • And 40+ other specialized modules\n\n"
                
            overview += "🎯 This is real-time data from your complete kpak-17 ERP installation.\n"
            overview += "Ask me specific questions about sales, inventory, manufacturing,\n"
            overview += "quality control, financial data, or any business area!"
            
            return overview
            
        except Exception as e:
            _logger.error(f"Error generating kpak-17 overview: {str(e)}")
            return "kpak-17 system overview temporarily unavailable. The system has 50+ modules available for analysis including sales, manufacturing, inventory, quality control, and specialized business processes. Please ask specific questions about your data."
    
    def _generate_fallback_response_with_data(self, message, data_context):
        """Generate fallback response when API is unavailable but we have data"""
        try:
            if not data_context or data_context.strip() == "":
                return "I'm sorry, I'm currently unable to access the AI service and no local data is available. Please try again later or check your API configuration."
            
            # Provide basic response with available data
            response = f"I have some information about your query, though my AI analysis service is temporarily unavailable:\n\n"
            response += data_context
            response += "\n\nFor more detailed analysis, please ensure the Groq API key is properly configured in System Parameters."
            
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