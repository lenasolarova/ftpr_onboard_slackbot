FROM registry.access.redhat.com/ubi9/python-39:latest

# Metadata
LABEL maintainer="FTPR Team <lsolarov@redhat.com>"
LABEL description="Slack bot for DevLake project creation"

# Set working directory
WORKDIR /app

# Run as root temporarily to install
USER 0

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ftpr_slack_bot/ ./ftpr_slack_bot/
COPY setup.py setup.cfg README.md ./

# Install the package (set version for pbr)
ENV PBR_VERSION=1.0.0
RUN pip install --no-cache-dir .

# Switch back to non-root user
USER 1001

# Set entrypoint
ENTRYPOINT ["ftpr-slack-bot"]
