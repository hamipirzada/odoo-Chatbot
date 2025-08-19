{
    'name': 'AI Analytics',
    'version': '17.0.1.0.0',
    'category': 'Analytics',
    'summary': 'AI-powered analytics and dashboard features',
    'license': 'LGPL-3',
    'description': """
        AI Analytics Module
        ===================
        
        This module provides:
        * AI-powered business intelligence
        * Chatbot integration with text-based analysis
        * Real-time data insights
        * Comprehensive business analytics
    """,
    'author': 'AI Analytics Team',
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/realtime_dashboard_views.xml',
        'views/ai_chatbot_views.xml',
        'data/ir_cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_analytics/static/src/css/chatbot.css',
            'ai_analytics/static/src/js/chatbot_widget.js',
            'ai_analytics/static/src/xml/chatbot_templates.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
}