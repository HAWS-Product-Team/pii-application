#!/usr/bin/env bash
set -euo pipefail

# SCRIPT_DIR makes this script executable from any location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BUILD_DIR="$SCRIPT_DIR/build_lambda"
PACKAGE_NAME="normalizer.zip"
HANDLER="pdf2csv.lambda_handler.handler"
RUNTIME="python3.12"
TARGET_ARCH="arm64"

echo "=== Building Normalizer Lambda Package ==="

# 1. Clean/create the build_lambda directory
echo "Cleaning build directory..."
rm -rf "$BUILD_DIR" "$PACKAGE_NAME"
mkdir -p "$BUILD_DIR"

# 2. In a public.ecr.aws/lambda/python:3.12 Docker container (--platform linux/arm64), 
# install uv and run uv pip install . --target build_lambda
echo "Installing dependencies inside Docker container (Python 3.12, arm64)..."
docker run --rm \
  -v "$SCRIPT_DIR":/var/task \
  --platform linux/arm64 \
  --entrypoint /bin/bash \
  -w /var/task \
  public.ecr.aws/lambda/python:3.12 \
  -c "pip install --no-cache-dir uv && uv pip install --system --target /var/task/build_lambda ."

# 3. Remove tests and __pycache__; strip .so files
echo "Cleaning up build artifacts..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

# Strip .so files if strip command exists
if command -v strip >/dev/null 2>&1; then
  find "$BUILD_DIR" -type f -name "*.so" -exec strip {} + 2>/dev/null || true
fi

# 4. Zip to Normalizer-lambda.zip
echo "Creating deployment ZIP..."
(cd "$BUILD_DIR" && zip -q -r "$SCRIPT_DIR/$PACKAGE_NAME" .)

# Print package name, SHA-256 digest, handler, runtime, and target
if command -v shasum >/dev/null 2>&1; then
  SHA256=$(shasum -a 256 "$PACKAGE_NAME" | awk '{print $1}')
elif command -v sha256sum >/dev/null 2>&1; then
  SHA256=$(sha256sum "$PACKAGE_NAME" | awk '{print $1}')
else
  SHA256="unknown"
fi

echo "=== Build Complete ==="
echo "Package:  $PACKAGE_NAME"
echo "SHA-256:  $SHA256"
echo "Handler:  $HANDLER"
echo "Runtime:  $RUNTIME"
echo "Target:   $TARGET_ARCH"
