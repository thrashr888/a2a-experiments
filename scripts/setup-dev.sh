#!/bin/bash

# A2A Learning Lab - Development Setup Script

set -e

echo "🚀 Setting up A2A Learning Lab development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
uv sync

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p src/web/static

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "⚠️  Docker is not running. Please start Docker and run this script again."
    exit 1
fi

# Start development services (PostgreSQL and Redis)
echo "🐘 Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
if docker-compose ps postgres | grep -q "healthy"; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL failed to start properly"
fi

if docker-compose ps redis | grep -q "healthy"; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis failed to start properly"
fi

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "To start the application:"
echo "  uv run src/main.py"
echo ""
echo "To start with Docker:"
echo "  docker-compose up --build"
echo ""
echo "Web interface will be available at: http://localhost:8080"
echo ""
echo "To stop services:"
echo "  docker-compose down"