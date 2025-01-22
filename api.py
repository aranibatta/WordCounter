from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/count-chars', methods=['POST'])
def count_characters():
    """
    API endpoint to count character occurrences in a string.
    
    Expected JSON Request Format:
    {
        "text": "string to analyze"
    }
    
    Returns JSON Response:
    {
        "counts": {
            "character": count,
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
            
        # Count character occurrences
        char_counts = {}
        for char in input_text:
            char_counts[char] = char_counts.get(char, 0) + 1
            
        # Prepare response
        response = {
            'counts': char_counts,
            'total_length': len(input_text)
        }
        
        logging.debug(f"Processed string of length {len(input_text)} with {len(char_counts)} unique characters")
        
        return jsonify(response), 200
        
    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Add a simple homepage route that serves the static HTML
@app.route('/')
def home():
    return app.send_static_file('index.html')
