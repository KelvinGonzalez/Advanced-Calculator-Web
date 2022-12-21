from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func
from sqlalchemy.ext.mutable import MutableDict, MutableList


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(150))

    variables = db.Column(MutableDict.as_mutable(db.PickleType), default={})
    functions = db.Column(MutableDict.as_mutable(db.PickleType), default={})
    objects = db.Column(MutableDict.as_mutable(db.PickleType), default={})
    shared_objects = db.Column(MutableList.as_mutable(db.PickleType), default=[])
    results = db.Column(MutableList.as_mutable(db.PickleType), default=[])

    collapsed = db.Column(MutableList.as_mutable(db.PickleType), default=[True, True, True, True, True, True, True, True])
