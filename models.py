# models.py
import uuid
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id            = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email         = db.Column(db.String, unique=True, nullable=False)
    name          = db.Column(db.String)
    password_hash = db.Column(db.String)     
    google_id     = db.Column(db.String, unique=True)

    # métodos utilitarios
    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw) -> bool:
        return check_password_hash(self.password_hash or "", raw)
    
class Project(db.Model):
    __tablename__ = 'project'
    id         = db.Column(db.String, primary_key=True)
    name       = db.Column(db.String, nullable=False)
    epw_base64 = db.Column(db.Text, nullable=False) 
    user_id    = db.Column(db.String, db.ForeignKey('user.id'), nullable=False, index=True)
    charts     = db.relationship('Chart', backref='project', cascade='all, delete-orphan')
    
class Chart(db.Model):
    __tablename__ = 'chart'
    id          = db.Column(db.String, primary_key=True)
    project_id  = db.Column(db.String, db.ForeignKey('project.id'), nullable=False, index=True)
    title       = db.Column(db.String, default='')
    description = db.Column(db.Text, default='')
    angle       = db.Column(db.Float, default=0.0)
    temp        = db.Column(db.Float, default=0.0)
    shades      = db.Column(db.JSON, default=[]) 
    hHeight     = db.Column(db.Float, default=1.5)
    hLength     = db.Column(db.Float, default=0.0)
    chkH        = db.Column(db.Boolean, default=False)
    vWidth      = db.Column(db.Float, default=1.5)
    vLength     = db.Column(db.Float, default=0.0)
    vSide       = db.Column(db.String, default='left')
    chkV        = db.Column(db.Boolean, default=False)
    preview     = db.Column(db.Text)


