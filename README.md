# MedBot Assistant

MedBot Assistant is a Python-based AI medical support chatbot that uses OpenAI’s Assistant API and Retrieval-Augmented Generation (RAG) to provide personalized health-related responses. The program uses a local JSON dataset to compare a user’s current health concern with previous cases and treatments, then generates a response through a simple Tkinter desktop interface.

## Features

- AI-powered health assistant built with Python
- Uses Retrieval-Augmented Generation through OpenAI file search
- Reads from a `dataset.json` file containing past medical or injury-related cases
- Provides personalized responses based on user prompts
- Simple desktop GUI built with Tkinter
- Uses threading to keep the interface responsive while the AI processes a request

## Technologies Used

- Python
- Tkinter
- OpenAI API
- OpenAI Assistants API
- File Search / RAG
- JSON dataset storage
- Threading

## How It Works

1. The user enters a health-related situation into the Tkinter interface.
2. The program uploads a local `dataset.json` file to the OpenAI Assistant.
3. The assistant uses file search to retrieve relevant information from the dataset.
4. The AI compares the user’s prompt with previous cases and treatments.
5. A personalized response is displayed in the application window.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/Urssopi/Med-Bot-Assistant.git
cd Med-Bot-Assistant
