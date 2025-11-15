from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Regexp
from models import db, User, Precaution, Prediction, init_db
import numpy as np
from transformers import pipeline
import random
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hospital-stay-prediction-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hospital.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize the database
init_db(app)

# Mock prediction model
def predict_stay_length(patient_data):
    base_days = 3
    if patient_data['age'] > 65:
        base_days += 2
    if patient_data['severity'] == 'high':
        base_days += 3
    elif patient_data['severity'] == 'medium':
        base_days += 1
    if patient_data['comorbidities'] > 2:
        base_days += 2
        
    predicted_days = max(1, base_days + np.random.randint(-1, 3))
    return predicted_days

# Initialize transformer pipeline
try:
    generator = pipeline('text-generation', model='gpt2', max_length=50)
except:
    generator = None

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class RegistrationForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=1, max=120)])
    contact = StringField('Contact Number', validators=[
        DataRequired(), 
        Length(min=10, max=15),
        Regexp(r'^\+?[1-9]\d{1,14}$', message="Invalid phone number format")
    ])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class DetectionForm(FlaskForm):
    age = IntegerField('Age', validators=[DataRequired(), NumberRange(min=1, max=120)])
    severity = SelectField('Condition Severity', 
                          choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], 
                          validators=[DataRequired()])
    comorbidities = IntegerField('Number of Comorbidities', validators=[DataRequired(), NumberRange(min=0, max=10)])
    temperature = StringField('Temperature (°F)', validators=[
        DataRequired(),
        Regexp(r'^\d+(\.\d+)?$', message="Enter a valid temperature (e.g., 98.6)")
    ])
    blood_pressure = StringField('Blood Pressure (e.g., 120/80)', validators=[
        DataRequired(),
        Regexp(r'^\d+/\d+$', message="Enter blood pressure as systolic/diastolic (e.g., 120/80)")
    ])
    oxygen_saturation = StringField('Oxygen Saturation (%)', validators=[
        DataRequired(),
        Regexp(r'^\d+(\.\d+)?$', message="Enter a valid percentage (e.g., 95)")
    ])
    submit = SubmitField('Predict Stay Length')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered. Please login.', 'danger')
            return redirect(url_for('login'))
        
        user = User(
            name=form.name.data,
            email=form.email.data,
            age=form.age.data,
            contact=form.contact.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('main'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/main')
@login_required
def main():
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.timestamp.desc()).limit(5).all()
    return render_template('main.html', user=current_user, predictions=predictions)

@app.route('/detection', methods=['GET', 'POST'])
@login_required
def detection():
    form = DetectionForm()
    if form.validate_on_submit():
        session['detection_data'] = {
            'age': form.age.data,
            'severity': form.severity.data,
            'comorbidities': form.comorbidities.data,
            'temperature': form.temperature.data,
            'blood_pressure': form.blood_pressure.data,
            'oxygen_saturation': form.oxygen_saturation.data
        }
        return redirect(url_for('output'))
    return render_template('detection.html', form=form)

@app.route('/output')
@login_required
def output():
    if 'detection_data' not in session:
        return redirect(url_for('detection'))
    
    patient_data = session['detection_data']
    predicted_days = predict_stay_length(patient_data)
    
    # Save prediction to database
    prediction = Prediction(
        user_id=current_user.id,
        age=patient_data['age'],
        severity=patient_data['severity'],
        comorbidities=patient_data['comorbidities'],
        temperature=patient_data['temperature'],
        blood_pressure=patient_data['blood_pressure'],
        oxygen_saturation=patient_data['oxygen_saturation'],
        predicted_days=predicted_days
    )
    db.session.add(prediction)
    db.session.commit()
    
    # Get precautions from database
    precautions = Precaution.query.all()
    selected_precautions = random.sample(precautions, min(5, len(precautions)))
    
    # Generate suggestions using transformer
    suggestions = []
    if generator:
        try:
            prompt = "Medical advice for reducing hospital stay: "
            generated = generator(prompt, num_return_sequences=5, max_length=60)
            suggestions = [item['generated_text'].replace(prompt, "").strip() for item in generated]
        except:
            suggestions = ["Stay hydrated and follow your treatment plan.",
                          "Communicate openly with your healthcare team.",
                          "Get adequate rest to support your recovery.",
                          "Follow all medication instructions precisely.",
                          "Report any new symptoms to your nurse immediately."]
    else:
        suggestions = ["Stay hydrated and follow your treatment plan.",
                      "Communicate openly with your healthcare team.",
                      "Get adequate rest to support your recovery.",
                      "Follow all medication instructions precisely.",
                      "Report any new symptoms to your nurse immediately."]
    
    return render_template('output.html', 
                         predicted_days=predicted_days,
                         precautions=selected_precautions,
                         suggestions=suggestions,
                         patient_data=patient_data)

if __name__ == '__main__':
    app.run(debug=True)