# MedBot Assistant

MedBot Assistant is a Python-based AI medical support chatbot that uses OpenAI’s Assistant API and Retrieval-Augmented Generation (RAG) to provide personalized health-related responses. The program reads from a local JSON dataset of past medical or injury-related cases and compares them to a user’s current situation to generate relevant guidance. It features a simple desktop interface built with Tkinter and uses threading to keep the UI responsive during API calls.

## Features
- AI-powered health assistant built with Python
- Uses Retrieval-Augmented Generation (RAG) via OpenAI file search
- Reads from a dataset.json file containing past cases and treatments
- Provides personalized responses based on user input
- Simple desktop GUI using Tkinter
- Multithreading to prevent UI freezing during processing

## Technologies Used
- Python
- Tkinter
- OpenAI API (Assistants API)
- File Search / RAG
- JSON dataset storage
- Threading

## How It Works
The user enters a health-related prompt into the application interface. The program uploads a local dataset.json file to the OpenAI Assistant and uses file search to retrieve relevant information. The assistant compares the user’s situation to past cases stored in the dataset and generates a personalized response, which is then displayed in the application window.

## Setup
1. Clone the repository:
git clone https://github.com/Urssopi/Med-Bot-Assistant.git
cd Med-Bot-Assistant

2. Install dependencies:
pip install openai

3. Add your OpenAI API key by replacing:
client = OpenAI(api_key="...use own api...")
with your own key. For better security, use an environment variable.

4. Create a dataset file:
dataset.json
This file should contain medical or injury-related data used for retrieval.

5. Run the program:
python medbot

## Project Structure
Med-Bot-Assistant/
├── medbot          # Main Python program
├── README.md       # Documentation
└── dataset.json    # Local dataset (not included)

## Example Use
User input:
I cut my hand while working on a job site. What should I do?

The assistant analyzes similar cases from the dataset and generates a relevant response.

## Disclaimer
MedBot Assistant is for educational and informational purposes only. It does not provide professional medical advice, diagnosis, or treatment. Always consult a licensed medical professional for serious concerns.

## Future Improvements
- Secure API key with environment variables
- Improve dataset structure and validation
- Add stronger error handling
- Save conversation history
- Enhance UI design
- Add automated tests

## Author
John Russo
