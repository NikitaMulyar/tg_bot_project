import sqlalchemy
from .db_session import SqlAlchemyBase


class User(SqlAlchemyBase):
    __tablename__ = 'users'

    chat_id = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    telegram_id = sqlalchemy.Column(sqlalchemy.String, nullable=True, primary_key=True)
    name = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)

    def __repr__(self):
        return f'<User> {self.id} {self.chat_id} {self.telegram_id} {self.name}'
