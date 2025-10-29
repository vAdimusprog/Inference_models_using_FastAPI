import re
import contractions
from sentence_transformers import SentenceTransformer
import onnx
import onnxruntime
import numpy as np

model = SentenceTransformer('all-MiniLM-L6-v2')
class Inference:
        def __init__(self):
            self.model_path = "model.onnx"
            self.__load_model()
            self.word_to_number = {
                "joy": 0,
                "sadness": 1,
                "fear": 2,
                "anger": 3
            }

            self.number_to_word = {v: k for k, v in self.word_to_number.items()}
            
        def __load_model(self):
            self.NN = onnxruntime.InferenceSession( self.model_path)
        

        def fix_puntuation(self,text):
            return re.sub("`","'",text)

        # заменяем английские сокращения на слова "I'm" → "I am"
        def fix_contraction(self,text):
            return contractions.fix(text)

        # Удаляем все символы, кроме английских букв
        def cleaning(self,text):
            text = re.sub(r'[^a-zA-Z]|https?://\S+|www\.\S+|<.*?|0-9>', " ", text)
            text = re.sub(r'\s+', ' ', text)
            return text


        def preprocces(self,text):
            text = str(text)
            text = self.fix_puntuation(text)
            text = self.fix_contraction(text)
            text = self.cleaning(text)
            text = text.lower()
            self.embeddings = model.encode(text)
            return self.embeddings
        
        def __call__(self, text: str) -> np.ndarray:
            inputs = self.preprocces(text)
            inputs = np.array(inputs, dtype=np.float32)
            input_data = inputs.reshape(1, -1)  # (1, 384)

            output = self.NN.run(None, {'inputs': input_data})[0]
            predicted = np.argmax(output, axis=1)
            return self.number_to_word[predicted[0]]
            
            