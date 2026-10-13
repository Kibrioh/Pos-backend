from flask import Flask, jsonify, request 
from config import Config
from extensions import db, migrate, cors
from sqlalchemy import text
from models import User, Category, Product, Sale, SaleItem, StockMovement

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})

    #test connection to postgresql
    @app.get("/api/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))

            return jsonify({
                "status": "success",
                "message": "POS API is running",
                "database": "connected"
            }), 200

        except Exception as e:
            db.session.rollback()

            return jsonify({
                "status": "error",
                "message": "Database connection failed",
                "error": str(e)
            }), 500

    return app

app = create_app()
if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=Config.PORT)
