#!/bin/bash
# Deploy to Render
# Prerequisites: Render CLI installed and authenticated
# Install: https://render.com/docs/cli

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Render Deployment Script ===${NC}"

# Check if render.yaml exists
if [ ! -f "render.yaml" ]; then
    echo -e "${RED}Error: render.yaml not found${NC}"
    echo "This file should be in the root of your repository"
    exit 1
fi

# Load environment variables from .env if it exists
if [ -f .env ]; then
    echo -e "${GREEN}Loading environment variables from .env${NC}"
    set -a
    source .env
    set +a
fi

echo -e "\n${YELLOW}=== Render Deployment Options ===${NC}"
echo "1. Deploy via Render Dashboard (recommended for first deployment)"
echo "2. Deploy via Render CLI"
echo ""
read -p "Choose option (1 or 2): " DEPLOY_OPTION

case $DEPLOY_OPTION in
    1)
        echo -e "\n${GREEN}=== Dashboard Deployment Instructions ===${NC}"
        echo ""
        echo "1. Go to https://dashboard.render.com"
        echo "2. Click 'New +' -> 'Blueprint'"
        echo "3. Connect your GitHub/GitLab repository"
        echo "4. Render will detect render.yaml and configure the service"
        echo "5. Set the following environment variables in the dashboard:"
        echo ""
        echo -e "${YELLOW}Required:${NC}"
        echo "  DB_HOST        - Database host"
        echo "  DB_PORT        - Database port (usually 5432)"
        echo "  DB_USER        - Database username"
        echo "  DB_PASS        - Database password"
        echo "  DB_DATABASE    - Database name"
        echo "  ADMIN_SECRET   - Admin authentication secret"
        echo ""
        echo -e "${YELLOW}LLM API Keys (at least one required):${NC}"
        echo "  GOOGLE_API_KEY    - Google/Gemini API key"
        echo "  OPENAI_API_KEY    - OpenAI API key"
        echo "  ANTHROPIC_API_KEY - Anthropic API key"
        echo ""
        echo -e "${YELLOW}Optional:${NC}"
        echo "  QDRANT_URL          - Qdrant vector database URL"
        echo "  QDRANT_API_KEY      - Qdrant API key"
        echo "  SECRET_TOKEN_ENC_KEY - Token encryption key"
        echo ""
        echo -e "${BLUE}Prompts Storage (pre-configured with defaults):${NC}"
        echo "  PROMPT_STORAGE_BACKEND - postgres (default), langsmith, service"
        echo "  LANGCHAIN_API_KEY      - LangChain API key (if backend=langsmith)"
        echo "  SERVICE_PROMPTS        - External prompts service URL (if backend=service)"
        echo ""
        echo -e "${BLUE}Observability (pre-configured with defaults):${NC}"
        echo "  OTEL_TRACING_BACKEND - Tracing: console, otlp, jaeger, sentry"
        echo "  OTEL_LOGGING_BACKEND - Logging: console, otlp, logtail"
        echo "  OTEL_LOG_LEVEL       - Log level: DEBUG, INFO, WARNING, ERROR"
        echo ""
        echo -e "${BLUE}Observability Backend-Specific:${NC}"
        echo "  SENTRY_DSN                - Sentry DSN (if using sentry backend)"
        echo "  OTEL_OTLP_ENDPOINT        - OTLP collector endpoint"
        echo "  OTEL_JAEGER_AGENT_HOST    - Jaeger agent host"
        echo "  BETTERSTACK_SOURCE_TOKEN  - Better Stack/Logtail token"
        echo "  BETTERSTACK_HOST          - Better Stack host URL"
        echo ""
        echo "6. Click 'Apply' to deploy"
        echo ""
        echo -e "${GREEN}Opening Render Dashboard...${NC}"

        # Try to open browser
        if command -v open &> /dev/null; then
            open "https://dashboard.render.com/select-repo?type=blueprint"
        elif command -v xdg-open &> /dev/null; then
            xdg-open "https://dashboard.render.com/select-repo?type=blueprint"
        else
            echo "Please open: https://dashboard.render.com/select-repo?type=blueprint"
        fi
        ;;
    2)
        echo -e "\n${GREEN}=== CLI Deployment ===${NC}"

        # Check if Render CLI is installed
        if ! command -v render &> /dev/null; then
            echo -e "${RED}Error: Render CLI is not installed${NC}"
            echo "Install it from: https://render.com/docs/cli"
            exit 1
        fi

        # Check if logged in
        if ! render whoami &> /dev/null 2>&1; then
            echo -e "${YELLOW}Not logged in to Render. Please login:${NC}"
            render login
        fi

        # Function to prompt for environment variable
        prompt_env() {
            local var_name=$1
            local prompt_text=$2
            local is_secret=${3:-false}

            if [ -z "${!var_name}" ]; then
                if [ "$is_secret" = true ]; then
                    read -sp "$prompt_text: " value
                    echo
                else
                    read -p "$prompt_text: " value
                fi
                export "$var_name=$value"
            fi
        }

        echo -e "${YELLOW}Checking required environment variables...${NC}"

        # Required variables
        prompt_env "DB_HOST" "Enter database host"
        prompt_env "DB_PORT" "Enter database port (default: 5432)"
        DB_PORT=${DB_PORT:-5432}
        prompt_env "DB_USER" "Enter database user"
        prompt_env "DB_PASS" "Enter database password" true
        prompt_env "DB_DATABASE" "Enter database name"
        prompt_env "ADMIN_SECRET" "Enter admin secret" true

        # LLM API Keys
        echo -e "\n${YELLOW}LLM API Keys (at least one required):${NC}"
        prompt_env "GOOGLE_API_KEY" "Enter Google API key (press Enter to skip)" true
        prompt_env "OPENAI_API_KEY" "Enter OpenAI API key (press Enter to skip)" true
        prompt_env "ANTHROPIC_API_KEY" "Enter Anthropic API key (press Enter to skip)" true

        if [ -z "$GOOGLE_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
            echo -e "${RED}Error: At least one LLM API key is required${NC}"
            exit 1
        fi

        # Prompts storage configuration
        echo -e "\n${BLUE}=== Prompts Storage Configuration ===${NC}"
        echo "Backends: postgres (default), langsmith, service"
        echo ""

        prompt_env "PROMPT_STORAGE_BACKEND" "Enter prompts backend (default: postgres)"
        PROMPT_STORAGE_BACKEND=${PROMPT_STORAGE_BACKEND:-postgres}

        if [[ "$PROMPT_STORAGE_BACKEND" == "langsmith" ]]; then
            prompt_env "LANGCHAIN_API_KEY" "Enter LangChain API key" true
        fi

        if [[ "$PROMPT_STORAGE_BACKEND" == "service" ]]; then
            prompt_env "SERVICE_PROMPTS" "Enter external prompts service URL"
        fi

        # Observability configuration
        echo -e "\n${BLUE}=== Observability Configuration ===${NC}"
        echo "Tracing backends: console, otlp, jaeger, sentry"
        echo "Logging backends: console, otlp, logtail (comma-separated)"
        echo ""

        prompt_env "OTEL_TRACING_BACKEND" "Enter tracing backend (default: console)"
        OTEL_TRACING_BACKEND=${OTEL_TRACING_BACKEND:-console}

        prompt_env "OTEL_LOGGING_BACKEND" "Enter logging backend (default: console)"
        OTEL_LOGGING_BACKEND=${OTEL_LOGGING_BACKEND:-console}

        # Backend-specific configuration
        if [[ "$OTEL_TRACING_BACKEND" == "sentry" ]]; then
            echo -e "\n${YELLOW}Sentry Configuration:${NC}"
            prompt_env "SENTRY_DSN" "Enter Sentry DSN" true
        fi

        if [[ "$OTEL_TRACING_BACKEND" == "otlp" ]] || [[ "$OTEL_LOGGING_BACKEND" == *"otlp"* ]]; then
            echo -e "\n${YELLOW}OTLP Configuration:${NC}"
            prompt_env "OTEL_OTLP_ENDPOINT" "Enter OTLP endpoint"
        fi

        if [[ "$OTEL_LOGGING_BACKEND" == *"logtail"* ]]; then
            echo -e "\n${YELLOW}Better Stack / Logtail Configuration:${NC}"
            prompt_env "BETTERSTACK_SOURCE_TOKEN" "Enter Better Stack source token" true
        fi

        # Deploy using render blueprint
        echo -e "\n${GREEN}Deploying via Render Blueprint...${NC}"
        render blueprint launch --yes

        echo -e "\n${GREEN}=== Deployment initiated ===${NC}"
        echo "Check status in the Render dashboard"
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac
