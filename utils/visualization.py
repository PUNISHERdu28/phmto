import plotly.express as px
import plotly.graph_objects as go
import plotly.figure_factory as ff
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List
import streamlit as st

class VisualizationGenerator:
    """Generate interactive visualizations using Plotly"""
    
    def __init__(self):
        self.color_palette = px.colors.qualitative.Set3
    
    def create_chart(self, df: pd.DataFrame, chart_type: str, columns: List[str]) -> go.Figure:
        """Create chart based on type and columns"""
        chart_type = chart_type.lower().replace(' ', '_')
        
        if chart_type in ['scatter_plot', 'scatter']:
            return self.create_scatter_plot(df, columns)
        elif chart_type in ['line_chart', 'line']:
            return self.create_line_chart(df, columns)
        elif chart_type in ['bar_chart', 'bar']:
            return self.create_bar_chart_from_columns(df, columns)
        elif chart_type == 'histogram':
            return self.create_histogram(df, columns[0] if columns else df.columns[0])
        elif chart_type in ['box_plot', 'box']:
            return self.create_box_plot(df, columns)
        elif chart_type in ['correlation_matrix', 'correlation']:
            return self.create_correlation_matrix(df)
        elif chart_type == 'heatmap':
            return self.create_heatmap(df, columns)
        else:
            # Default to scatter plot
            return self.create_scatter_plot(df, columns)
    
    def create_scatter_line(self, df: pd.DataFrame, x_col: str, y_col: str, 
                           color_col: Optional[str] = None, chart_type: str = "scatter") -> go.Figure:
        """Create scatter plot or line chart"""
        try:
            if chart_type == "scatter plot":
                fig = px.scatter(
                    df, 
                    x=x_col, 
                    y=y_col, 
                    color=color_col,
                    title=f"{y_col} vs {x_col}",
                    hover_data=df.columns.tolist()[:5]  # Show first 5 columns on hover
                )
            else:  # line chart
                fig = px.line(
                    df, 
                    x=x_col, 
                    y=y_col, 
                    color=color_col,
                    title=f"{y_col} over {x_col}",
                    markers=True
                )
            
            fig.update_layout(
                height=500,
                showlegend=color_col is not None,
                hovermode='closest'
            )
            
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating {chart_type}: {str(e)}")
    
    def create_scatter_plot(self, df: pd.DataFrame, columns: List[str]) -> go.Figure:
        """Create scatter plot from column list"""
        if len(columns) < 2:
            # Auto-select numeric columns
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) >= 2:
                columns = numeric_cols[:2]
            else:
                raise Exception("Need at least 2 numeric columns for scatter plot")
        
        x_col, y_col = columns[0], columns[1]
        color_col = columns[2] if len(columns) > 2 else None
        
        return self.create_scatter_line(df, x_col, y_col, color_col, "scatter plot")
    
    def create_line_chart(self, df: pd.DataFrame, columns: List[str]) -> go.Figure:
        """Create line chart from column list"""
        if len(columns) < 2:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) >= 2:
                columns = numeric_cols[:2]
            else:
                raise Exception("Need at least 2 columns for line chart")
        
        x_col, y_col = columns[0], columns[1]
        color_col = columns[2] if len(columns) > 2 else None
        
        return self.create_scatter_line(df, x_col, y_col, color_col, "line chart")
    
    def create_bar_chart(self, df: pd.DataFrame, x_col: str, y_col: str) -> go.Figure:
        """Create bar chart"""
        try:
            # If x_col is categorical, group by it
            if df[x_col].dtype == 'object' or df[x_col].dtype.name == 'category':
                # Group by category and aggregate
                if df[y_col].dtype in ['int64', 'float64']:
                    grouped_df = df.groupby(x_col)[y_col].mean().reset_index()
                else:
                    grouped_df = df.groupby(x_col).size().reset_index(name='count')
                    y_col = 'count'
            else:
                grouped_df = df
            
            fig = px.bar(
                grouped_df,
                x=x_col,
                y=y_col,
                title=f"{y_col} by {x_col}"
            )
            
            fig.update_layout(
                height=500,
                xaxis_tickangle=-45 if len(grouped_df) > 10 else 0
            )
            
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating bar chart: {str(e)}")
    
    def create_bar_chart_from_columns(self, df: pd.DataFrame, columns: List[str]) -> go.Figure:
        """Create bar chart from column list"""
        if len(columns) < 2:
            # Auto-select columns
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            
            if categorical_cols and numeric_cols:
                columns = [categorical_cols[0], numeric_cols[0]]
            else:
                columns = df.columns.tolist()[:2]
        
        return self.create_bar_chart(df, columns[0], columns[1])
    
    def create_histogram(self, df: pd.DataFrame, column: str, bins: int = 30) -> go.Figure:
        """Create histogram"""
        try:
            fig = px.histogram(
                df,
                x=column,
                nbins=bins,
                title=f"Distribution of {column}",
                marginal="box"  # Add box plot on top
            )
            
            fig.update_layout(
                height=500,
                showlegend=False
            )
            
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating histogram: {str(e)}")
    
    def create_box_plot(self, df: pd.DataFrame, columns: List[str]) -> go.Figure:
        """Create box plot"""
        try:
            if len(columns) == 1:
                # Single variable box plot
                fig = px.box(df, y=columns[0], title=f"Box Plot of {columns[0]}")
            else:
                # Box plot by category
                fig = px.box(
                    df, 
                    x=columns[0], 
                    y=columns[1], 
                    title=f"{columns[1]} by {columns[0]}"
                )
            
            fig.update_layout(height=500)
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating box plot: {str(e)}")
    
    def create_correlation_matrix(self, df: pd.DataFrame) -> go.Figure:
        """Create correlation matrix heatmap"""
        try:
            # Select only numeric columns
            numeric_df = df.select_dtypes(include=[np.number])
            
            if numeric_df.empty:
                raise Exception("No numeric columns found for correlation matrix")
            
            corr_matrix = numeric_df.corr()
            
            # Create heatmap
            fig = px.imshow(
                corr_matrix,
                text_auto=True,
                aspect="auto",
                title="Correlation Matrix",
                color_continuous_scale='RdBu_r',
                zmin=-1, zmax=1
            )
            
            fig.update_layout(
                height=600,
                width=600
            )
            
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating correlation matrix: {str(e)}")
    
    def create_heatmap(self, df: pd.DataFrame, columns: List[str]) -> go.Figure:
        """Create general heatmap"""
        try:
            if not columns:
                # Use all numeric columns
                numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                if len(numeric_cols) < 2:
                    raise Exception("Need at least 2 numeric columns for heatmap")
                data = df[numeric_cols].corr()
            else:
                data = df[columns]
            
            fig = px.imshow(
                data,
                text_auto=True,
                aspect="auto",
                title="Data Heatmap"
            )
            
            fig.update_layout(height=500)
            return fig
            
        except Exception as e:
            raise Exception(f"Error creating heatmap: {str(e)}")
    
    def create_chart_from_suggestion(self, df: pd.DataFrame, suggestion: Dict[str, Any]) -> go.Figure:
        """Create chart from AI suggestion"""
        try:
            chart_type = suggestion.get('type', 'scatter').lower()
            x_col = suggestion.get('x_column')
            y_col = suggestion.get('y_column')
            
            if chart_type in ['scatter', 'scatter_plot']:
                if x_col and y_col and x_col in df.columns and y_col in df.columns:
                    return self.create_scatter_line(df, x_col, y_col, chart_type="scatter plot")
                else:
                    # Auto-select columns
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if len(numeric_cols) >= 2:
                        return self.create_scatter_line(df, numeric_cols[0], numeric_cols[1], chart_type="scatter plot")
            
            elif chart_type in ['bar', 'bar_chart']:
                if x_col and y_col and x_col in df.columns and y_col in df.columns:
                    return self.create_bar_chart(df, x_col, y_col)
                else:
                    # Auto-select columns
                    categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if categorical_cols and numeric_cols:
                        return self.create_bar_chart(df, categorical_cols[0], numeric_cols[0])
            
            elif chart_type in ['histogram', 'hist']:
                col = y_col or x_col
                if col and col in df.columns:
                    return self.create_histogram(df, col)
                else:
                    # Auto-select numeric column
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if numeric_cols:
                        return self.create_histogram(df, numeric_cols[0])
            
            elif chart_type in ['line', 'line_chart']:
                if x_col and y_col and x_col in df.columns and y_col in df.columns:
                    return self.create_scatter_line(df, x_col, y_col, chart_type="line chart")
                else:
                    # Auto-select columns
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    if len(numeric_cols) >= 2:
                        return self.create_scatter_line(df, numeric_cols[0], numeric_cols[1], chart_type="line chart")
            
            # Default fallback
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) >= 2:
                return self.create_scatter_line(df, numeric_cols[0], numeric_cols[1], chart_type="scatter plot")
            else:
                raise Exception("Unable to create suggested chart with available data")
                
        except Exception as e:
            raise Exception(f"Error creating chart from suggestion: {str(e)}")
    
    def create_summary_dashboard(self, df: pd.DataFrame) -> List[go.Figure]:
        """Create a set of summary visualizations"""
        figures = []
        
        try:
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            
            # 1. Correlation matrix if enough numeric columns
            if len(numeric_cols) >= 2:
                figures.append(self.create_correlation_matrix(df))
            
            # 2. Histograms for numeric columns (first 3)
            for col in numeric_cols[:3]:
                figures.append(self.create_histogram(df, col))
            
            # 3. Bar charts for categorical columns (first 2)
            for cat_col in categorical_cols[:2]:
                if numeric_cols:
                    figures.append(self.create_bar_chart(df, cat_col, numeric_cols[0]))
            
            # 4. Scatter plot for first two numeric columns
            if len(numeric_cols) >= 2:
                figures.append(self.create_scatter_line(df, numeric_cols[0], numeric_cols[1]))
            
            return figures
            
        except Exception as e:
            st.error(f"Error creating summary dashboard: {str(e)}")
            return []
