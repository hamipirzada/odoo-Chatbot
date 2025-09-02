# Odoo AI Analytics Chatbot

A powerful AI-driven business intelligence chatbot for Odoo 17 that provides intelligent data analysis and insights using Claude's advanced language model.

## 🚀 Features

### 🤖 AI-Powered Analysis
- **Claude AI Integration**: Uses Anthropic's Claude for advanced natural language processing
- **Intent-Based Responses**: Understands query context and provides relevant business insights
- **Real-time Data Access**: Connects directly to your Odoo database for live data analysis

### 📊 Text-Based Analysis
- **Comprehensive Reports**: Detailed text-based analysis and insights
- **Data-Driven Responses**: Analysis based on real Odoo data
- **Accounting Focus**: Specialized in financial and accounting data analysis
- **Intelligent Summaries**: Clear, actionable business insights

### 💼 Business Intelligence Coverage
- **Accounting Analysis**: Journal entries, financial transactions, balance analysis
- **Invoice Management**: Invoice tracking, payment analysis, receivables/payables
- **Financial Reporting**: Profit/loss insights, financial health indicators
- **Data Consistency**: Precise, factual responses based on actual accounting data
- **Restricted Scope**: Focused on accounting data for accuracy and reliability

### 🎯 Smart Features
- **Chat Management**: Persistent chat history with sidebar navigation
- **Responsive Design**: Mobile-friendly interface that adapts to screen size
- **Error Handling**: Robust error management with fallback responses
- **Timezone Support**: Accurate timestamps and date handling
- **Security**: Accounting-focused responses, restricted data access

## 📋 Requirements

- Odoo 17.0+
- Python 3.8+
- Required Python packages: `pytz`, `requests`
- Claude API key from Anthropic

## 🛠️ Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/hamipirzada/odoo-Chatbot.git
   cd odoo-Chatbot
   ```

2. **Copy to Odoo addons directory**:
   ```bash
   cp -r ai_analytics /path/to/your/odoo/addons/
   ```

3. **Install required Python packages**:
   ```bash
   pip install pytz requests
   ```

4. **Update Odoo apps list**:
   - Go to Apps menu in Odoo
   - Click "Update Apps List"
   - Search for "AI Analytics"

5. **Install the module**:
   - Click "Install" on AI Analytics module

6. **Configure Claude API**:
   - Get your API key from [Anthropic Console](https://console.anthropic.com/)
   - Set the API key using one of these methods:
     - Environment variable: `export CLAUDE_API_KEY="your_api_key_here"`
     - Odoo system parameter: Go to Settings > Technical > Parameters > System Parameters
       - Create new parameter: `ai_analytics.claude_api_key` with your API key value

## 🔧 Configuration

### Environment Variables
```bash
export CLAUDE_API_KEY="your_claude_api_key_here"
```

### Odoo Configuration
The module automatically creates necessary database tables and configurations upon installation.

## 📱 Usage

### Accessing the Chatbot
1. Go to **AI Analytics** menu in Odoo
2. Click on **AI Business Assistant**
3. Use the integrated chatbot interface

### Sample Queries
- `"Show me accounting data for February 2025"`
- `"Analyze journal entries for this month"`
- `"What are our current account balances?"`
- `"Give me invoice analysis for Q4"`
- `"How are our payments compared to last month?"`

### Chat Features
- **New Chat**: Start fresh conversations
- **Chat History**: Access previous conversations from sidebar
- **Delete Chats**: Remove unwanted chat sessions
- **Responsive Input**: Chat field adapts to sidebar toggle

## 🏗️ Architecture

### Backend Components
- **`models/ai_chatbot.py`**: Core chatbot logic and data processing
- **`models/realtime_dashboard.py`**: Dashboard data management
- **`controllers/chatbot_controller.py`**: HTTP endpoints for frontend
- **`data/ir_cron_data.xml`**: Background job configurations

### Frontend Components  
- **`static/src/js/chatbot_widget.js`**: OWL component for chatbot UI
- **`static/src/xml/chatbot_templates.xml`**: HTML templates
- **`static/src/css/chatbot.css`**: Styling and responsive design

### Key Features Implementation
- **Accounting Data Access**: Intelligent analysis of financial data
- **Intent Recognition**: Advanced query analysis for relevant data retrieval
- **Data Consistency**: Same query always returns same results
- **Timezone Handling**: Accurate timestamp processing

## 🎨 Customization

### Adding New Data Analysis
Extend the accounting data analysis methods in `models/ai_chatbot.py`:

```python
def _get_custom_accounting_analysis(self, message):
    # Your custom analysis logic here
    return "Custom accounting insights..."
```

### Modifying UI
Update templates in `static/src/xml/chatbot_templates.xml` and styles in `static/src/css/chatbot.css`.

### Extending Data Sources
Currently focused on accounting data (account_move, account_move_line). Extend carefully to maintain data accuracy.

## 🐛 Troubleshooting

### Common Issues
1. **No AI responses**: Check Claude API key configuration
2. **No data in responses**: Verify database has accounting records
3. **API errors**: Confirm Claude API key is properly configured
4. **Module not loading**: Check Odoo logs for installation errors

### Debug Mode
Enable debug logging in Odoo configuration:
```ini
log_level = debug
```

## 🔒 Security

- **Accounting-Only Responses**: Chatbot only answers accounting and financial questions
- **No External Data**: All analysis based on your Odoo database
- **API Security**: Claude API calls use secure HTTPS endpoints
- **Access Control**: Respects Odoo user permissions and security groups
- **Data Restriction**: Limited to accounting tables only for security

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the LGPL-3.0 License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Anthropic**: For providing the powerful Claude AI API
- **Odoo Community**: For the amazing ERP framework
- **OWL Framework**: For modern JavaScript components

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Contact: [Your contact information]

## 🚀 Roadmap

- [ ] Extended accounting modules support
- [ ] Advanced financial analytics
- [ ] Export capabilities (PDF, Excel)
- [ ] Multi-language support
- [ ] Mobile responsiveness improvements
- [ ] Enhanced data visualization

---

**Made with ❤️ for the Odoo community**