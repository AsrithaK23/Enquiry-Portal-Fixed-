import os
from flask import Flask
from flask_cors import CORS
from database import init_db
from routes.enquiries     import enquiries_bp
from routes.dashboard     import dashboard_bp
from routes.auth          import auth_bp
from routes.chatbot       import chat_bp
from routes.email_webhook import email_bp
from routes.automation    import automation_bp


def create_app():
    app = Flask(__name__)

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "database.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    init_db(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(enquiries_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(email_bp)
    app.register_blueprint(automation_bp)

    @app.route("/")
    def health():
        return {"status": "Smart Enquiry Portal API running"}, 200

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        from models import User
        from database import db
        if User.query.filter_by(role="admin").count() == 0:
            admin = User(name="Admin", email="admin@portal.com", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created: admin@portal.com / admin123")
    print("🚀 Backend running at http://localhost:5000")
    app.run(debug=True, port=5000)
