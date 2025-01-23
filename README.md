# Word Counter Application

A Flask-based web application for interactive text analysis, providing comprehensive document parsing and visualization tools. The application can analyze text input or file uploads (PDF, Markdown, or TXT) and generate word frequency visualizations.

## Features

- Text analysis with word frequency counting
- File upload support (PDF, MD, TXT)
- Real-time word frequency visualization using Chart.js
- Interactive API documentation
- Progress bar for file uploads
- Clean, responsive UI
- Support for bullet points and structured text

## API Documentation

### Text Analysis Endpoint

Analyze text content directly using JSON payload:

```bash
curl -X POST http://word-counter.replit.app/api/count-chars \
-H "Content-Type: application/json" \
-d '{
    "text": "Your text here"
}'
```

### File Upload Endpoint

Analyze content from PDF, Markdown, or Text files:

```bash
# Upload and analyze a PDF file
curl -X POST http://word-counter.replit.app/api/count-chars \
-F "file=@sample.pdf"
```

### Response Format

```json
{
    "counts": {
        "word1": 4,
        "word2": 2,
        "word3": 1
    },
    "total_length": 7
}
```

## Local Development

1. Clone the repository
2. Install dependencies:
```bash
pip install flask flask-cors pypdf2 markdown
```

3. Run the development server:
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## Deployment on Replit

1. Create a new Replit project
2. Upload the project files or clone from repository
3. Install required packages using the Replit packager
4. Click "Run" to start the server

The application will be deployed to your Replit subdomain.

## Project Structure

```
├── api.py              # Main API implementation
├── main.py            # Application entry point
├── static/            # Static files
│   └── index.html     # Frontend implementation
└── uploads/           # Temporary file upload directory
```

## Dependencies

- Flask
- Flask-CORS
- PyPDF2
- Markdown
- Chart.js (frontend)
- Bootstrap (frontend)
- Prism.js (frontend)

## Features

### Text Analysis
- Word frequency counting
- Special character handling
- URL filtering
- Case-insensitive analysis

### File Processing
- PDF text extraction
- Markdown parsing
- Plain text processing
- Structured text preservation

### Visualization
- Interactive bar charts
- Real-time updates
- Responsive design
- Color-coded results

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is open source and available under the MIT License.
