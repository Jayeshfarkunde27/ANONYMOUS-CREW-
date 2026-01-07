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
    property_type = db.Column(db.String(50), default='room', nullable=False)  # 'room', 'hostel', 'apartment'
    room_type = db.Column(db.String(50), nullable=False)
    rent = db.Column(db.Integer, nullable=False)
    address = db.Column(db.Text, nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    images = db.Column(db.JSON)  # List of image filenames
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class SeekerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seeker_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    seeker_name = db.Column(db.String(150), nullable=False)
    seeker_phone = db.Column(db.String(20), nullable=True)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(30), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='request_obj', lazy=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('seeker_request.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Wishlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)




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
                if user.role == 'Tenant':
                    return redirect(url_for('tenant'))
                elif user.role == 'Room/PG':
                    return redirect(url_for('room'))
                elif user.role == 'Seeker':
                    return redirect(url_for('seeker'))
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
        role_input = (request.form.get('role') or '').strip()

        # Map various form values to canonical role names used in the DB
        mapping = {
            'seeker': 'Seeker',
            'tenant': 'Tenant',
            'room_owner': 'Tenant',
            'owner': 'Tenant',
            'room/pg': 'Room/PG',
            'room_pg': 'Room/PG'
        }

        canonical = mapping.get(role_input.lower()) if role_input else None

        if canonical:
            current_user.role = canonical
            db.session.commit()
            flash(f'Role selected: {canonical}', 'success')
            # Redirect to the appropriate dashboard
            if canonical == 'Tenant':
                return redirect(url_for('tenant'))
            elif canonical == 'Seeker':
                return redirect(url_for('seeker'))
            else:
                return redirect(url_for('room'))
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

    # Get all properties grouped by type
    rooms = Property.query.filter_by(user_id=current_user.id, property_type='room').all()
    hostels = Property.query.filter_by(user_id=current_user.id, property_type='hostel').all()
    apartments = Property.query.filter_by(user_id=current_user.id, property_type='apartment').all()
    # unread requests count for notification badge
    try:
        unread_count = SeekerRequest.query.filter_by(owner_id=current_user.id, status='new').count()
    except Exception:
        unread_count = 0
    
    return render_template('tenant.html', rooms=rooms, hostels=hostels, apartments=apartments, unread_count=unread_count)


@app.route('/seeker')
def seeker():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))

    if current_user.role != 'Seeker':
        return redirect(url_for('role_selection'))

    # For seeker we may show profile summary and notifications
    try:
        unread_count = SeekerRequest.query.filter_by(seeker_user_id=current_user.id, status='new').count()
    except Exception:
        unread_count = 0

    # Recommended: latest 6 properties
    recommended = Property.query.order_by(Property.created_at.desc()).limit(6).all()

    # wishlist ids for current user
    wishlist_items = Wishlist.query.filter_by(user_id=current_user.id).all()
    wishlist_ids = {w.property_id for w in wishlist_items}

    return render_template('seeker.html', unread_count=unread_count, recommended=recommended, wishlist_ids=wishlist_ids)

@app.route('/add_property', methods=['GET', 'POST'])
def add_property():
    if not current_user.is_authenticated or current_user.role != 'Tenant':
        return redirect(url_for('auth'))

    # Get type from query parameter (GET) or form (POST)
    if request.method == 'POST':
        property_type = request.form.get('property_type', 'room')
    else:
        property_type = request.args.get('type', 'room')

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
            property_type=property_type,  # Save the property type
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

    return render_template('add_property.html', property_type=property_type)

@app.route("/view_property/<int:property_id>")
def view_property(property_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))
    
    property_obj = Property.query.get_or_404(property_id)
    
    # Check if current user owns this property
    if property_obj.user_id != current_user.id:
        flash('You do not have permission to view this property.', 'error')
        return redirect(url_for('tenant'))
    
    return render_template('view_property.html', property=property_obj)

@app.route("/edit_property/<int:property_id>", methods=['GET', 'POST'])
def edit_property(property_id):
    if not current_user.is_authenticated or current_user.role != 'Tenant':
        return redirect(url_for('auth'))
    
    property_obj = Property.query.get_or_404(property_id)
    
    # Check if current user owns this property
    if property_obj.user_id != current_user.id:
        flash('You do not have permission to edit this property.', 'error')
        return redirect(url_for('tenant'))
    
    if request.method == 'POST':
        property_obj.room_type = request.form.get('room_type')
        property_obj.rent = int(request.form.get('rent'))
        property_obj.address = request.form.get('address')
        property_obj.latitude = float(request.form.get('latitude'))
        property_obj.longitude = float(request.form.get('longitude'))
        
        # Handle new images
        images = request.files.getlist('images')
        for image in images:
            if image:
                filename = secure_filename(image.filename)
                image.save(f'static/uploads/{filename}')
                if property_obj.images:
                    property_obj.images.append(filename)
                else:
                    property_obj.images = [filename]
        
        db.session.commit()
        flash('Property updated successfully!', 'success')
        return redirect(url_for('view_property', property_id=property_obj.id))
    
    return render_template('edit_property.html', property=property_obj)

@app.route("/logout")
def logout():
    logout_user()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('home'))

@app.route("/room")
def room():
    if not current_user.is_authenticated:
        return redirect('/auth')
    
    if current_user.role !='Room/PG':
        return redirect('/role_selection')

    return render_template("room.html")


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        age = request.form.get('age')
        gender = request.form.get('gender')
        permanent_address = request.form.get('permanent_address', '').strip()
        temporary_address = request.form.get('temporary_address', '').strip()
        same_address = 'same_address' in request.form

        # Basic validation
        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if phone and not re.match(r'^[6-9]\d{9}$', phone):
            errors.append('Enter a valid 10-digit phone number.')
        if age:
            try:
                age_val = int(age)
                if age_val < 18:
                    errors.append('You must be 18 or older.')
            except ValueError:
                errors.append('Invalid age provided.')
        else:
            age_val = None

        if same_address:
            temporary_address = permanent_address

        if not permanent_address:
            errors.append('Permanent address is required.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('profile.html')

        # Save changes
        current_user.full_name = full_name
        current_user.phone = phone
        current_user.age = age_val
        current_user.gender = gender
        current_user.permanent_address = permanent_address
        current_user.temporary_address = temporary_address
        db.session.commit()
        flash('Profile updated successfully!', 'success')

        # Redirect back to appropriate dashboard
        if current_user.role == 'Tenant':
            return redirect(url_for('tenant'))
        elif current_user.role == 'Room/PG':
            return redirect(url_for('room'))
        else:
            return redirect(url_for('role_selection'))

    return render_template('profile.html')


@app.route('/notifications')
def notifications():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))

    # requests where current user is the owner
    reqs = SeekerRequest.query.filter_by(owner_id=current_user.id).order_by(SeekerRequest.created_at.desc()).all()
    return render_template('notifications.html', requests=reqs)


@app.route('/request_property/<int:property_id>', methods=['GET', 'POST'])
def request_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if request.method == 'POST':
        seeker_name = request.form.get('name') or 'Anonymous'
        seeker_phone = request.form.get('phone')
        message = request.form.get('message')

        newreq = SeekerRequest(
            property_id=prop.id,
            owner_id=prop.user_id,
            seeker_user_id=current_user.id if current_user.is_authenticated else None,
            seeker_name=seeker_name,
            seeker_phone=seeker_phone,
            message=message
        )
        db.session.add(newreq)
        db.session.commit()
        flash('Request sent to owner.', 'success')
        return redirect(url_for('view_property', property_id=prop.id))

    return render_template('request_property.html', property=prop)


@app.route('/search')
def search():
    qtype = request.args.get('type', 'room')
    qtype = qtype.lower()
    # accept synonyms
    if qtype in ('room', 'rooms'):
        ptype = 'room'
    elif qtype in ('hostel', 'pg', 'hostels'):
        ptype = 'hostel'
    elif qtype in ('apartment', 'apartments'):
        ptype = 'apartment'
    else:
        ptype = 'room'

    properties = Property.query.filter_by(property_type=ptype).order_by(Property.created_at.desc()).all()
    return render_template('search_results.html', properties=properties, qtype=ptype)


@app.route('/wishlist')
def wishlist():
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))
    items = Wishlist.query.filter_by(user_id=current_user.id).order_by(Wishlist.created_at.desc()).all()
    props = [Property.query.get(w.property_id) for w in items]
    return render_template('wishlist.html', properties=props)


@app.route('/wishlist/toggle/<int:property_id>', methods=['POST'])
def wishlist_toggle(property_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))

    existing = Wishlist.query.filter_by(user_id=current_user.id, property_id=property_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        flash('Removed from wishlist', 'success')
    else:
        neww = Wishlist(user_id=current_user.id, property_id=property_id)
        db.session.add(neww)
        db.session.commit()
        flash('Added to wishlist', 'success')

    return redirect(request.referrer or url_for('seeker'))


@app.route('/chat/<int:request_id>', methods=['GET', 'POST'])
def chat(request_id):
    if not current_user.is_authenticated:
        return redirect(url_for('auth'))
    req_obj = SeekerRequest.query.get_or_404(request_id)

    # Only owner or seeker may access (owner for now)
    if current_user.id != req_obj.owner_id and current_user.id != req_obj.seeker_user_id:
        flash('You do not have permission to access this chat.', 'error')
        return redirect(url_for('notifications'))

    if request.method == 'POST':
        text = request.form.get('text')
        if text and text.strip():
            msg = Message(request_id=req_obj.id, sender_id=current_user.id, text=text.strip())
            db.session.add(msg)
            db.session.commit()
            return redirect(url_for('chat', request_id=req_obj.id))

    messages = Message.query.filter_by(request_id=req_obj.id).order_by(Message.created_at.asc()).all()
    return render_template('chat.html', req=req_obj, messages=messages)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)