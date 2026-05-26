set -e

echo "Running backend tests..."
(
  cd backend/inflation-classifier

  uv run coverage run -m pytest
  uv run coverage report -m
)

echo "Running frontend tests..."
(
  cd frontend
  npm ci
  npm run test 
)

echo "All tests passed!"
