import pickle
with open('logs.pickle', 'rb') as f:
    logs_data = pickle.load(f)

print(f"Всего записей в логах: {len(logs_data)}")
for i, log in enumerate(logs_data):
    print(f"Запись {i+1}: {log}")