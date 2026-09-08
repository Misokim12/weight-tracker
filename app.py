import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# 절대 경로 지정을 통해 instance/weight.db를 확실하게 로드
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'weight.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# 모델 정의
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='athlete')  # 'admin' 또는 'athlete'
    target_weight = db.Column(db.Float, nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class WeightRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    weight_before = db.Column(db.Float, nullable=False)
    weight_after = db.Column(db.Float, nullable=True)
    note = db.Column(db.Text, nullable=True)

    user = db.relationship('User', backref=db.backref('records', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 메인 대시보드
@app.route('/')
@login_required
def index():
    if current_user.role == 'admin':
        return redirect(url_for('admin'))
    records = WeightRecord.query.filter_by(user_id=current_user.id).order_by(WeightRecord.date.desc()).all()
    return render_template('index.html', records=records)

# 체중 기록 추가
@app.route('/athlete/<int:user_id>/records', methods=['POST'])
@login_required
def athlete_records(user_id):
    if current_user.id != user_id and current_user.role != 'admin':
        flash('권한이 없습니다.', 'error')
        return redirect(url_for('index'))
    
    date_str = request.form.get('date')
    weight_before = request.form.get('weight_before')
    weight_after = request.form.get('weight_after')
    note = request.form.get('note')

    if date_str and weight_before:
        record_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        new_record = WeightRecord(
            user_id=user_id,
            date=record_date,
            weight_before=float(weight_before),
            weight_after=float(weight_after) if weight_after else None,
            note=note
        )
        db.session.add(new_record)
        db.session.commit()
        flash('체중 기록이 성공적으로 저장되었습니다.', 'success')
    return redirect(url_for('index'))

# 로그인
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('아이디 또는 비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')

# 로그아웃
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# 비밀번호 변경
@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
            db.session.commit()
            flash('비밀번호가 성공적으로 변경되었습니다.', 'success')
            return redirect(url_for('index'))
    return render_template('change_password.html')

# 관리자 페이지
@app.route('/admin')
@login_required
def admin():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    users = User.query.filter_by(role='athlete').all()
    return render_template('admin.html', users=users)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
