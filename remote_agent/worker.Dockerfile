FROM node:20-slim

# Install Claude Code CLI
RUN npm install -g @anthropic-ai/claude-code

# Pre-install common MCP servers for faster startup
RUN npx -y @anthropic-ai/mcp-filesystem --version 2>/dev/null || true
RUN npx -y @anthropic-ai/mcp-git --version 2>/dev/null || true

# Install Python for data platform workers
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip git curl jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENTRYPOINT ["claude", "--print", "--output-format", "json"]
