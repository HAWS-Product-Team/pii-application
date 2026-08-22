#!/bin/bash
# Since modification time isn't normalized before hashing, this script will produce a different
# hash even though the bits are the same.

set -e

# Configuration
PYTHON_VERSION="3.12"
BUILD_DIR="build_lambda"
PACKAGE_NAME="pii-calculator-lambda.zip"

echo "Building PIICalculation Lambda package for Linux ARM64..."

# Check for docker
if ! command -v docker &> /dev/null; then
    echo "Error: 'docker' is not installed. Please install Docker first."
    exit 1
fi

# Clean up
echo "Cleaning up..."
rm -rf "$BUILD_DIR" "$PACKAGE_NAME"
mkdir -p "$BUILD_DIR"

# Build using Amazon Linux 2023 ARM64 image
docker run --rm \
    -v "$PWD:/src" \
    --platform linux/arm64 \
    --entrypoint /bin/bash \
    public.ecr.aws/lambda/python:$PYTHON_VERSION \
    -c "
        pip install uv &&
        cd /src &&
        uv pip install . --target /src/$BUILD_DIR
    "

# Remove unnecessary files
echo "Cleaning up build directory..."
find "$BUILD_DIR" -type d -name "tests" -prune -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$BUILD_DIR" -name "*.so" -exec strip {} \; 2>/dev/null || true


# Create ZIP
echo "Creating ZIP artifact: $PACKAGE_NAME..."
cd "$BUILD_DIR"
zip -q -r "../$PACKAGE_NAME" .
cd ..
DIGEST=$(openssl dgst -binary -sha256 "$PACKAGE_NAME" | openssl base64)

echo "------------------------------------------------"
echo "Build Successful!"
echo "Package: $PACKAGE_NAME"
echo "Digest: $DIGEST"
echo "Handler: piicalculator.lambda_handler.handler"
echo "Runtime: Python $PYTHON_VERSION"
echo "Target: Linux ARM64"
echo "------------------------------------------------"