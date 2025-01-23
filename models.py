from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON
from app import db

class Analysis(db.Model):
    __tablename__ = 'analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    share_id = db.Column(db.String(16), unique=True, nullable=False)
    content = db.Column(db.Text, nullable=False)  # Original text content
    results = db.Column(JSON, nullable=False)     # Analysis results
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
