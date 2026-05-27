# Используем официальный образ Microsoft с уже предустановленным Playwright и браузерами
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Отключаем буферизацию логов Python (чтобы сразу видеть их в docker logs)
ENV PYTHONUNBUFFERED=1

# Копируем и устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код проекта
COPY . .

# Команда для запуска приложения модуля app
CMD ["python", "-m", "app"]