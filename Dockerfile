FROM python:3.7
COPY . .
RUN pip install -r requirements.txt
ENV LISTEN_MODE=webhook
ENV MODE=prd
ENV WEBHOOK_HOST=https://msm-guild-bot.herokuapp.com
CMD python3 poll.py