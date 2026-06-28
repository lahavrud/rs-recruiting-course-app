#!/bin/sh
# LocalStack runs every *.sh in /etc/localstack/init/ready.d once SQS is ready.
# Create the task queue the API enqueues to and the worker consumes from.
awslocal sqs create-queue --queue-name rs-recruiting-tasks
