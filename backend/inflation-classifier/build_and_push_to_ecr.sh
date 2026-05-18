#!/bin/bash
# build the docker image and push to ecr
# For this to work you need to have your permissions configured correctly. See/execute create_ecr_docker_permissions.sh

docker build -t pii-ecr-dev .
docker tag pii-ecr-dev:latest 226778503410.dkr.ecr.us-east-1.amazonaws.com/pii-ecr-dev:latest
docker push 226778503410.dkr.ecr.us-east-1.amazonaws.com/pii-ecr-dev:latest
