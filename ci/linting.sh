#!/bin/bash

set -e

echo "Running flake8"
flake8 . --ignore=E203,W503,E722,E731 --max-complexity=100 --max-line-length=160

echo "Running pyright"
pyright .

shopt -s globstar
echo "Running black"
black --check .

echo "Running pyflakes"
pyflakes .
