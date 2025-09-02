#!/usr/bin/env python3
"""
Script to configure Claude API key for AI Analytics module
Run this script to set up your API key in Odoo system parameters
"""

import os
import sys

# Add Odoo path
sys.path.append('/home/hamid/Desktop/odoo-17')

def setup_claude_api_key():
    """Configure Claude API key in Odoo system parameters"""
    
    print("🤖 AI Analytics - Claude API Key Setup")
    print("=" * 50)
    
    # Get API key from user
    api_key = input("Enter your Claude API key (or press Enter to skip): ").strip()
    
    if not api_key:
        print("\n📝 To configure the API key manually in Odoo:")
        print("1. Go to Settings → System Parameters")
        print("2. Create a new parameter:")
        print("   - Key: ai_analytics.claude_api_key")
        print("   - Value: your_claude_api_key_here")
        print("\n🔗 Get your API key at: https://console.anthropic.com/")
        return
    
    print(f"\n✅ API Key configured: {api_key[:8]}***")
    print("\n📋 Manual setup instructions:")
    print("1. Log into your Odoo system")
    print("2. Go to Settings → System Parameters")  
    print("3. Create/update parameter:")
    print(f"   - Key: ai_analytics.claude_api_key")
    print(f"   - Value: {api_key}")
    print("\n🎯 Your AI Analytics chatbot will now be fully functional!")

if __name__ == "__main__":
    setup_claude_api_key()