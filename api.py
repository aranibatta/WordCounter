import os
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for
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
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from statistics import mean

# Download required NLTK data
nltk.download('punkt', quiet=True)

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

def count_syllables(word):
    """Count syllables in a word using a basic heuristic."""
    word = word.lower()
    count = 0
    vowels = 'aeiouy'
    if word[0] in vowels:
        count += 1
    for index in range(1, len(word)):
        if word[index] in vowels and word[index - 1] not in vowels:
            count += 1
    if word.endswith('e'):
        count -= 1
    if count == 0:
        count = 1
    return count

def calculate_complexity_metrics(text):
    """Calculate text complexity metrics for each sentence."""
    sentences = sent_tokenize(text)
    metrics = []

    for sentence in sentences:
        words = word_tokenize(sentence)
        if not words:  # Skip empty sentences
            continue

        # Calculate metrics
        word_lengths = [len(word) for word in words]
        syllable_counts = [count_syllables(word) for word in words]

        # Flesch Reading Ease score for the sentence
        words_per_sentence = len(words)
        syllables_per_word = mean(syllable_counts) if syllable_counts else 0
        flesch_score = 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word

        # Normalize score to 0-100 range
        normalized_flesch = max(0, min(100, flesch_score))

        metrics.append({
            'text': sentence,
            'complexity_score': normalized_flesch,
            'metrics': {
                'word_count': len(words),
                'avg_word_length': mean(word_lengths),
                'avg_syllables': mean(syllable_counts),
                'flesch_score': normalized_flesch
            }
        })

    return metrics

def join_hyphenated_words(text):
    """Join words that have been split with hyphens at line breaks."""
    pattern = r'(\w+)-\n\s*(\w+)'
    return re.sub(pattern, r'\1\2', text)

def handle_bullet_points(text):
    """Properly format bullet points and numbered lists."""
    text = re.sub(r'(^|\n)[\u2022\u2023\u2043\u2219]\s*', r'\1• ', text)
    text = re.sub(r'(^|\n)\d+\.\s*', lambda m: f'\n{m.group().strip()} ', text)
    return text

def clean_extra_whitespace(text):
    """Clean up extra whitespace while preserving intentional line breaks."""
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\s+', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def process_file_content(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    content = ""
    file_ext = filename.rsplit('.', 1)[1].lower()

    try:
        if file_ext == 'pdf':
            reader = PdfReader(file_path)
            text_blocks = []

            for page in reader.pages:
                # Extract text from page
                text = page.extract_text()

                # Process hyphenated words
                text = join_hyphenated_words(text)

                # Handle bullet points and numbered lists
                text = handle_bullet_points(text)

                # Split into lines and preserve intentional breaks
                lines = text.split('\n')
                cleaned_lines = []

                current_paragraph = []
                for line in lines:
                    # Remove excessive spaces while preserving word boundaries
                    cleaned_line = ' '.join(word for word in line.split() if word)

                    if cleaned_line:
                        # Check if this line is a continuation of the previous line
                        if (cleaned_line[0].islower() and current_paragraph
                            and not cleaned_line.startswith(('•', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))):
                            current_paragraph.append(cleaned_line)
                        else:
                            # If we have a paragraph built up, add it to cleaned_lines
                            if current_paragraph:
                                cleaned_lines.append(' '.join(current_paragraph))
                                current_paragraph = []
                            # Start a new paragraph
                            current_paragraph.append(cleaned_line)

                # Add any remaining paragraph
                if current_paragraph:
                    cleaned_lines.append(' '.join(current_paragraph))

                # Join the cleaned lines into a single block of text
                if cleaned_lines:
                    text_blocks.append('\n'.join(cleaned_lines))

            # Join blocks with double newlines for paragraph separation
            raw_content = '\n\n'.join(text_blocks)
            # Final cleanup of whitespace
            content = clean_extra_whitespace(raw_content)

        elif file_ext == 'md':
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                # Convert markdown to plain text by first converting to HTML
                html = markdown.markdown(md_content)
                # Remove HTML tags (simple approach)
                content = re.sub(r'<[^>]+>', ' ', html)
                content = clean_extra_whitespace(content)
        else:  # txt files
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                content = clean_extra_whitespace(content)

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
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                text = process_file_content(file)
            else:
                return jsonify({'error': 'Invalid file type. Allowed types: PDF, MD, TXT'}), 400
        else:
            data = request.get_json()
            if not data or 'text' not in data:
                return jsonify({'error': 'No text or file provided'}), 400
            text = data['text']

        if not isinstance(text, str):
            return jsonify({'error': 'Text must be a string'}), 400

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

        # Calculate complexity metrics
        complexity_analysis = calculate_complexity_metrics(text)

        # Prepare response
        results = {
            'counts': word_counts,
            'total_length': len(valid_words),
            'complexity_analysis': complexity_analysis,
            'overall_metrics': {
                'avg_complexity': mean([s['complexity_score'] for s in complexity_analysis]),
                'sentence_count': len(complexity_analysis),
                'avg_sentence_length': mean([s['metrics']['word_count'] for s in complexity_analysis])
            }
        }

        # Generate unique share ID and save analysis
        share_id = secrets.token_urlsafe(12)
        analysis = Analysis(
            share_id=share_id,
            content=text,
            results=results
        )
        db.session.add(analysis)
        db.session.commit()

        # Add share URL to response
        results['share_url'] = url_for('get_analysis', share_id=share_id, _external=True)

        logging.debug(f"Processed text with {len(valid_words)} words and {len(word_counts)} unique words")
        return jsonify(results), 200

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

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