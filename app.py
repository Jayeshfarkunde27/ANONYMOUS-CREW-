from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import re

app = Flask(__name__)
app.secret_key = 'super_secret_key_rentto_2026_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth'

# User Model with Profile Fields
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(150))
    phone = db.Column(db.String(15))
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    permanent_address = db.Column(db.Text)
    temporary_address = db.Column(db.Text)
    role=db.Column(db.String(20),nullable=True)
    properties = db.relationship('Property', backref='owner', lazy=True)

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_type = db.Column(db.String(50), nullable=False)
    rent = db.Column(db.Integer, nullable=False)
    address = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    images = db.Column(db.JSON)  # List of image filenames
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Home Page
@app.route('/')
def home():
    return render_template('index.html')

# Auth Route (Login & Sign Up)
@app.route('/auth', methods=['GET', 'POST'])
def auth():
    mode = request.args.get('mode', 'login')  # 'login' or 'signup'

    if request.method == 'POST':
        action = request.form.get('action')

        # Login
        if action == 'login':
            email = request.form.get('email')
            password = request.form.get('password')

            if not email or not password:
                flash('Email and password are required.', 'error')
                return redirect(url_for('auth', mode='login'))

            user = User.query.filter_by(email=email.lower()).first()
            if user and check_password_hash(user.password, password):
                login_user(user)
                flash('Logged in successfully!', 'success')
                if user.role=='Tenant':
                    return render_template("tenant.html")
                elif user.role=='Room/PG':
                    return render_template("room.html")
            else:
                flash('Invalid email or password.', 'error')
                return redirect(url_for('auth', mode='login'))

        # Sign Up - Step 1: Email + Password
        if action == 'signup_step1':
            email = request.form.get('email')
            password = request.form.get('password')

            if not email or not password:
                flash('Email and password are required.', 'error')
                return redirect(url_for('auth', mode='signup'))

            if User.query.filter_by(email=email.lower()).first():
                flash('Email already registered.', 'error')
                return redirect(url_for('auth', mode='signup'))

            if len(password) < 6:
                flash('Password must be at least 6 characters.', 'error')
                return redirect(url_for('auth', mode='signup'))

            # Store temporary data
            session['signup_email'] = email.lower()
            session['signup_password'] = generate_password_hash(password)
            return redirect(url_for('auth', mode='signup', step='profile'))

        # Sign Up - Step 2: Profile Form
        if action == 'save_profile':
            email = session.get('signup_email')
            hashed_password = session.get('signup_password')

            if not email or not hashed_password:
                flash('Session expired. Please start again.', 'error')
                return redirect(url_for('auth', mode='signup'))

            full_name = request.form.get('full_name')
            phone = request.form.get('phone')
            age = request.form.get('age')
            gender = request.form.get('gender')
            permanent_address = request.form.get('permanent_address')
            temporary_address = request.form.get('temporary_address', '').strip()
            same_address = 'same_address' in request.form

            # Validation
            errors = []
            if not full_name:
                errors.append("Full name is required.")
            if not phone or not re.match(r'^[6-9]\d{9}$', phone):
                errors.append("Valid 10-digit phone number required.")
            if not age or int(age) < 18:
                errors.append("You must be 18 or older.")
            if gender not in ['male', 'female', 'other', 'prefer_not']:
                errors.append("Please select gender.")
            if not permanent_address:
                errors.append("Permanent address is required.")

            # Handle same address
            if same_address:
                temporary_address = permanent_address

            if not temporary_address:
                errors.append("Temporary address is required.")

            if errors:
                for error in errors:
                    flash(error, 'error')
                return redirect(url_for('auth', mode='signup', step='profile'))

            # Create user
            new_user = User(
                email=email,
                password=hashed_password,
                full_name=full_name,
                phone=phone,
                age=int(age),
                gender=gender,
                permanent_address=permanent_address,
                temporary_address=temporary_address
            )
            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            flash('Account created successfully!', 'success')
            session.pop('signup_email', None)
            session.pop('signup_password', None)
            return redirect('/role_selection')

    # GET request - show correct form
    step = request.args.get('step')
    if mode == 'signup' and step == 'profile':
        return render_template('auth/auth.html', mode='signup', show_profile=True)
    return render_template('auth/auth.html', mode=mode)

# Dashboard
@app.route('/role_selection', methods=['GET', 'POST'])
def role_selection():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))

    # If user already has a role, redirect them to the correct dashboard
    if current_user.role == 'Tenant':
        return redirect(url_for('tenant'))
    elif current_user.role == 'Room/PG':
        return redirect(url_for('room'))

    # If POST request: user is selecting role
    if request.method == 'POST':
        role = request.form.get('role')

        if role == 'Tenant':
            current_user.role = 'Tenant'
            db.session.commit()
            flash('Role selected: Tenant 👤', 'success')
            return render_template("tenant.html")

        elif role == 'Room/PG':
            current_user.role = 'Room/PG'
            db.session.commit()
            flash('Role selected: Room/PG ', 'success')
            return render_template("room.html")

        else:
            flash('Please select a valid role.', 'error')

    # If GET request and no role yet → show selection page
    return render_template('role_selection.html')

@app.route("/tenant")
def tenant():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))
    
    if current_user.role != 'Tenant':
        return redirect(url_for('role_selection'))

    properties = Property.query.filter_by(user_id=current_user.id).all()
    return render_template('tenant.html', properties=properties)

@app.route('/add_property', methods=['GET', 'POST'])
def add_property():
    if not current_user.is_authenticated or current_user.role != 'Tenant':
        return redirect(url_for('auth'))

    if request.method == 'POST':
        room_type = request.form.get('room_type')
        rent = request.form.get('rent')
        address = request.form.get('address')
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        images = request.files.getlist('images')

        # Save images and get filenames
        image_filenames = []
        for image in images:
            if image:
                filename = secure_filename(image.filename)
                image.save(f'static/uploads/{filename}')
                image_filenames.append(filename)

        new_property = Property(
            room_type=room_type,
            rent=int(rent),
            address=address,
            latitude=float(latitude),
            longitude=float(longitude),
            images=image_filenames,
            owner=current_user
        )
        db.session.add(new_property)
        db.session.commit()
        flash('Property added successfully!', 'success')
        return redirect(url_for('tenant'))

    return render_template('add_property.html')

@app.route("/room")
def room():
    if not current_user.is_authenticated:
        return redirect('/auth')
    
    if current_user.role !='Room/PG':
        return redirect('/role_selection')

    return render_template("room.html")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)