import streamlit as st
import streamlit.components.v1 as components
import geopandas as gpd
import pandas as pd
import boto3
from botocore.config import Config

AWS_ACCESS_KEY = st.secrets["AWS_ACCESS_KEY"]
AWS_SECRET_KEY = st.secrets["AWS_SECRET_KEY"]
BUCKET_NAME = st.secrets["BUCKET_NAME"]

s3 = boto3.client('s3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    config=Config(signature_version='s3v4')
)

def load_map_from_s3(metric):
    """Load HTML map file from S3"""
    key = f"maps/{metric}_map.html"
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key=key)
        return obj['Body'].read().decode('utf-8')
    except Exception as e:
        st.error(f"Error loading map: {e}")
        return None

def load_data_from_s3():
    """Load GeoJSON data from S3"""
    try:
        obj = s3.get_object(Bucket=BUCKET_NAME, Key='data/merged_map_extended.geojson')
        return gpd.read_file(obj['Body'])
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


# Page configuration
st.set_page_config(layout="wide")
st.title("Health and Food Access Dashboard")

# Load data first
merged_map = load_data_from_s3()
# Define metrics dictionary for labels
metrics = {
    "OBESITY_CrudePrev": "Obesity Prevalence",
    "DIABETES_CrudePrev": "Diabetes Prevalence",
    "BPHIGH_CrudePrev": "High Blood Pressure",
    "PCT_LACCESS_POP15": "Population with Low Food Access",
    "PCT_LACCESS_SNAP15": "SNAP Recipients with Low Food Access"
}

# Create two columns
col1, col2 = st.columns([5, 5])

with col1:
    metric = st.selectbox(
        "Select Health or Food Access Metric",
        options=list(metrics.keys()),
        format_func=lambda x: metrics[x]
    )
    
    # Load map from S3
    html_data = load_map_from_s3(metric)
    if html_data:
        components.html(html_data, height=400)
    else:
        st.error("Unable to load map data")

with col2:
    # Dynamic Statistics for Selected Metric
    st.header("Top 10 States")
    rankings = merged_map[['STATE', metric]].sort_values(
        by=metric, 
        ascending=False
    ).head(10)
    rankings[metric] = rankings[metric].round(1).astype(str) + '%'
    st.dataframe(rankings, hide_index=True)
    
    # Update summary statistics based on selected metric
    st.header("Summary Statistics")
    stats = merged_map[metric].describe()
    col2_1, col2_2, col2_3, col2_4 = st.columns(4)
    with col2_1:
        st.metric("Mean", f"{stats['mean']:.1f}%")
    with col2_2:
        st.metric("Median", f"{stats['50%']:.1f}%")
    with col2_3:
        st.metric("Maximum", f"{stats['max']:.1f}%")
    with col2_4:
        st.metric("Minimum", f"{stats['min']:.1f}%")

# Add new section for aggregate worst states analysis
st.markdown("---")  # Horizontal line
st.header("Priority States for Food Access Program")

# Calculate aggregate scores across all metrics
metrics_list = ['OBESITY_CrudePrev', 'DIABETES_CrudePrev', 'BPHIGH_CrudePrev', 
                'PCT_LACCESS_POP15', 'PCT_LACCESS_SNAP15']

# Create normalized score for each metric and sum
def get_priority_states(data, metrics):
    # Normalize each metric and sum
    normalized_scores = pd.DataFrame()
    for m in metrics:
        normalized_scores[m] = (data[m] - data[m].min()) / (data[m].max() - data[m].min())
    data['aggregate_score'] = normalized_scores.mean(axis=1)
    
    return data[['STATE', 'aggregate_score']].sort_values(
        by='aggregate_score', 
        ascending=False
    ).head(5)

priority_states = get_priority_states(merged_map_extended, metrics_list)

# Display priority states in three columns
col_p1, col_p2 = st.columns([3, 7])
with col_p1:
    st.subheader("Top 5 Priority States")
    priority_df = priority_states.copy()
    priority_df['aggregate_score'] = (priority_df['aggregate_score'] * 100).round(1).astype(str) + '%'
    st.dataframe(priority_df, hide_index=True)
with col_p2:
    st.subheader("Recommendation")
    st.write("""
    These states show consistently poor health outcomes and limited food access across all metrics, making them primary candidates for food access program implementation. The aggregate scores (shown as percentages) are calculated by normalizing each state's metrics (obesity, diabetes, blood pressure, food access, and SNAP access) to a 0-100 scale and averaging them. For example, Mississippi's 72.9% score indicates it ranks poorly across all health and access metrics, while Alabama's 64.4% suggests significant but relatively lower systemic challenges. Higher percentages indicate states facing more severe combined challenges in both health outcomes and food accessibility.
    """)


st.markdown("---")
st.header("Program Impact Analysis")

# Create three columns for key metrics
impact_col1, impact_col2, impact_col3 = st.columns(3)

with impact_col1:
    st.subheader("Food Access Impact")
    priority_states = merged_map_extended[merged_map_extended['STATE'].isin(['MS', 'WV', 'LA', 'DE', 'AL'])]
    
    # Food access metrics
    food_metrics = {
        'Low Access Population': priority_states['PCT_LACCESS_POP15'].mean(),
        'SNAP Recipients': priority_states['PCT_LACCESS_SNAP15'].mean(),
        'Low Income Access': priority_states['PCT_LACCESS_LOWI15'].mean()
                }
    for metric, value in food_metrics.items():
        st.metric(metric, f"{value:.1f}%")

with impact_col2:
    st.subheader("Demographic Impact")
    demographics = {
        'SNAP Recipients': priority_states['PCT_LACCESS_SNAP15'].mean(),
        'Low Income': priority_states['PCT_LACCESS_LOWI15'].mean(),
        'Seniors': priority_states['PCT_LACCESS_SENIORS15'].mean(),
        'White Population': priority_states['PCT_LACCESS_WHITE15'].mean(),
        'Black Population': priority_states['PCT_LACCESS_BLACK15'].mean(),
        'Hispanic Population': priority_states['PCT_LACCESS_HISP15'].mean()
    }
    for group, value in demographics.items():
        st.metric(group, f"{value:.1f}%")


with impact_col3:
    st.subheader("Current Health Status")
    health_metrics = {
        'Obesity Rate': priority_states['OBESITY_CrudePrev'].mean(),
        'Diabetes Rate': priority_states['DIABETES_CrudePrev'].mean(),
        'High BP Rate': priority_states['BPHIGH_CrudePrev'].mean()
    }
    for metric, value in health_metrics.items():
        st.metric(metric, f"{value:.1f}%")

# Add program recommendations
st.markdown("""
### Implementation Strategy
1. **Target Population**: Focus on areas where 18.5% of the population has limited food access
2. **Key Demographics**: 
   - Seniors (2.7% with low access)
   - Low-income residents (7.8% with low access)
3. **Health Impact**: Based on current health metrics in priority states:
   - 38.5% obesity rate
   - 14.3% diabetes rate
   - 41.4% high blood pressure rate
4. **Focus Areas**: Target regions with highest concentration of SNAP recipients and low-income populations with limited food access
""")

