# Tool chain
AWS Batch, ECS Fargate

# Pre-reading
Please read the following docs to get a basic understanding of how to work with AWS Batch. These features are used in 
operating the data pipeline.

Job Definitions with ECS Fargate: https://docs.aws.amazon.com/batch/latest/userguide/create-job-definition-Fargate.html 
Job definition parameters: https://docs.aws.amazon.com/batch/latest/userguide/job_definition_parameters.html

# Building and packaging a new inflation classifier model for AWS Batch

To build and package a new inflation classifier model for AWS Batch, follow these steps:
1. Build your model into a Docker image: `docker build -t classifier:latest .` 
2. Push the Docker image to a container registry such as Amazon Elastic Container Registry (ECR):
   1. `create_ecr_docker_permissions.sh`
   2. `build_and_push_to_ecr.sh`
   3. confirm the image was pushed: `aws ecr describe-images --repository-name pii-ecr-dev \
  --query 'imageDetails[?imageTags != null].{Tag: imageTags, Digest: imageDigest, Pushed: imagePushedAt}' \
  --output table`
3. (onetime setup by terraform) Create a new job definition in AWS Batch that references your Docker image.
4. (onetime setup by terraform) Configure the job definition parameters as needed.
5. Submit a new job to AWS Batch using the job definition: Go to the [step functions state machine dashboard.](https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/statemachines/view/arn%3Aaws%3Astates%3Aus-east-1%3A226778503410%3AstateMachine%3Apii-data-pipeline-dev?type=standard)

XXX Aren't steps 3-5 one-time setup or setup by terraform?

## Working with ECR
To get info about your ECR repo, such as the ecr repo name: `aws ecr describe-repositories`
To get metadata about the container images in your ECR repo (supply the repo name):
`aws ecr describe-images --repository-name <your-repo-name>`
To just list container images in your ECR repo (supply the repo name): `aws ecr describe-list --repository-name pii-ecr-dev`
If no tags were used, you'll only have the image digest.  However you can get the date and time of the image.

Note: when you push to ECR, it will create multiple images for metadata, architecture varients, and other purposes. The
following will filter those out and only list images with tags: `aws ecr describe-images --repository-name pii-ecr-dev \
--query 'imageDetails[?imageTags != null].{Tag: imageTags, Digest: imageDigest, Pushed: imagePushedAt}' \
--output table`

### Future
If we have more images we'll have to reorganize this to use a path to differentiate, or tag carefully, or use a 
different repo for each container.  See in Resources, Common ECR Organization Patterns.


# Resources
## Common ECR Organization Patterns

1. Hierarchical naming (recommended)

ECR supports / in repository names, which gives you a natural namespace:

team-a/api
team-a/worker
team-a/migrations
team-b/frontend
team-b/ingest
shared/base-image
shared/linter

This is the most common pattern in larger orgs. It's scannable and maps to team ownership.

2. Prefix-based (if you can't use /)

pii-api
pii-worker
pii-migrations
pii-frontend
pii-ingest

3. Tag conventions for variants within a repo

Use tags to distinguish what kind of image it is:

pii-api:latest
pii-api:v1.2.3
pii-api:dev
pii-api:staging
pii-api:prod

Or for multi-arch / multi-variant:

pii-api:amd64
pii-api:arm64
pii-api:debug

### Practical tips

Concern
Approach
Discoverability
Consistent naming convention + a README in your repo/wiki
Access control
Per-repo or per-namespace IAM policies
Cleanup
Lifecycle policies per repo (e.g., keep last 10 images)
Scanning
Enable ECR image scanning on push
Multi-env
Tags (:dev, :prod) rather than separate repos

### What to avoid

- One giant repo with everything tagged differently — becomes unmanageable
- Encoding too much in the name — pii-ecr-dev-api-v2-2024 is a mess
- Separate repos per environment — you want the same image to be promotable across envs via tag, not re-pushed

### TL;DR

<team-or-domain>/<service>

with tags for version/environment. That's what most teams converge on.
