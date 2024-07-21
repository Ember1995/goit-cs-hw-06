FROM python:3.10

ENV APP_HOME /app

WORKDIR $APP_HOME

COPY . .

COPY .env $APP_HOME/.env

RUN pip install -r requirements.txt

EXPOSE 3000
EXPOSE 5000

ENTRYPOINT ["python", "main.py"]
