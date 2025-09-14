import plotly
import json
import base64
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import streamlit as st
import os

class ExportHandler:
    """Handle exports and shareable links for visualizations and analysis"""
    
    def __init__(self):
        self.base_url = "https://data-analysis-tool.streamlit.app"  # Replace with actual deployment URL
    
    def export_chart_html(self, fig) -> str:
        """Export Plotly chart as standalone HTML"""
        try:
            html_str = plotly.offline.plot(
                fig, 
                include_plotlyjs=True, 
                output_type='div',
                config={'displayModeBar': True, 'displaylogo': False}
            )
            
            # Wrap in a complete HTML document
            full_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Data Analysis Chart - {datetime.now().strftime('%Y-%m-%d %H:%M')}</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        margin: 0;
                        padding: 20px;
                        background-color: #f8f9fa;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                        color: #333;
                    }}
                    .chart-container {{
                        background: white;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        padding: 20px;
                        margin: 0 auto;
                        max-width: 1200px;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 30px;
                        color: #666;
                        font-size: 0.9em;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>📊 AI Data Analysis Tool</h1>
                    <p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
                </div>
                <div class="chart-container">
                    {html_str}
                </div>
                <div class="footer">
                    <p>Created with AI-powered data analysis • Powered by Plotly</p>
                </div>
            </body>
            </html>
            """
            
            return full_html
            
        except Exception as e:
            raise Exception(f"Failed to export chart as HTML: {str(e)}")
    
    def create_shareable_link(self, fig, session_id: str) -> str:
        """Create shareable link for visualization"""
        try:
            # Generate unique ID for this visualization
            viz_id = str(uuid.uuid4())
            
            # Convert figure to JSON
            fig_json = fig.to_json()
            
            # In a real implementation, you would save this to a database
            # For now, we'll create a mock shareable link
            link = f"{self.base_url}/shared/{viz_id}?session={session_id}"
            
            # Store visualization data in session state (temporary solution)
            if 'shared_visualizations' not in st.session_state:
                st.session_state.shared_visualizations = {}
            
            st.session_state.shared_visualizations[viz_id] = {
                'figure_json': fig_json,
                'created_at': datetime.now().isoformat(),
                'session_id': session_id
            }
            
            return link
            
        except Exception as e:
            raise Exception(f"Failed to create shareable link: {str(e)}")
    
    def export_analysis_report(self, df, analysis_results: Dict[str, Any], visualizations: list = None) -> str:
        """Export comprehensive analysis report as HTML"""
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Generate HTML report
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Data Analysis Report - {timestamp}</title>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                        line-height: 1.6;
                        margin: 0;
                        padding: 20px;
                        background-color: #f8f9fa;
                        color: #333;
                    }}
                    .container {{
                        max-width: 1000px;
                        margin: 0 auto;
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        border-bottom: 2px solid #e9ecef;
                        padding-bottom: 30px;
                        margin-bottom: 40px;
                    }}
                    .header h1 {{
                        color: #2c3e50;
                        margin-bottom: 10px;
                    }}
                    .section {{
                        margin-bottom: 40px;
                    }}
                    .section h2 {{
                        color: #34495e;
                        border-left: 4px solid #3498db;
                        padding-left: 15px;
                        margin-bottom: 20px;
                    }}
                    .insight-list {{
                        background: #f8f9fa;
                        padding: 20px;
                        border-radius: 8px;
                        border-left: 4px solid #28a745;
                    }}
                    .insight-list li {{
                        margin-bottom: 10px;
                    }}
                    .data-summary {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .stat-card {{
                        background: #e9ecef;
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                    }}
                    .stat-value {{
                        font-size: 2em;
                        font-weight: bold;
                        color: #3498db;
                    }}
                    .stat-label {{
                        color: #666;
                        margin-top: 5px;
                    }}
                    .footer {{
                        text-align: center;
                        margin-top: 50px;
                        padding-top: 30px;
                        border-top: 2px solid #e9ecef;
                        color: #666;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🤖 AI Data Analysis Report</h1>
                        <p>Generated on {timestamp}</p>
                    </div>
                    
                    <div class="section">
                        <h2>📊 Dataset Overview</h2>
                        <div class="data-summary">
                            <div class="stat-card">
                                <div class="stat-value">{df.shape[0]:,}</div>
                                <div class="stat-label">Rows</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">{df.shape[1]}</div>
                                <div class="stat-label">Columns</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">{df.isnull().sum().sum()}</div>
                                <div class="stat-label">Missing Values</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-value">{len(df.select_dtypes(include=['number']).columns)}</div>
                                <div class="stat-label">Numeric Columns</div>
                            </div>
                        </div>
                    </div>
            """
            
            # Add AI insights
            if analysis_results.get('insights'):
                html_content += f"""
                    <div class="section">
                        <h2>💡 Key Insights</h2>
                        <ul class="insight-list">
                """
                for insight in analysis_results['insights']:
                    html_content += f"<li>{insight}</li>"
                html_content += "</ul></div>"
            
            # Add patterns
            if analysis_results.get('patterns'):
                html_content += f"""
                    <div class="section">
                        <h2>🔍 Detected Patterns</h2>
                        <ul class="insight-list">
                """
                for pattern in analysis_results['patterns']:
                    html_content += f"<li>{pattern}</li>"
                html_content += "</ul></div>"
            
            # Add recommendations
            if analysis_results.get('recommendations'):
                html_content += f"""
                    <div class="section">
                        <h2>💭 Recommendations</h2>
                        <ul class="insight-list">
                """
                for rec in analysis_results['recommendations']:
                    html_content += f"<li>{rec}</li>"
                html_content += "</ul></div>"
            
            # Add anomalies
            if analysis_results.get('anomalies'):
                html_content += f"""
                    <div class="section">
                        <h2>⚠️ Detected Anomalies</h2>
                        <ul class="insight-list">
                """
                for anomaly in analysis_results['anomalies']:
                    html_content += f"<li>{anomaly}</li>"
                html_content += "</ul></div>"
            
            # Close HTML
            html_content += f"""
                    <div class="footer">
                        <p>Report generated by AI-powered Data Analysis Tool</p>
                        <p>Powered by Claude and GPT models • Interactive visualizations by Plotly</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            return html_content
            
        except Exception as e:
            raise Exception(f"Failed to export analysis report: {str(e)}")
    
    def export_data_csv(self, df) -> str:
        """Export DataFrame as CSV string"""
        try:
            return df.to_csv(index=False)
        except Exception as e:
            raise Exception(f"Failed to export data as CSV: {str(e)}")
    
    def export_data_json(self, df) -> str:
        """Export DataFrame as JSON string"""
        try:
            return df.to_json(orient='records', indent=2)
        except Exception as e:
            raise Exception(f"Failed to export data as JSON: {str(e)}")
    
    def create_dashboard_export(self, df, analysis_results: Dict[str, Any], figures: list) -> str:
        """Create comprehensive dashboard export with visualizations"""
        try:
            # Start with analysis report
            html_content = self.export_analysis_report(df, analysis_results)
            
            # Add visualizations section
            viz_section = """
                <div class="section">
                    <h2>📈 Generated Visualizations</h2>
            """
            
            for i, fig in enumerate(figures):
                chart_html = plotly.offline.plot(
                    fig, 
                    include_plotlyjs=True if i == 0 else False,  # Include JS only once
                    output_type='div'
                )
                viz_section += f"""
                    <div style="margin-bottom: 40px; padding: 20px; background: #f8f9fa; border-radius: 8px;">
                        <h3>Chart {i+1}</h3>
                        {chart_html}
                    </div>
                """
            
            viz_section += "</div>"
            
            # Insert visualizations before footer
            footer_pos = html_content.rfind('<div class="footer">')
            if footer_pos != -1:
                html_content = html_content[:footer_pos] + viz_section + html_content[footer_pos:]
            else:
                html_content += viz_section
            
            return html_content
            
        except Exception as e:
            raise Exception(f"Failed to create dashboard export: {str(e)}")
