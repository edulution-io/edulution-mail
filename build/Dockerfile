FROM ubuntu:latest

RUN apt-get update && apt-get install -y curl git mariadb-client python3-pip
RUN pip3 install python-keycloak==2.10.0
RUN curl -sSL https://get.docker.com/ | CHANNEL=stable sh

RUN mkdir -p /opt/ && cd /opt/ && git clone https://github.com/mailcow/mailcow-dockerized mailcow

COPY ./entrypoint.sh entrypoint.sh
RUN chmod +x entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]