FROM ubuntu:latest
LABEL authors="kapis"

ENTRYPOINT ["top", "-b"]