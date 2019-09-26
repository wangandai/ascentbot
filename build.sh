pipenv lock --requirements > requirements.txt
docker build -t registry.heroku.com/msm-guild-bot/web . && docker push registry.heroku.com/msm-guild-bot/web
heroku container:release -a msm-guild-bot web

