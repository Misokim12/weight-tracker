from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

# 1. Flask 앱 객체를 먼저 생성해야 합니다!
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///weight.db'

# 2. DB 및 로그인 매니저 설정 ...
db = SQLAlchemy(app)

# ... (중간 생략: 모델 정의, 기존 라우트 등) ...

# 3. 비밀번호 변경 라우트는 맨 아래쪽에 위치시킵니다.
@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user
    if request.method == "POST":
        current_pw = request.form.get("current_password", "")
        new_pw = request.form.get("new_password", "")
        confirm_pw = request.form.get("confirm_password", "")

        if not user.check_password(current_pw):
            flash("현재 비밀번호가 올바르지 않습니다.", "error")
            return redirect(url_for("change_password"))

        if len(new_pw) < 6:
            flash("새 비밀번호는 6자 이상이어야 합니다.", "error")
            return redirect(url_for("change_password"))

        if new_pw != confirm_pw:
            flash("새 비밀번호 확인이 일치하지 않습니다.", "error")
            return redirect(url_for("change_password"))

        user.set_password(new_pw)
        db.session.commit()
        flash("비밀번호가 성공적으로 변경되었습니다.", "success")
        return redirect(url_for("index"))

    return render_template("change_password.html")
