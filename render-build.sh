#!/bin/bash
set -e

# Create bin folder
mkdir -p bin

# Download tar
curl -L https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar -o stockfish.tar

# Extract tar
tar -xf stockfish.tar

# Move the binary into bin/
mv stockfish/stockfish-ubuntu-x86-64-avx2 bin/stockfish

# Make executable
chmod +x bin/stockfish

# Clean up
rm -rf stockfish stockfish.tar

# Echo confirmation
echo "✅ Stockfish ready at: $(pwd)/bin/stockfish"
echo "✅ Stockfish version:"
bin/stockfish --version
echo "✅ Stockfish build complete!"