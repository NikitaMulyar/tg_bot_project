import datetime
import sqlalchemy
from sqlalchemy import orm

from .db_session import SqlAlchemyBase


class Big_data(SqlAlchemyBase):
    __tablename__ = 'big_data'
    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True,)
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.id"))
    user = orm.relationship('User')
    start_date = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now)
