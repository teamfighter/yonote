FROM python:3.12-slim
WORKDIR /app
COPY yonote_cli ./yonote_cli
RUN pip install -e ./yonote_cli
ENTRYPOINT ["yonote"]
