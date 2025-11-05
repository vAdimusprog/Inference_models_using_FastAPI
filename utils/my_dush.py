import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dash import Dash, html, dash_table, dcc, callback, Output, Input, State
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from database.database import ClickHouse

PREDICTED_TIP = 'predicted_tip'
WORDS_COUNT = 'words_count'
PREDICTION_LOGS_TABLE = 'model_logs2.ModelLogs'

database = ClickHouse()

#Строим гистограмму
def plot_distribution(column_name: str) -> go.Figure | None:
    dataframe = database.execute_query(
        f'select {column_name} from {PREDICTION_LOGS_TABLE}'
    )
    
    if len(dataframe) == 0:
        return None
    data = dataframe[column_name]
    
    numeric_data = pd.to_numeric(data, errors='coerce')
    is_numeric = not numeric_data.isna().all()
    
    if is_numeric:
        fig = go.Figure()
        fig.add_trace(go.Histogram(
            x=numeric_data.dropna(),
            name="Длина предложения",
            opacity=1.0
        ))
        fig.update_layout(
            xaxis_title="Количество слов в запросе",
            yaxis_title='Количество запросов'
        )
    else:
        value_counts = data.value_counts()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=value_counts.index,
            y=value_counts.values,
            name="Предсказания"
        ))
        fig.update_layout(
            xaxis_title="Предсказание",
            yaxis_title='Количество'
        )
    
    return fig

# Получаем данные из ClickHouse
def get_clickhouse_data():
    query = f"""
    SELECT {PREDICTED_TIP}, {WORDS_COUNT} 
    FROM {PREDICTION_LOGS_TABLE} 
    LIMIT 1000
    """
    return database.execute_query(query)


df = get_clickhouse_data()

external_stylesheets = [dbc.themes.CERULEAN]
app = Dash(__name__, external_stylesheets=external_stylesheets)

app.layout = dbc.Container([
    dbc.Row([
        html.Div('Дашборд для модели классификации эмоций', className="text-primary text-center fs-3")
    ]),

    dbc.Row([
        dbc.Col([
            dbc.RadioItems(
                options=[
                    {"label": "Предсказание", "value": PREDICTED_TIP},
                    {"label": "Длина предложения", "value": WORDS_COUNT}
                ],
                value=PREDICTED_TIP,
                inline=True,
                id='column-selector'
            )
        ], width=8),
        
        dbc.Col([
            dbc.Button("Показать всю таблицу", id="show-table-btn", color="primary", className="me-2"),
        ], width=4, className="d-flex align-items-center justify-content-end")
    ], style={'margin': '20px 0'}, className="align-items-center"),

    # Модальное окно для полной таблицы
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Full Data Table")),
        dbc.ModalBody([
            dash_table.DataTable(
                data=df.to_dict('records') if not df.empty else [],
                page_size=20,
                style_table={'overflowX': 'auto'},
                style_cell={
                    'minWidth': '100px', 'width': '150px', 'maxWidth': '300px',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                },
                id='full-data-table'
            )
        ]),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-full-table", className="ms-auto")
        ),
    ], id="modal-full-table", size="xl", scrollable=True),

    dbc.Row([
        dbc.Col([
            html.H4("Данные", className="text-center mb-3"),
            dash_table.DataTable(
                data=df.to_dict('records') if not df.empty else [],
                page_size=12, 
                style_table={'overflowX': 'auto', 'height': '400px', 'overflowY': 'auto'},
                style_cell={
                    'minWidth': '100px', 'width': '150px', 'maxWidth': '200px',
                    'overflow': 'hidden',
                    'textOverflow': 'ellipsis',
                },
                id='data-table'
            )
        ], width=6),

        dbc.Col([
            html.H4("Зависимость", className="text-center mb-3"),
            dcc.Graph(
                figure={}, 
                id='distribution-graph',
                style={'height': '400px'}  
            )
        ], width=6),
    ], style={'margin-bottom': '20px'}),

    # Строка с статистикой
    dbc.Row([
        dbc.Col([
            html.H4("Общая информация", className="text-center mb-3"),
            html.Div(id="data-summary", className="p-3 bg-light rounded")
        ], width=12)
    ])

], fluid=True)

# Callback для открытия/закрытия модального окна
@app.callback(
    Output("modal-full-table", "is_open"),
    [Input("show-table-btn", "n_clicks"), 
     Input("close-full-table", "n_clicks")],
    [State("modal-full-table", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open

# Callback для обновления графика распределения
@app.callback(
    Output(component_id='distribution-graph', component_property='figure'),
    Input(component_id='column-selector', component_property='value')
)
def update_distribution(selected_column):
    if df.empty:
        return go.Figure()
    
    fig = plot_distribution(selected_column)
    if fig is None:
        return go.Figure()
    
    fig.update_layout(
        title=f'Гистограмма для {selected_column.replace("_", " ").title()}',
        height=350,
        margin=dict(l=50, r=50, t=50, b=50) 
    )
    return fig

# Callback для обновления таблицы
@app.callback(
    Output(component_id='data-table', component_property='data'),
    Input(component_id='column-selector', component_property='value')
)
def update_table(selected_column):
    """Обновляет таблицу для показа выбранной колонки"""
    if df.empty:
        return []
    
    # Показываем только выбранную колонку в таблице
    table_data = df[[selected_column]].to_dict('records')
    return table_data

# Callback для обновления статистики
@app.callback(
    Output(component_id='data-summary', component_property='children'),
    Input(component_id='column-selector', component_property='value')
)
def update_summary(selected_column):
    if df.empty or selected_column not in df.columns:
        return "Нет доступных данных"
    
    data = df[selected_column]
    
    # Проверяем тип данных
    numeric_data = pd.to_numeric(data, errors='coerce')
    is_numeric = not numeric_data.isna().all()
    
    if is_numeric:
        # Статистика для числовых данных
        valid_data = numeric_data.dropna()
        stats = [
            html.H5(f"Статистика для {selected_column.replace('_', ' ').title()}"),
            html.P(f"Всего записей: {len(data):,}"),
            html.P(f"Валидных числовых записей: {len(valid_data):,}"),
            html.P(f"Среднее значение: {valid_data.mean():.2f}"),
            html.P(f"Медиана: {valid_data.median():.2f}"),
            html.P(f"Стандартное отклонение: {valid_data.std():.2f}"),
            html.P(f"Минимальное значение: {valid_data.min():.2f}"),
            html.P(f"Максимальное значение: {valid_data.max():.2f}"),
            html.P(f"Пропущенные значения: {numeric_data.isnull().sum()}"),
            html.P(f"Тип данных: {data.dtype}")
        ]
    else:
        # Статистика для категориальных данных
        unique_values = data.unique()
        value_counts = data.value_counts()
        stats = [
            html.H5(f"Статистика для {selected_column.replace('_', ' ').title()}"),
            html.P(f"Всего записей: {len(data):,}"),
            html.P(f"Уникальных классов: {len(unique_values)}"),
            html.P(f"Самый частый класс: '{value_counts.index[0]}' ({value_counts.iloc[0]} вхождений)"),
            html.P(f"Пропущенные значения: {data.isnull().sum()}"),
            html.P(f"Тип данных: {data.dtype}"),
            html.P(html.Strong("Все уникальные классы:")),
            html.Ul([html.Li(f"{cls}") for cls in sorted(unique_values)]),
            html.P(html.Strong("Распределение классов:")),
            html.Ul([html.Li(f"{cls}: {count} вхождений") for cls, count in value_counts.head(10).items()])
        ]
    
    return stats

if __name__ == '__main__':
    app.run(debug=True)