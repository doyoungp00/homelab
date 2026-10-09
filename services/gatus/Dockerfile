FROM docker:27-cli

RUN apk add --no-cache python3 py3-yaml

COPY generator.py /generator.py

ENTRYPOINT ["python3", "/generator.py"]
