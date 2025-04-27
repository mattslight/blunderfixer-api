#!/bin/bash
set -e

# Create bin folder
mkdir -p bin
cd bin

# Download Stockfish 17 Linux AVX2 version
curl -L https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar -o stockfish.tar

# Extract
tar -xf stockfish.tar
mv stockfish-ubuntu-x86-64-avx2 stockfish
chmod +x stockfish

# Clean up
rm stockfish.tar

# Echo confirmation
echo "✅ Stockfish binary is located at: $(pwd)/stockfish"

# Go back
cd ..
