import datetime
import re
from pydantic import BaseModel, field_validator


class Text(BaseModel):
    text: str
    
    @field_validator('text')
    def text_validator(cls, text):

        if not text or not text.strip():
            raise ValueError('Текст не должен быть пустым')

        if not re.search(r'[a-zA-Zа-яА-Я]', text):
            raise ValueError('Текст должен содержать буквы')
        

        if len(text.strip()) < 2:
            raise ValueError('Текст должен содержать минимум 2 символа')
        
        return text.strip()