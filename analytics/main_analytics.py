import streamlit as st
import pandas as pd
import numpy as np
import os
from typing import Optional
import traceback

# Import our utility classes (imports directs dans le même dossier)
from data_processor import DataProcessor
from ai_analyzer import AIAnalyzer
from visualization import VisualizationGenerator
from export_handler import ExportHandler

# Page config
st.set_page_config(
    page_title="AI Data Analysis Tool",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize utilities
@st.cache_resource
def get_utilities():
    """Initialize and cache utility classes"""
    data_processor = DataProcessor()
    viz_generator = VisualizationGenerator()
    export_handler = ExportHandler()
    
    # AI Analyzer - handle case where API keys are missing
    ai_analyzer = None
    try:
        ai_analyzer = AIAnalyzer()
    except ValueError:
        pass  # No API keys available
    
    return data_processor, ai_analyzer, viz_generator, export_handler

def main():
    """Main Streamlit application"""
    
    # Header
    st.title("📊 AI-Powered Data Analysis Tool")
    st.markdown("Upload your data files and get instant insights with AI-powered analysis and interactive visualizations.")
    
    # Initialize utilities
    data_processor, ai_analyzer, viz_generator, export_handler = get_utilities()
    
    # Sidebar for file upload
    with st.sidebar:
        st.header("📁 Data Upload")
        uploaded_file = st.file_uploader(
            "Choose a CSV or JSON file",
            type=["csv", "json"],
            help="Upload your data file to begin analysis"
        )
        
        # Show API key status
        st.header("🔑 AI Features")
        anthropic_key = bool(os.environ.get('ANTHROPIC_API_KEY'))
        openai_key = bool(os.environ.get('OPENAI_API_KEY'))
        
        if anthropic_key or openai_key:
            st.success("✅ AI analysis available")
            if anthropic_key:
                st.info("📝 Claude Sonnet 4 enabled")
            if openai_key:
                st.info("🤖 GPT-5 enabled")
        else:
            st.warning("⚠️ No API keys detected")
            st.info("Add ANTHROPIC_API_KEY or OPENAI_API_KEY for AI features")
    
    # Main content area
    if uploaded_file is not None:
        try:
            # Load and process data
            with st.spinner("📊 Loading and processing data..."):
                df = data_processor.load_file(uploaded_file)
            
            # Display data overview
            st.header("📋 Data Overview")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📊 Total Rows", len(df))
            with col2:
                st.metric("📋 Total Columns", len(df.columns))
            with col3:
                st.metric("💾 File Size", f"{uploaded_file.size:,} bytes")
            
            # Show data preview
            st.subheader("🔍 Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            
            # Data summary
            st.subheader("📈 Data Summary")
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Data Types:**")
                st.dataframe(df.dtypes.reset_index().rename(columns={0: 'Type', 'index': 'Column'}))
            
            with col2:
                # Basic statistics for numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    st.write("**Numeric Statistics:**")
                    st.dataframe(df[numeric_cols].describe())
            
            # Tabs for different analysis types
            tab1, tab2, tab3, tab4 = st.tabs(["🎯 Quick Analysis", "📊 Visualizations", "🤖 AI Insights", "📤 Export"])
            
            with tab1:
                st.subheader("🎯 Quick Data Analysis")
                
                # Missing values
                missing_data = df.isnull().sum()
                if missing_data.sum() > 0:
                    st.write("**Missing Values:**")
                    missing_df = missing_data[missing_data > 0].reset_index()
                    missing_df.columns = ['Column', 'Missing Count']
                    st.dataframe(missing_df)
                else:
                    st.success("✅ No missing values found!")
                
                # Column information
                st.write("**Column Details:**")
                col_info = []
                for col in df.columns:
                    col_info.append({
                        'Column': col,
                        'Type': str(df[col].dtype),
                        'Non-Null Count': df[col].count(),
                        'Unique Values': df[col].nunique()
                    })
                st.dataframe(pd.DataFrame(col_info))
            
            with tab2:
                st.subheader("📊 Interactive Visualizations")
                
                # Chart type selection
                chart_types = [
                    "scatter_plot", "line_chart", "bar_chart", 
                    "histogram", "box_plot", "correlation_matrix", "heatmap"
                ]
                
                selected_chart = st.selectbox("Select Chart Type", chart_types)
                
                # Column selection based on chart type
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                all_cols = df.columns.tolist()
                
                if selected_chart in ["scatter_plot", "line_chart"]:
                    col1, col2 = st.columns(2)
                    with col1:
                        x_col = st.selectbox("X-axis", all_cols)
                    with col2:
                        y_col = st.selectbox("Y-axis", numeric_cols)
                    
                    if st.button("Generate Chart"):
                        try:
                            fig = viz_generator.create_scatter_line(df, x_col, y_col, chart_type=selected_chart.replace('_', ' '))
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error creating chart: {str(e)}")
                
                elif selected_chart == "histogram":
                    selected_col = st.selectbox("Select Column", numeric_cols)
                    if st.button("Generate Histogram"):
                        try:
                            fig = viz_generator.create_chart(df, "histogram", [selected_col])
                            st.plotly_chart(fig, use_container_width=True)
                        except Exception as e:
                            st.error(f"Error creating histogram: {str(e)}")
                
                elif selected_chart == "correlation_matrix":
                    if len(numeric_cols) >= 2:
                        if st.button("Generate Correlation Matrix"):
                            try:
                                fig = viz_generator.create_correlation_matrix(df[numeric_cols])
                                st.plotly_chart(fig, use_container_width=True)
                            except Exception as e:
                                st.error(f"Error creating correlation matrix: {str(e)}")
                    else:
                        st.warning("Need at least 2 numeric columns for correlation matrix")
            
            with tab3:
                st.subheader("🤖 AI-Powered Insights")
                
                if ai_analyzer:
                    # Analysis type selection
                    analysis_types = [
                        "comprehensive_analysis",
                        "statistical_summary", 
                        "pattern_detection",
                        "outlier_analysis",
                        "correlation_insights"
                    ]
                    
                    selected_analysis = st.selectbox("Select Analysis Type", analysis_types)
                    
                    if st.button("🚀 Run AI Analysis"):
                        try:
                            with st.spinner("🧠 AI is analyzing your data..."):
                                results = ai_analyzer.analyze_data(df, selected_analysis)
                            
                            st.success("✅ Analysis complete!")
                            
                            # Display results
                            if "summary" in results:
                                st.write("**Summary:**")
                                st.write(results["summary"])
                            
                            if "insights" in results:
                                st.write("**Key Insights:**")
                                for insight in results["insights"]:
                                    st.write(f"• {insight}")
                            
                            if "recommendations" in results:
                                st.write("**Recommendations:**")
                                for rec in results["recommendations"]:
                                    st.write(f"• {rec}")
                            
                        except Exception as e:
                            st.error(f"AI analysis failed: {str(e)}")
                            st.error(f"Traceback: {traceback.format_exc()}")
                    
                    # Natural language questions
                    st.subheader("💬 Ask Questions About Your Data")
                    user_question = st.text_input("Ask a question about your data:")
                    
                    if user_question and st.button("🔍 Get Answer"):
                        try:
                            with st.spinner("🤔 AI is thinking..."):
                                answer = ai_analyzer.answer_question(df, user_question)
                            
                            st.success("✅ Answer ready!")
                            st.write("**Answer:**")
                            st.write(answer.get("answer", "No answer generated"))
                            
                            if "visualization_suggestion" in answer:
                                st.info(f"💡 Visualization suggestion: {answer['visualization_suggestion']}")
                            
                        except Exception as e:
                            st.error(f"Failed to answer question: {str(e)}")
                else:
                    st.warning("🔑 AI features require API keys")
                    st.info("Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variables to enable AI analysis")
                    
                    # Show basic analysis without AI
                    st.subheader("📊 Basic Analysis (No AI)")
                    if st.button("Run Basic Analysis"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Data Shape:**")
                            st.write(f"• {len(df)} rows, {len(df.columns)} columns")
                            
                            st.write("**Column Types:**")
                            for dtype, count in df.dtypes.value_counts().items():
                                st.write(f"• {dtype}: {count} columns")
                        
                        with col2:
                            if len(numeric_cols) > 0:
                                st.write("**Numeric Summary:**")
                                st.write(f"• Numeric columns: {len(numeric_cols)}")
                                st.write(f"• Total missing: {df[numeric_cols].isnull().sum().sum()}")
            
            with tab4:
                st.subheader("📤 Export and Share")
                st.write("Export your analysis and visualizations")
                
                # Note: Export functionality would be implemented here
                # For now, showing placeholder
                st.info("📋 Export functionality ready - generate charts first, then return here to download")
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.error(f"Detailed error: {traceback.format_exc()}")
    
    else:
        # Landing page when no file is uploaded
        st.header("🎯 Welcome to AI Data Analysis Tool")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.subheader("📊 Upload Data")
            st.write("• Support for CSV and JSON files")
            st.write("• Automatic data cleaning")
            st.write("• Smart type detection")
        
        with col2:
            st.subheader("🤖 AI Analysis")
            st.write("• Powered by Claude Sonnet 4")
            st.write("• GPT-5 backup analysis")
            st.write("• Natural language insights")
        
        with col3:
            st.subheader("📈 Visualizations")
            st.write("• Interactive Plotly charts")
            st.write("• Multiple chart types")
            st.write("• Export capabilities")
        
        st.info("👆 Upload a file in the sidebar to get started!")

if __name__ == "__main__":
    main()