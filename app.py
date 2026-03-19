from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from sqlalchemy.exc import IntegrityError
from config import Config
from dotenv import load_dotenv
from extensions import db, login_manager

@login_manager.user_loader
def load_user(user_id):
    from database.models import User
    return User.query.get(int(user_id))

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    from routes.public        import public_bp
    from routes.auth          import auth_bp
    from routes.dashboard     import dashboard_bp
    from routes.subjects      import subjects_bp
    from routes.upload        import upload_bp
    from routes.study_plan    import study_plan_bp
    from routes.assistant     import assistant_bp
    from routes.calendar      import calendar_bp
    from routes.admin         import admin_bp
    from routes.quiz          import quiz_bp
    from routes.analytics     import analytics_bp
    from routes.schedule      import schedule_bp
    from routes.offline       import offline_bp
    from routes.notes         import notes_bp
    from routes.chat          import chat_bp
    from routes.leaderboard   import leaderboard_bp
    from routes.certificates  import certificates_bp
    from routes.notifications import notif_bp
    from routes.profile       import profile_bp
    from routes.attendance    import attendance_bp

    for bp in [public_bp, auth_bp, dashboard_bp, subjects_bp, upload_bp, study_plan_bp,
               assistant_bp, calendar_bp, admin_bp, quiz_bp, analytics_bp,
               schedule_bp, offline_bp, notes_bp, chat_bp,
               leaderboard_bp, certificates_bp, notif_bp, profile_bp, attendance_bp]:
        app.register_blueprint(bp)

    # Context processor — inject unread count into all templates
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        unread = 0
        if current_user.is_authenticated:
            try:
                unread = current_user.unread_notifications
            except Exception:
                pass
        return {'unread_notif_count': unread}

    with app.app_context():
        db.create_all()
        try:
            from database.models import User, ChatRoom
            admin_email = "soumya@admin.com"
            admin_user  = User.query.filter_by(email=admin_email).first()
            if not admin_user:
                admin_user = User(email=admin_email, name="Soumya", role='admin', is_admin=True)
                admin_user.set_password("Soumya@290806")
                db.session.add(admin_user)
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f"Admin setup: {e}")
        try:
            from database.models import ChatRoom, User
            if not ChatRoom.query.filter_by(name="General").first():
                owner = User.query.filter_by(is_admin=True).first()
                if owner:
                    db.session.add(ChatRoom(name="General", created_by=owner.id, is_public=True))
                    db.session.commit()
        except Exception:
            db.session.rollback()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
