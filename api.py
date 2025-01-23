import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import re
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import markdown
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer

# Download required NLTK data
try:
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('vader_lexicon')

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize NLTK sentiment analyzer
sia = SentimentIntensityAnalyzer()

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

def analyze_sentiment(text):
    """Analyze sentiment of the text using NLTK's VADER sentiment analyzer."""
    sentiment_scores = sia.polarity_scores(text)

    # Interpret the compound score
    compound = sentiment_scores['compound']
    if compound >= 0.05:
        overall_sentiment = 'positive'
    elif compound <= -0.05:
        overall_sentiment = 'negative'
    else:
        overall_sentiment = 'neutral'

    return {
        'scores': sentiment_scores,
        'overall_sentiment': overall_sentiment
    }

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
                text = page.extract_text()
                text = join_hyphenated_words(text)
                text = handle_bullet_points(text)

                lines = text.split('\n')
                cleaned_lines = []
                current_paragraph = []

                for line in lines:
                    cleaned_line = ' '.join(word for word in line.split() if word)

                    if cleaned_line:
                        if (cleaned_line[0].islower() and current_paragraph 
                            and not cleaned_line.startswith(('•', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.'))):
                            current_paragraph.append(cleaned_line)
                        else:
                            if current_paragraph:
                                cleaned_lines.append(' '.join(current_paragraph))
                                current_paragraph = []
                            current_paragraph.append(cleaned_line)

                if current_paragraph:
                    cleaned_lines.append(' '.join(current_paragraph))

                if cleaned_lines:
                    text_blocks.append('\n'.join(cleaned_lines))

            raw_content = '\n\n'.join(text_blocks)
            content = clean_extra_whitespace(raw_content)

        elif file_ext == 'md':
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
                html = markdown.markdown(md_content)
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
    url_pattern = re.compile(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )
    if url_pattern.match(word):
        return []

    cleaned = re.sub(r'[^a-zA-Z\' ]', ' ', word)
    cleaned = re.sub(r'\s\'|\'\s|^\'+|\'+$', ' ', cleaned)
    return [w.lower() for w in cleaned.split() if w and len(w) > 1]

@app.route('/api/count-chars', methods=['POST'])
def count_characters():
    """
    API endpoint to count word occurrences and analyze sentiment in a string or uploaded file.
    """
    try:
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

        # Word frequency analysis
        words = text.split()
        word_counts = {}
        valid_words = []

        for word in words:
            cleaned_words = clean_word(word)
            for cleaned_word in cleaned_words:
                if cleaned_word:
                    valid_words.append(cleaned_word)
                    word_counts[cleaned_word] = word_counts.get(cleaned_word, 0) + 1

        # Sentiment analysis
        sentiment_result = analyze_sentiment(text)

        # Prepare response with both word frequency and sentiment analysis
        response = {
            'counts': word_counts,
            'total_length': len(valid_words),
            'sentiment': {
                'scores': sentiment_result['scores'],
                'overall_sentiment': sentiment_result['overall_sentiment']
            }
        }

        logging.debug(f"Processed text with {len(valid_words)} words and {len(word_counts)} unique words")
        logging.debug(f"Sentiment analysis results: {sentiment_result}")

        return jsonify(response), 200

    except Exception as e:
        logging.error(f"Error processing request: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/')
def home():
    return app.send_static_file('index.html')