#!/bin/bash
echo " Usage: This script gets docker command authenticated to use ecr."
echo "Set AWS_PROFILE if you want to use an AWS account that's different from the default."
echo "You're presently using this identity:"
aws sts get-caller-identity --no-cli-pager

echo "Here is a list of your profiles:"
cat ~/.aws/config

echo "AWS_PROFILE is presently set to:"
echo "${AWS_PROFILE:-}"
echo
echo "Authenticating docker to ecr"

# When you run `docker tag`, you aren't just adding a label; you are creating a reference that tells Docker where the image lives.
#
# Local Image: `pii-ecr-dev:latest` (Lives on your local machine)
# Remote Image: `226778503410.dkr.ecr.us-east-1.amazonaws.com/pii-ecr-dev:latest` (Lives in AWS ECR)
#
# When you run `docker push`, Docker looks at the tag you provided. If the tag contains a registry hostname (like `amazonaws.com`), Docker knows to send the image to that specific server.
#
#If you tried to push an image tagged only as `pii-ecr-dev:latest` (without the registry URL), Docker would try to push it to Docker Hub by default, which is not where your ECR repository is.
# AWS ECR repositories are private and tied to specific AWS accounts and regions. The format `ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com` is the standard DNS name for your private registry.
#
# Commands you'll be using:
# - docker images
# - docker tag <image name>:<tag> 226778503410.dkr.ecr.us-east-1.amazonaws.com/pii-ecr-dev:latest
# - docker push 226778503410.dkr.ecr.us-east-1.amazonaws.com/pii-ecr-dev:latest

aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 226778503410.dkr.ecr.us-east-1.amazonaws.com