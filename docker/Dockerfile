# Build on Debian Bullseye (glibc 2.31) with Python 3.11 to produce binaries
# that run on older Linux distributions.  Building on newer releases (e.g.
# Python 3.12 base images) links against glibc 2.38, which fails on systems with
# older libc versions.
FROM python:3.11-slim-bullseye
WORKDIR /app
COPY yonote_cli ./yonote_cli
RUN pip install -e ./yonote_cli
ENTRYPOINT ["yonote"]
