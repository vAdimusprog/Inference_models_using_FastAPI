import os
import threading
from typing import Any
from database.Entity import Entity
import clickhouse_connect
from dotenv import load_dotenv


class ClickHouse:
    """Клиент для работы с базой данных ClickHouse"""
    
    _query_lock = threading.Lock()

    def __init__(self, create_tables_on_init: bool = True):
        load_dotenv()

        self.host = os.environ.get('CLICKHOUSE_HOST', 'localhost')
        self.port = int(os.environ.get('CLICKHOUSE_PORT', 8123))
        self.username = os.environ.get('CLICKHOUSE_USERNAME', 'default')
        self.password = os.environ.get('CLICKHOUSE_PASSWORD', '')
        self.database_name = os.environ.get('CLICKHOUSE_DATABASE', 'default')
        
        # Создаем базу данных если нужно
        self._create_database_if_missing()
        
        # Подключаемся к базе данных
        self.db_client = clickhouse_connect.get_client(
            host=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            database=self.database_name
        )

        if create_tables_on_init:
            self.create_tables()

    def _create_database_if_missing(self):
        """Создает базу данных и таблицу если они не существуют"""
        try:
            temp_client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password
            )
            
            # Создаем базу данных если не существует
            temp_client.command(f'CREATE DATABASE IF NOT EXISTS `{self.database_name}`')
            print(f"✅ База данных '{self.database_name}' создана или уже существует")
            
            # Создаем таблицу ModelLogs если не существует
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS `{self.database_name}`.`ModelLogs`
            (
                predicted_tip String,
                words_count Int32,
                datetime DateTime
            ) ENGINE = MergeTree()
            ORDER BY datetime
            """
            temp_client.command(create_table_sql)
            print(f"✅ Таблица '{self.database_name}.ModelLogs' создана или уже существует")
            
            temp_client.close()
        except Exception as e:
            print(f"❌ Ошибка при создании базы данных/таблицы: {e}")

    @staticmethod
    def sanitize_sql_value(input_value: Any) -> str:
        """Обезвреживает строковые значения для защиты от SQL-инъекций"""
        if not isinstance(input_value, str):
            return str(input_value)
        
        safe_value = (
            input_value
            .replace("'", "''")  
            .replace(";", "")    
            .replace("--", "")   
        )
        return safe_value

    def create_tables(self):
        """Создает все таблицы на основе моделей Entity"""
        try:
            entity_classes = Entity.get_concrete_classes()

            for entity_class in entity_classes:
                table_schema = entity_class.generate_create_table_schema()
                table_engine = entity_class._engine()
                table_options = entity_class._after_engine()

                create_table_sql = (
                    f'CREATE TABLE IF NOT EXISTS `{entity_class.__name__}` '
                    f'{table_schema} ENGINE {table_engine} {table_options}'
                )
                
                self.db_client.command(create_table_sql)
                print(f"✅ Таблица '{entity_class.__name__}' создана")
        except Exception as e:
            print(f"❌ Ошибка при создании таблиц: {e}")

    def insert_data(self, table_name: str, columns: list[str], data_rows: list[list[Any]]):
        """Вставляет данные в указанную таблицу"""
        try:
            # Добавляем имя базы данных к имени таблицы
            full_table_name = f"`{self.database_name}`.`{table_name}`"
            self.db_client.insert(full_table_name, data_rows, column_names=columns)
            print(f"✅ Данные вставлены в таблицу {full_table_name}")
        except Exception as e:
            print(f"❌ Ошибка при вставке данных: {e}")
            raise

    def execute_query(self, sql_query: str, parameters: dict = None) -> Any:
        """Выполняет SQL запрос и возвращает результат"""
        with self._query_lock:
            try:
                
                query_result = self.db_client.query_df(sql_query, parameters)
                return query_result
            except Exception as e:
                print(f"❌ Ошибка при выполнении запроса: {e}")
                return None