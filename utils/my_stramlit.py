import datetime
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from database.database import ClickHouse

PREDICTED_TIP = 'predicted_tip'
WORDS_COUNT = 'words_count'
PREDICTION_LOGS_TABLE = 'model_logs2.ModelLogs'


@st.cache_resource
def get_database() -> ClickHouse:
    return ClickHouse()


@st.cache_data
def get_min_date(_database: ClickHouse) -> datetime.date:
    """Fetches the minimum datetime from the ModelLogs table."""
    result = _database.execute_query(f"SELECT MIN(datetime) as min_value FROM {PREDICTION_LOGS_TABLE}")
    if not result.empty and 'min_value' in result and pd.notna(result['min_value'][0]):
        return result['min_value'][0].date()
    return datetime.date.today()


def get_value_range(_database: ClickHouse, column_name: str) -> Optional[tuple[float, float]]:
    """Fetches the min and max values for a given column."""
    query = f"SELECT MIN({column_name}) as min_value, MAX({column_name}) as max_value FROM {PREDICTION_LOGS_TABLE}"
    result = _database.execute_query(query)
    if not result.empty and pd.notna(result['min_value'][0]) and pd.notna(result['max_value'][0]):
        return float(result['min_value'][0]), float(result['max_value'][0])
    return None


def update_slider_range(_database: ClickHouse, selected_columns: list[str]) -> tuple[float, float, tuple[float, float]]:
    """Calculates the min, max and value range for the slider based on selected columns."""
    if not selected_columns:
        return 0.0, 100.0, (0.0, 100.0)

    ranges = [get_value_range(_database, col) for col in selected_columns]
    valid_ranges = [r for r in ranges if r is not None]

    if not valid_ranges:
        return 0.0, 100.0, (0.0, 100.0)

    min_value = min(r[0] for r in valid_ranges)
    max_value = max(r[1] for r in valid_ranges)

    return min_value, max_value, (min_value, max_value)


def plot_distribution(_database: ClickHouse, column_name: str, bin_range: tuple[float, float]) -> go.Figure:
    """Generates a histogram for the selected column within a given range."""
    query = f"""
        SELECT {column_name} FROM {PREDICTION_LOGS_TABLE}
        WHERE {column_name} >= %(min_value)s AND {column_name} <= %(max_value)s
    """
    params = {'min_value': bin_range[0], 'max_value': bin_range[1]}
    dataframe = _database.execute_query(query, params)
    
    if dataframe.empty:
        return go.Figure().update_layout(title='Нет данных для отображения')
    
    data = dataframe[column_name]
    numeric_data = pd.to_numeric(data, errors='coerce')
    is_numeric = not numeric_data.isna().all()
    
    fig = go.Figure()
    
    if is_numeric:
        fig.add_trace(go.Histogram(
            x=numeric_data.dropna(),
            name="Длина предложения",
            opacity=1.0
        ))
        fig.update_layout(
            xaxis_title="Количество слов в запросе",
            yaxis_title='Количество запросов',
            title=f'Распределение для {column_name.replace("_", " ").title()}'
        )
    else:
        value_counts = data.value_counts()
        fig.add_trace(go.Bar(
            x=value_counts.index,
            y=value_counts.values,
            name="Предсказания"
        ))
        fig.update_layout(
            xaxis_title="Предсказание",
            yaxis_title='Количество',
            title=f'Распределение для {column_name.replace("_", " ").title()}'
        )
    
    return fig


def get_data_summary(_database: ClickHouse, selected_column: str) -> str:
    """Generates summary statistics for the selected column."""
    query = f"SELECT {selected_column} FROM {PREDICTION_LOGS_TABLE} LIMIT 1000"
    dataframe = _database.execute_query(query)
    
    if dataframe.empty or selected_column not in dataframe.columns:
        return "Нет доступных данных"
    
    data = dataframe[selected_column]
    numeric_data = pd.to_numeric(data, errors='coerce')
    is_numeric = not numeric_data.isna().all()
    
    if is_numeric:
        valid_data = numeric_data.dropna()
        summary = f"""
        **Статистика для {selected_column.replace('_', ' ').title()}**
        
        Всего записей: {len(data):,}
        Валидных числовых записей: {len(valid_data):,}
        Среднее значение: {valid_data.mean():.2f}
        Медиана: {valid_data.median():.2f}
        Стандартное отклонение: {valid_data.std():.2f}
        Минимальное значение: {valid_data.min():.2f}
        Максимальное значение: {valid_data.max():.2f}
        Пропущенные значения: {numeric_data.isnull().sum()}
        """
    else:
        unique_values = data.unique()
        value_counts = data.value_counts()
        summary = f"""
        **Статистика для {selected_column.replace('_', ' ').title()}**
        
        Всего записей: {len(data):,}
        Уникальных классов: {len(unique_values)}
        Самый частый класс: '{value_counts.index[0]}' ({value_counts.iloc[0]} вхождений)
        Пропущенные значения: {data.isnull().sum()}
        """
    
    return summary


def get_sample_data(_database: ClickHouse, selected_column: str, limit: int = 1000) -> pd.DataFrame:
    """Fetches sample data from the database."""
    query = f"SELECT {selected_column} FROM {PREDICTION_LOGS_TABLE} LIMIT {limit}"
    return _database.execute_query(query)


def main():
    st.set_page_config(page_title="Классификация эмоций", layout="wide")
    st.title("Дашборд для мониторинга модели классификации эмоций")

    database = get_database()
    min_date = get_min_date(database)
    today = datetime.date.today()

    st.sidebar.header("Фильтры")

    # Выбор колонки для анализа
    selected_column = st.sidebar.radio(
        "Выберите параметр для анализа:",
        options=[PREDICTED_TIP, WORDS_COUNT],
        format_func=lambda x: "Предсказание" if x == PREDICTED_TIP else "Длина предложения"
    )

    # Слайдер для фильтрации значений
    min_val, max_val, val_range = update_slider_range(database, [selected_column])
    value_range = st.sidebar.slider(
        "Фильтр по значению:",
        min_value=min_val,
        max_value=max_val,
        value=val_range,
        step=1.0
    )

    # Фильтр по дате
    date_range = st.sidebar.date_input(
        "Выберите диапазон дат:",
        value=(min_date, today),
        min_value=min_date,
        max_value=today
    )

    # Основная часть дашборда
    col1, col2 = st.columns([2, 1])

    with col1:
        st.header("Распределение данных")
        st.plotly_chart(plot_distribution(database, selected_column, value_range), use_container_width=True)

    with col2:
        st.header("Общая информация")
        summary = get_data_summary(database, selected_column)
        st.markdown(summary)

    # Таблица с данными
    st.header("Пример данных")
    sample_data = get_sample_data(database, selected_column)
    if not sample_data.empty:
        st.dataframe(sample_data, use_container_width=True)
    else:
        st.info("Нет данных для отображения")

    # Дополнительная статистика
    st.header("Детальная статистика")
    if not sample_data.empty and selected_column in sample_data.columns:
        data = sample_data[selected_column]
        numeric_data = pd.to_numeric(data, errors='coerce')
        
        if not numeric_data.isna().all():
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Среднее значение", f"{numeric_data.mean():.2f}")
            with col2:
                st.metric("Медиана", f"{numeric_data.median():.2f}")
            with col3:
                st.metric("Стандартное отклонение", f"{numeric_data.std():.2f}")


if __name__ == "__main__":
    main()
