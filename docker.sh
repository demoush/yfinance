#!/bin/bash

# Check if an argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 {build|run|start|stop|bash|status|logs}"
    exit 1
fi

# Load environment variables from .env file
export $(sed 's/#.*//' .env | grep -v '^\s*$' | xargs) 

# Execute the corresponding command based on the argument
case "$1" in
    build)        
        docker build --build-arg BUILD_VERSION=$BUILD_VERSION --platform linux/amd64 -t flask-yfinance:$BUILD_VERSION .
        ;;
    run)
        echo "Starting version: $BUILD_VERSION"

        # Ensure the container is not already running
        if [ "$(docker ps -q -f name=flask-yfinance)" ]; then
            echo "Container 'flask-yfinance' is already running. Stopping it first."
            docker stop flask-yfinance
            docker rm flask-yfinance
        fi

        # Define base directories to mount
        BASE_MOUNTS=(
            ".env:/app/.env"
        )

        # Start building the docker run command
        CMD="docker run --restart always --platform linux/amd64 -p 5000:5000 -d"

        # Add base mounts
        for mount in "${BASE_MOUNTS[@]}"; do
            CMD="$CMD -v \"$(pwd)/$mount\""
        done

    
        # Add environment variables
        CMD="$CMD -e BUILD_VERSION=$BUILD_VERSION"

        # Add container name and image
        CMD="$CMD --name flask-yfinance flask-yfinance:$BUILD_VERSION"

        # Execute the command
        eval $CMD

        ;;
    start)
        echo "Starting version: $BUILD_VERSION"
        docker start flask-yfinance
        ;;

    stop)
        # Check if the container is running before executing bash
        if [ "$(docker ps -q -f name=flask-yfinance)" ]; then
            echo "Container 'flask-yfinance' is already running. Stopping it."
            docker stop flask-yfinance
            docker rm flask-yfinance
        fi
        ;;
    bash)
        # Check if the container is running before executing bash
        if [ "$(docker ps -q -f name=flask-yfinance)" ]; then

            # Load environment variables from .env file
            export $(sed 's/#.*//' .env | grep -v '^\s*$' | xargs)

            docker exec -it flask-yfinance:$BUILD_VERSION bash
        else
            echo "Container 'flask-yfinance' is not running. Please start it first."
            exit 1
        fi
        ;;
    status)
	    docker ps --format "table {{.ID}}\t{{.Image}}\t{{.Status}}"
	;;
    logs)
        docker logs -f flask-yfinance
	;;
    *)
        echo "Invalid option: $1"
        echo "Usage: $0 {build|run|start|bash}"
        exit 1
        ;;
esac