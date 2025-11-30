FROM python:3.10-slim

# جلوگیری از ایجاد فایل‌های pyc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# محل پروژه
WORKDIR /app

# نصب وابستگی‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی پروژه
COPY . .

# ساخت پوشه media
RUN mkdir -p media

EXPOSE 8000

# اجرای پروژه
CMD ["python", "app.py"]
