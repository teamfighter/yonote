# Base on Debian Bullseye (glibc 2.31) with Python 3.11 for compatibility with older Linux distributions.
FROM python:3.11-slim-bullseye
WORKDIR /app
COPY yonote_cli ./yonote_cli
RUN pip install -e ./yonote_cli
ENTRYPOINT ["yonote"]
