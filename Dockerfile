FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY *.py .
RUN mkdir -p static/miniapp
COPY admin.html static/admin.html
COPY index.html static/miniapp/index.html
EXPOSE 8000
CMD ["python", "run.py"]
