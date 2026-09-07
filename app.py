# [코치] 선수 삭제 기능 추가
@app.route("/delete-athlete/<int:user_id>", methods=["POST"])
@login_required
def delete_athlete(user_id):
    if current_user.role != "admin":
        return redirect(url_for("index"))
    
    athlete = User.query.get_or_404(user_id)
    if athlete.role == "admin":
        flash("관리자 계정은 삭제할 수 없습니다.", "error")
        return redirect(url_for("index"))
        
    db.session.delete(athlete)
    db.session.commit()
    flash(f"선수 '{athlete.name}' 계정이 삭제되었습니다.", "success")
    return redirect(url_for("index"))
