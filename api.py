from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
import re
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import markdown

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_file_content(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    content = ""
    file_ext = filename.rsplit('.', 1)[1].lower()

    try:
        if file_ext == 'pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                content += page.extract_text()
        elif file_ext == 'md':
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                # Convert markdown to plain text by first converting to HTML
                html = markdown.markdown(md_content)
                # Remove HTML tags (simple approach)
                content = html.replace('<p>', '').replace('</p>', '\n')
        else:  # txt files
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

        os.remove(file_path)  # Clean up uploaded file
        return content
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise e

def clean_word(word):
    # Remove URLs
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    if url_pattern.match(word):
        return ''

    # Remove special characters and numbers, keep only letters
    cleaned = re.sub(r'[^a-zA-Z]', '', word)
    return cleaned.lower()

@app.route('/api/count-chars', methods=['POST'])
def count_characters():
    """
    API endpoint to count word occurrences in a string or uploaded file.
    Ignores numbers, special characters, and URLs.
    """
    try:
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                text = process_file_content(file)
            else:
                return jsonify({'error': 'Invalid file type. Allowed types: PDF, MD, TXT'}), 400
        else:
            # Get JSON data from request
            data = request.get_json()
            if not data or 'text' not in data:
                return jsonify({'error': 'No text or file provided'}), 400
            text = data['text']

        # Validate input type
        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 400

        # Split text into words and clean them
        words = text.split()
        word_counts = {}
        valid_words = []

        for word in words:
            cleaned_word = clean_word(word)
            if cleaned_word:  # Only count non-empty strings after cleaning
                valid_words.append(cleaned_word)
                word_counts[cleaned_word] = word_counts.get(cleaned_word, 0) + 1

        # Prepare response
        response = {
            'counts': word_counts,
            'total_length': len(valid_words)
        }

        logging.debug(f"Processed text with {len(valid_words)} words and {len(word_counts)} unique words")

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

# Add a simple homepage route that serves the static HTML
@app.route('/')
def home():
    return app.send_static_file('index.html')