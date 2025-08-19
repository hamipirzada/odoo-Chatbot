# Odoo AI Analytics Chatbot

A powerful AI-driven business intelligence chatbot for Odoo 17 that provides intelligent data analysis, insights, and interactive visualizations using Groq's LLM.

## 🚀 Features

### 🤖 AI-Powered Analysis
- **Groq LLM Integration**: Uses `llama-3.3-70b-versatile` model for natural language processing
- **Intent-Based Responses**: Understands query context and provides relevant business insights
- **Real-time Data Access**: Connects directly to your Odoo database for live data analysis

### 📊 Dynamic Chart Generation
- **Query-Specific Charts**: Different visualizations based on query intent
- **Multiple Chart Types**: Line, Bar, Pie charts with Chart.js integration
- **Period-Specific Analysis**: Special handling for date/month-specific queries
- **Interactive Visualizations**: Hover effects, responsive design

### 💼 Business Intelligence Coverage
- **Sales Analysis**: Revenue trends, order patterns, customer insights
- **Customer Analytics**: Customer behavior, top buyers, relationship analysis  
- **Product Performance**: Inventory levels, best-sellers, product trends
- **Financial Insights**: Invoice analysis, profit/loss tracking, financial health
- **Universal Data Reader**: Automatically detects and analyzes all available Odoo modules

### 🎯 Smart Features
- **Chat Management**: Persistent chat history with sidebar navigation
- **Responsive Design**: Mobile-friendly interface that adapts to screen size
- **Error Handling**: Robust error management with fallback responses
- **Timezone Support**: Automatic timezone conversion for accurate timestamps
- **Security**: Business-only responses, no general purpose Q&A

## 📋 Requirements

- Odoo 17.0+
- Python 3.8+
- Required Python packages: `groq`, `pytz`, `requests`
- Groq API key
- Chart.js (included in static files)

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
   pip install groq pytz requests
   ```

4. **Update Odoo apps list**:
   - Go to Apps menu in Odoo
   - Click "Update Apps List"
   - Search for "AI Analytics"

5. **Install the module**:
   - Click "Install" on AI Analytics module

6. **Configure Groq API**:
   - Get your API key from [Groq Console](https://console.groq.com/)
   - Set the API key using one of these methods:
     - Environment variable: `export GROQ_API_KEY="your_api_key_here"`
     - Odoo system parameter: Go to Settings > Technical > Parameters > System Parameters
       - Create new parameter: `ai_analytics.groq_api_key` with your API key value

## 🔧 Configuration

### Environment Variables
```bash
export GROQ_API_KEY="your_groq_api_key_here"
```

### Odoo Configuration
The module automatically creates necessary database tables and configurations upon installation.

## 📱 Usage

### Accessing the Chatbot
1. Go to **AI Analytics** menu in Odoo
2. Click on **AI Analytics Dashboard**  
3. Use the integrated chatbot interface

### Sample Queries
- `"Show me sales data for February 2025"`
- `"What are our top customers this month?"`
- `"Analyze product performance trends"`
- `"Give me financial insights for Q4"`
- `"How are our sales compared to last month?"`

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
- **`static/src/js/chart.min.js`**: Chart.js library for visualizations

### Key Features Implementation
- **Universal Data Access**: Intelligent model detection across all Odoo modules
- **Chart Persistence**: Charts remain visible when switching between chats
- **Intent Recognition**: Advanced query analysis for appropriate chart generation
- **Timezone Handling**: Automatic conversion to user's local timezone

## 🎨 Customization

### Adding New Chart Types
Extend the `_generate_chart_data_by_intent()` method in `models/ai_chatbot.py`:

```python
def _get_custom_chart_data(self, message):
    # Your custom chart logic here
    return {
        'charts': [chart_config],
        'has_charts': True
    }
```

### Modifying UI
Update templates in `static/src/xml/chatbot_templates.xml` and styles in `static/src/css/chatbot.css`.

### Adding New Data Sources
Extend the `_detect_relevant_models()` method to include additional Odoo models.

## 🐛 Troubleshooting

### Common Issues
1. **Charts not rendering**: Check browser console for JavaScript errors
2. **No data in responses**: Verify database has relevant records
3. **API errors**: Confirm Groq API key is properly configured
4. **Module not loading**: Check Odoo logs for installation errors

### Debug Mode
Enable debug logging in Odoo configuration:
```ini
log_level = debug
```

## 🔒 Security

- **Business-Only Responses**: Chatbot only answers Odoo-related business questions
- **No External Data**: All analysis based on your Odoo database
- **API Security**: Groq API calls use secure HTTPS endpoints
- **Access Control**: Respects Odoo user permissions and security groups

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the LGPL-3.0 License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Groq**: For providing the powerful LLM API
- **Chart.js**: For beautiful chart visualizations
- **Odoo Community**: For the amazing ERP framework
- **OWL Framework**: For modern JavaScript components

## 📞 Support

For support and questions:
- Create an issue on GitHub
- Contact: [Your contact information]

## 🚀 Roadmap

- [ ] Multi-language support
- [ ] Advanced analytics dashboards
- [ ] Export capabilities (PDF, Excel)
- [ ] Voice input integration
- [ ] Mobile app companion
- [ ] Advanced AI training on business data

---

**Made with ❤️ for the Odoo community**