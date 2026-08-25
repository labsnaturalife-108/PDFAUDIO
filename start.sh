#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

PORT=${1:-8088}

echo "=================================================="
echo "🎙️ AudioBook Studio (Fish Audio S2 TTS)"
echo "=================================================="

# Check environment
python3 cli.py check

echo ""
echo "🚀 Запуск веб-студии на http://127.0.0.1:$PORT ..."
python3 cli.py server --port $PORT
