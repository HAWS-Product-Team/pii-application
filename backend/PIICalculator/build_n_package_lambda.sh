#!/bin/bash
set -e

# Configuration
PYTHON_VERSION="3.12"
BUILD_DIR="build_lambda"
PACKAGE_NAME="pii-calculator-lambda.zip"

echo "Building PIICalculation Lambda package..."

# Check for uv
if ! command -v uv &> /dev/null; then
    echo "Error: 'uv' is not installed. Please install it first."
    exit 1
fi

# Clean up
echo "Cleaning up..."
rm -rf "$BUILD_DIR" "$PACKAGE_NAME"
mkdir -p "$BUILD_DIR"

# Install dependencies and the current package
echo "Installing dependencies to $BUILD_DIR..."
# --no-editable ensures we copy the actual files, not links
uv pip install . \
    --target "$BUILD_DIR" \
    --python "$PYTHON_VERSION" \
    --no-cache \
    --upgrade

# Remove unnecessary files to reduce package size
echo "Cleaning up build directory..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} +
find "$BUILD_DIR" -type d -name "*.egg-info" -exec rm -rf {} +

# Create ZIP
echo "Creating ZIP artifact: $PACKAGE_NAME..."
cd "$BUILD_DIR"
zip -q -r "../$PACKAGE_NAME" .
cd ..

echo "------------------------------------------------"
echo "Build Successful!"
echo "Package: $PACKAGE_NAME"
echo "Handler: piicalculator.lambda_handler.handler"
echo "Runtime: Python $PYTHON_VERSION"
echo "------------------------------------------------"
