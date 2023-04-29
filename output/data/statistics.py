import sqlalchemy
from sqlalchemy import orm
from .db_session import SqlAlchemyBase
from datetime import timedelta


class Statistic(SqlAlchemyBase):
    __tablename__ = 'statistics'

    user_id = sqlalchemy.Column(sqlalchemy.Integer, sqlalchemy.ForeignKey("users.telegram_id"), primary_key=True)
    user = orm.relationship('User')
    total_len = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, default=0)
    total_seconds = sqlalchemy.Column(sqlalchemy.Interval, nullable=True, default=timedelta(seconds=0))
    total_voices = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, default=0)
    total_msgs = sqlalchemy.Column(sqlalchemy.Integer, nullable=True, default=0)

    def __repr__(self):
        return f'<Statistic> {self.user.name} {self.total_len} {self.total_seconds} {self.total_voices} {self.total_msgs}'
