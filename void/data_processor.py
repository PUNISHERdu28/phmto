import pandas as pd
import json
import numpy as np
from typing import Union, Dict, Any
import streamlit as st

class DataProcessor:
    """Handles data loading, cleaning, and preprocessing"""
    
    def load_file(self, uploaded_file) -> pd.DataFrame:
        """Load CSV or JSON file and return pandas DataFrame"""
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            if file_extension == 'csv':
                # Try different encodings
                try:
                    df = pd.read_csv(uploaded_file, encoding='utf-8')
                except UnicodeDecodeError:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, encoding='latin-1')
                    
            elif file_extension == 'json':
                # Handle different JSON structures
                content = uploaded_file.read()
                data = json.loads(content)
                
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    # Try to normalize nested JSON
                    try:
                        df = pd.json_normalize(data)
                    except:
                        # If normalization fails, convert dict to single row
                        df = pd.DataFrame([data])
                else:
                    raise ValueError("Unsupported JSON structure")
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            # Basic data cleaning
            df = self.clean_data(df)
            
            return df
            
        except Exception as e:
            raise Exception(f"Failed to load file: {str(e)}")
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Perform basic data cleaning"""
        # Remove completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Convert numeric strings to numbers where possible
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert to numeric
                numeric_series = pd.to_numeric(df[col], errors='coerce')
                if not numeric_series.isna().all():
                    # If more than 50% of values can be converted, convert the column
                    if (numeric_series.notna().sum() / len(df)) > 0.5:
                        df[col] = numeric_series
        
        # Convert date-like strings to datetime
        for col in df.columns:
            if df[col].dtype == 'object':
                # Check if column contains date-like strings
                sample_values = df[col].dropna().head(10)
                if len(sample_values) > 0:
                    try:
                        pd.to_datetime(sample_values, errors='raise')
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                    except:
                        pass
        
        return df
    
    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate comprehensive data summary"""
        summary = {
            'shape': df.shape,
            'columns': list(df.columns),
            'dtypes': df.dtypes.to_dict(),
            'missing_values': df.isnull().sum().to_dict(),
            'memory_usage': df.memory_usage(deep=True).sum(),
            'numeric_columns': df.select_dtypes(include=[np.number]).columns.tolist(),
            'categorical_columns': df.select_dtypes(include=['object', 'category']).columns.tolist(),
            'datetime_columns': df.select_dtypes(include=['datetime64']).columns.tolist()
        }
        
        # Add statistical summary for numeric columns
        numeric_cols = summary['numeric_columns']
        if numeric_cols:
            summary['numeric_stats'] = df[numeric_cols].describe().to_dict()
        
        # Add unique value counts for categorical columns
        categorical_cols = summary['categorical_columns'][:10]  # Limit to first 10 for performance
        if categorical_cols:
            summary['categorical_stats'] = {}
            for col in categorical_cols:
                unique_count = df[col].nunique()
                summary['categorical_stats'][col] = {
                    'unique_count': unique_count,
                    'top_values': df[col].value_counts().head(5).to_dict() if unique_count <= 100 else {}
                }
        
        return summary
    
    def detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect anomalies in numeric columns using IQR method"""
        anomalies = {}
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        for col in numeric_cols:
            data = df[col].dropna()
            if len(data) > 0:
                Q1 = data.quantile(0.25)
                Q3 = data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outliers = data[(data < lower_bound) | (data > upper_bound)]
                if len(outliers) > 0:
                    anomalies[col] = {
                        'count': len(outliers),
                        'percentage': (len(outliers) / len(data)) * 100,
                        'bounds': {'lower': lower_bound, 'upper': upper_bound},
                        'outlier_values': outliers.tolist()[:10]  # Limit to first 10
                    }
        
        return anomalies
    
    def get_correlation_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate correlation matrix for numeric columns"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 1:
            return df[numeric_cols].corr()
        else:
            return pd.DataFrame()
    
    def prepare_data_for_ai(self, df: pd.DataFrame, max_rows: int = 100) -> str:
        """Prepare data summary for AI analysis"""
        # Get basic summary
        summary = self.get_data_summary(df)
        
        # Get sample data
        sample_df = df.head(max_rows)
        
        # Prepare text summary
        ai_summary = f"""
        Dataset Summary:
        - Shape: {summary['shape'][0]} rows, {summary['shape'][1]} columns
        - Columns: {', '.join(summary['columns'])}
        - Data types: {summary['dtypes']}
        - Missing values: {summary['missing_values']}
        
        Sample data (first {len(sample_df)} rows):
        {sample_df.to_string()}
        
        Statistical summary for numeric columns:
        {df.describe().to_string() if len(summary['numeric_columns']) > 0 else 'No numeric columns'}
        """
        
        return ai_summary
