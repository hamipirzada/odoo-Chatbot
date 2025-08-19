from odoo import models, fields, api
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


class RealtimeDashboard(models.Model):
    _name = 'realtime.dashboard'
    _description = 'Real-time Dashboard Data'
    _order = 'create_date desc'

    name = fields.Char('Dashboard Name', required=True)
    data = fields.Text('Dashboard Data', help='JSON data for dashboard widgets')
    last_refresh = fields.Datetime('Last Refresh', default=fields.Datetime.now)
    active = fields.Boolean('Active', default=True)
    dashboard_type = fields.Selection([
        ('sales', 'Sales Dashboard'),
        ('analytics', 'Analytics Dashboard'),
        ('ai', 'AI Insights Dashboard'),
        ('custom', 'Custom Dashboard'),
    ], string='Dashboard Type', default='analytics')
    
    @api.model
    def refresh_dashboard_data(self):
        """Method called by cron job to refresh dashboard data"""
        try:
            dashboards = self.search([('active', '=', True)])
            for dashboard in dashboards:
                dashboard._update_dashboard_data()
            _logger.info(f"Successfully refreshed {len(dashboards)} dashboards")
            return True
        except Exception as e:
            _logger.error(f"Error refreshing dashboard data: {str(e)}")
            return False
    
    @api.model
    def trigger_dashboard_refresh(self):
        """Legacy method name compatibility - calls refresh_dashboard_data"""
        return self.refresh_dashboard_data()
    
    def _update_dashboard_data(self):
        """Update dashboard data with latest information"""
        sample_data = {
            'widgets': [
                {
                    'id': 'widget_1',
                    'type': 'chart',
                    'title': 'Analytics Overview',
                    'data': {'value': 100, 'trend': 'up'},
                    'last_update': fields.Datetime.now().isoformat()
                }
            ],
            'last_update': fields.Datetime.now().isoformat(),
            'status': 'active'
        }
        
        self.write({
            'data': json.dumps(sample_data),
            'last_refresh': fields.Datetime.now()
        })
        
    @api.model
    def create_default_dashboard(self):
        """Create a default dashboard if none exists"""
        existing = self.search([('dashboard_type', '=', 'ai')], limit=1)
        if not existing:
            self.create({
                'name': 'AI Analytics Dashboard',
                'dashboard_type': 'ai',
                'data': json.dumps({
                    'widgets': [],
                    'status': 'initialized'
                })
            })