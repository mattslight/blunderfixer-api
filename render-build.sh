#!/bin/bash
set -e

# Create bin folder
mkdir -p bin
cd bin

# Download Stockfish 17 Linux AVX2 version
curl -L https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar -o stockfish.tar

# Extract
tar -xf stockfish.tar

# Move the binary from the extracted folder
mv stockfish-ubuntu-x86-64-avx2/stockfish stockfish
chmod +x stockfish

# Clean up
rm -r stockfish-ubuntu-x86-64-avx2 stockfish.tar

# Echo confirmation
echo "✅ Stockfish binary is located at: $(pwd)/stockfish"

# Go back
cd ..
