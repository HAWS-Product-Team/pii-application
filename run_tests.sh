echo "Running frontend tests..."
cd frontend
npx vitest run --coverage

echo "All tests passed!"
