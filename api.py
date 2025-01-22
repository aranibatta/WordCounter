from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/count-chars', methods=['POST'])
def count_characters():
    """
    API endpoint to count word occurrences in a string.

    Expected JSON Request Format:
    {
        "text": "string to analyze"
    }

    Returns JSON Response:
    {
        "counts": {
            "word": count,
            ...
        },
        "total_length": integer
    }

    Error Response:
    {
        "error": "error message"
    }
    """
    try:
        # Get JSON data from request
        data = request.get_json()

        # Validate input
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided. Please send JSON with "text" field'}), 400

        input_text = data['text']

        # Validate input type
        if not isinstance(input_text, str):
            return jsonify({'error': 'Text must be a string'}), 400

        # Count word occurrences
        words = input_text.lower().split()
        word_counts = {}
        for word in words:
            # Remove common punctuation from words
            word = word.strip('.,!?()[]{}":;')
            if word:  # Only count non-empty strings
                word_counts[word] = word_counts.get(word, 0) + 1

        # Prepare response
        response = {
            'counts': word_counts,
            'total_length': len(words)
        }

        logging.debug(f"Processed text with {len(words)} words and {len(word_counts)} unique words")

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Add a simple homepage route that serves the static HTML
@app.route('/')
def home():
    return app.send_static_file('index.html')