import datetime
import sqlalchemy
from sqlalchemy import orm

from .db_session import SqlAlchemyBase


class Big_data(SqlAlchemyBase):
    __tablename__ = 'big_data'
    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.telegram_id"))
    user = orm.relationship('User')
    start_date = sqlalchemy.Column(sqlalchemy.DateTime, default=datetime.datetime.now, primary_key=True)
    type = sqlalchemy.Column(sqlalchemy.String, default="text")
