from Entity import Entity

class ModelLogs(Entity):
    
    predicted_tip: str = 'String'
    words_count: str = 'Int32'
    datetime: str = 'DateTime'

    @staticmethod
    def _after_engine() -> str:
        
        return 'ORDER BY datetime'