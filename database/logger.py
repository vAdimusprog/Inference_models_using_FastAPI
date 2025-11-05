import datetime
import json
import threading
import os
import pickle
import yaml
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from database.database import ClickHouse

def write_file(file, path):
    extension = os.path.splitext(path)[1]
    if extension == '.pickle':
        with open(path, 'wb') as f:
            pickle.dump(file, f)

def read_file(path):
    extension = os.path.splitext(path)[1]
    try:
        if extension == '.pickle':
            with open(path, 'rb') as f:
                file = pickle.load(f)
        elif extension == '.yaml':
            with open(path, 'r') as f:
                file = yaml.safe_load(f)
        else:
            print('Unknown extension')
            return None
    except FileNotFoundError:
        print('File not found')
        return None
    return file

database = ClickHouse()

logs = []
log_lock = threading.Lock()

prediction_logs = []
prediction_lock = threading.Lock()

class LogMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования запросов и ответов API."""

    def __init__(self, app):
        super().__init__(app)
        global logs
        logs = self._read_logs()
        self.logs_table_columns = ['predicted_tip', 'words_count', 'datetime']

    @staticmethod
    def _read_logs():
        """Читает и возвращает существующие логи из файла."""
        logs_from_file = read_file('logs.pickle')
        if logs_from_file is None:
            return []
        return logs_from_file

    def _extract_prediction_data(self, request_body: str, response_body: str) -> tuple:
        """Извлекает predicted_tip и words_count из запроса и ответа."""
        try:
            # Парсим тело запроса
            request_data = json.loads(request_body)
            
            # Парсим тело ответа
            response_data = json.loads(response_body)
            
            # Извлекаем predicted_tip из ответа
            predicted_tip = ""
            if 'predicted_tip' in response_data:
                predicted_tip = str(response_data['predicted_tip'])
            elif 'tip' in response_data:
                predicted_tip = str(response_data['tip'])
            elif 'prediction' in response_data:
                predicted_tip = str(response_data['prediction'])
            elif 'result' in response_data:
                predicted_tip = str(response_data['result'])
            
            # Извлекаем words_count из запроса
            words_count = 0
            if 'text' in request_data:
                text = str(request_data['text'])
                words_count = len(text.split())
            elif 'message' in request_data:
                text = str(request_data['message'])
                words_count = len(text.split())
            elif 'input' in request_data:
                text = str(request_data['input'])
                words_count = len(text.split())
            elif 'prompt' in request_data:
                text = str(request_data['prompt'])
                words_count = len(text.split())
            
            return predicted_tip, words_count
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"Ошибка при извлечении данных предсказания: {e}")
            return "", 0

    async def dispatch(self, request: Request, call_next):
        """Обрабатывает запрос и логирует информацию."""
        if request.url.path != "/predict":
            return await call_next(request)

        request_body = await request.body()

        try:
            json.loads(request_body)
        except json.JSONDecodeError:
            print("Не удалось распарсить тело запроса как JSON")
            return JSONResponse(content={"error": "Неверный JSON"}, status_code=400)

        async def receive():
            return {'type': 'http.request', 'body': request_body}

        request = Request(scope=request.scope, receive=receive)
        response = await call_next(request)
        response_body = b""

        async for chunk in response.body_iterator:
            response_body += chunk

        # Восстанавливаем итератор тела ответа
        response = Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )

        # Извлекаем данные для логирования
        predicted_tip, words_count = self._extract_prediction_data(
            request_body.decode("utf-8"), 
            response_body.decode("utf-8")
        )

        # Создаем лог запись в соответствии с ModelLogs
        log_entry = [
            predicted_tip,           # predicted_tip: str
            words_count,             # words_count: int (будет преобразован в Int32)
            datetime.datetime.now()  # datetime: DateTime
        ]

        with log_lock:
            logs.append(log_entry)
            write_file(logs, 'logs.pickle')

            # Вставляем логи в базу при достижении лимита
            if len(logs) >= 5:
                logs_to_insert = logs.copy()
                try:
                    database.insert_data('ModelLogs', self.logs_table_columns, logs_to_insert)
                    logs.clear()
                    write_file(logs, 'logs.pickle')
                    print(f"Вставлено {len(logs_to_insert)} записей в базу данных")
                except Exception as e:
                    print(f"Ошибка при вставке логовввв в базу данных: {e}")

        return response