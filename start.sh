#!/bin/bash

playwright install
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0