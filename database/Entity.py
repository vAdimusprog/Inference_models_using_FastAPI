from abc import ABC, abstractmethod
from enum import Enum


class AutoRegisterMeta(type(Enum), type(ABC)):
    def __new__(cls, class_name, base_classes, class_attributes):
        new_class = type.__new__(cls, class_name, base_classes, class_attributes)
        
        for base_class in base_classes:
            if hasattr(base_class, 'register_subclass'):
                base_class.register_subclass(new_class)
                
        return new_class


class Entity(ABC, Enum, metaclass=AutoRegisterMeta):
    _registered_classes = []

    @classmethod
    def register_subclass(cls, new_subclass):
        cls._registered_classes.append(new_subclass)

    @classmethod
    def get_concrete_classes(cls):
        return cls._registered_classes

    @classmethod
    def generate_create_table_schema(cls):
        column_definitions = []
        
        for attribute_name, attribute_type in cls.__dict__.items():
            if not attribute_name.startswith("_"):
                column_definitions.append(f'{attribute_name} {attribute_type}')
        
        columns_sql = ', '.join(column_definitions)
        return f'({columns_sql})'

    @staticmethod
    @abstractmethod
    def _after_engine():
        pass

    @staticmethod
    def _engine():
        return "MergeTree"