from sentence_transformers import SentenceTransformer
import os


model_path = "E:/pet/Inference_models_using_FastAPI/functions/all-MiniLM-L6-v2"


print("Скачивание модели...")
model = SentenceTransformer('all-MiniLM-L6-v2')
model.save(model_path)
print(f"Модель сохранена в: {model_path}")