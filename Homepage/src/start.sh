#!/bin/bash
cd "$(dirname "$0")"
echo "Suno Community Server starting on http://localhost:8000"
echo "upload_max_filesize: 100M, post_max_size: 120M"
php -S localhost:8000 -c php.ini
