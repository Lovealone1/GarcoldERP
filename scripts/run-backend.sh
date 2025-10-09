#!/bin/bash

echo "=============================="
echo " Iniciando Garcold POS Backend"
echo "=============================="

poetry run uvicorn app.main:app --reload --host localhost --port 8000