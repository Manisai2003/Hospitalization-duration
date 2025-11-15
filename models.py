from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    contact = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Precaution(db.Model):
    __tablename__ = 'precautions'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

class Prediction(db.Model):
    __tablename__ = 'predictions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    severity = db.Column(db.String(20), nullable=False)
    comorbidities = db.Column(db.Integer, nullable=False)
    temperature = db.Column(db.String(10), nullable=False)
    blood_pressure = db.Column(db.String(20), nullable=False)
    oxygen_saturation = db.Column(db.String(10), nullable=False)
    predicted_days = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    user = db.relationship('User', backref=db.backref('predictions', lazy=True))

def init_db(app):
    with app.app_context():
        db.create_all()
        
        # Add sample precautions if not exists
        if Precaution.query.count() == 0:
            precautions = [
                "Maintain proper hygiene to prevent hospital-acquired infections.",
                "Follow all prescribed medication schedules without missing doses.",
                "Engage in light physical activity as recommended by your healthcare provider.",
                "Ensure adequate hydration and nutrition during your hospital stay.",
                "Communicate openly with your care team about any concerns or symptoms.",
                "Get sufficient rest to support your body's healing process.",
                "Keep your environment clean and sanitized.",
                "Monitor your vital signs regularly as instructed.",
                "Report any new or worsening symptoms immediately.",
                "Follow discharge instructions carefully to prevent readmission."
            ]
            for text in precautions:
                db.session.add(Precaution(text=text))
            db.session.commit()