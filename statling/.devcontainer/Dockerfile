FROM mcr.microsoft.com/devcontainers/python:1-3.14-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install additional system packages
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        zsh \
        vim \
        nano \
        tree \
        htop \
        less \
        man-db \
    && apt-get autoremove -y \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

# Install oh-my-zsh for better zsh experience
RUN sh -c "$(wget -O- https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# Set zsh as default shell for vscode user
RUN chsh -s /bin/zsh vscode

# Configure git to use color output
RUN git config --global color.ui auto

# Create workspace directory
WORKDIR /workspace

# Keep container running
CMD ["sleep", "infinity"]
