import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, send_file
from flask_cors import CORS
import logging
import re
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import markdown
import secrets
from shutil import copyfile
from models import Analysis
from app import app, db
import io

# Initialize Flask app
CORS(app)  # Enable CORS for all routes

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def join_hyphenated_words(text):
    """Join words that have been split with hyphens at line breaks."""
    # Pattern for hyphenated words at line breaks
    pattern = r'(\w+)-\n\s*(\w+)'
    # Join the words, removing the hyphen and line break
    return re.sub(pattern, r'\1\2', text)

def handle_bullet_points(text):
    """Properly format bullet points and numbered lists."""
    # Add space after bullet points and numbers
    text = re.sub(r'(^|\n)[\u2022\u2023\u2043\u2219]\s*', r'\1• ', text)
    text = re.sub(r'(^|\n)\d+\.\s*', lambda m: f'\n{m.group().strip()} ', text)
    return text

def clean_extra_whitespace(text):
    """Clean up extra whitespace while preserving intentional line breaks."""
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    # Remove spaces at the beginning of lines
    text = re.sub(r'\n\s+', '\n', text)
    # Remove multiple consecutive empty lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def process_file_content(file):
    filename = secure_filename(file.filename)
    file_extension = filename.rsplit('.', 1)[1].lower()

    # Generate a unique filename to store
    stored_filename = f"{secrets.token_urlsafe(8)}.{file_extension}"
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
    file.save(file_path)

    content = ""
    try:
        if file_extension == 'pdf':
            reader = PdfReader(file_path)
            text_blocks = []

            for page in reader.pages:
                # Extract text from page
                text = page.extract_text()
                text = join_hyphenated_words(text)
                text = handle_bullet_points(text)
                text_blocks.append(text)

            raw_content = '\n\n'.join(text_blocks)
            content = clean_extra_whitespace(raw_content)

        elif file_extension == 'md':
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                html = markdown.markdown(md_content)
                content = re.sub(r'<[^>]+>', ' ', html)
                content = clean_extra_whitespace(content)
        else:  # txt files
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                content = clean_extra_whitespace(content)

        return content, stored_filename
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
        return []

    # Remove special characters but preserve word boundaries
    # Keep apostrophes within words (e.g., "don't")
    cleaned = re.sub(r'[^a-zA-Z\' ]', ' ', word)
    # Remove standalone apostrophes and clean up spaces
    cleaned = re.sub(r'\s\'|\'\s|^\'+|\'+$', ' ', cleaned)
    # Split into words, convert to lowercase, and filter empty strings
    return [w.lower() for w in cleaned.split() if w and len(w) > 1]

@app.route('/api/count-chars', methods=['POST'])
def count_characters():
    try:
        text = None
        stored_filename = None
        original_filename = None

        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                text, stored_filename = process_file_content(file)
                original_filename = secure_filename(file.filename)
            else:
                return jsonify({'error': 'Invalid file type. Allowed types: PDF, MD, TXT'}), 400
        else:
            data = request.get_json()
            if not data or 'text' not in data:
                return jsonify({'error': 'No text or file provided'}), 400
            text = data['text']

        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 404

        # Process text and get word counts
        words = text.split()
        word_counts = {}
        valid_words = []

        for word in words:
            cleaned_words = clean_word(word)
            for cleaned_word in cleaned_words:
                if cleaned_word:
                    valid_words.append(cleaned_word)
                    word_counts[cleaned_word] = word_counts.get(cleaned_word, 0) + 1

        # Prepare response
        results = {
            'counts': word_counts,
            'total_length': len(valid_words)
        }

        # Generate unique share ID and save analysis
        share_id = secrets.token_urlsafe(12)
        analysis = Analysis(
            share_id=share_id,
            content=text,
            results=results,
            stored_filename=stored_filename,
            original_filename=original_filename
        )
        db.session.add(analysis)
        db.session.commit()

        # Add share URL to response
        results['share_url'] = url_for('get_analysis', share_id=share_id, _external=True)

        # Add download URL if there's content
        if stored_filename:
            results['download_url'] = url_for('download_file', share_id=share_id, _external=True)
        else:
            results['download_url'] = url_for('download_text', share_id=share_id, _external=True)

        logging.debug(f"Processed text with {len(valid_words)} words and {len(word_counts)} unique words")
        return jsonify(results), 200

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/download/<share_id>')
def download_file(share_id):
    """Download the original uploaded file"""
    analysis = Analysis.query.filter_by(share_id=share_id).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    if analysis.stored_filename:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], analysis.stored_filename)
        if os.path.exists(file_path):
            return send_file(
                file_path,
                as_attachment=True,
                download_name=analysis.original_filename or analysis.stored_filename
            )
    return jsonify({'error': 'File not found'}), 404

@app.route('/download/text/<share_id>')
def download_text(share_id):
    """Download the text content as a .txt file"""
    analysis = Analysis.query.filter_by(share_id=share_id).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    return send_file(
        io.BytesIO(analysis.content.encode('utf-8')),
        mimetype='text/plain',
        as_attachment=True,
        download_name=f'analysis_{share_id}.txt'
    )

@app.route('/analysis/<share_id>')
def get_analysis(share_id):
    """Retrieve shared analysis results"""
    analysis = Analysis.query.filter_by(share_id=share_id).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    return app.send_static_file('index.html')

@app.route('/api/analysis/<share_id>')
def get_analysis_data(share_id):
    """Get analysis data for the frontend"""
    analysis = Analysis.query.filter_by(share_id=share_id).first()
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    return jsonify({
        'text': analysis.content,
        'results': analysis.results
    }), 200

@app.route('/')
def home():
    return app.send_static_file('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static', 'favicon.ico')