from sqlalchemy import create_engine, Column, Integer, Sequence, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, Sequence("user_id_seq"), primary_key=True)
    username = Column(String, unique=True)
    authkey = Column(String, nullable=False)

    @staticmethod
    def new(session, username, password):
        unique = session.query(User.username).filter_by(username=username).first() is None
        if unique:
            new_user = User(username=username, authkey=password)
            session.add(new_user)
            return new_user
        return None

    @staticmethod
    def find(session, username):
        return session.query(User).filter_by(username=username).first()


class Thread(Base):
    __tablename__ = "threads"
    id = Column(Integer, Sequence("thread_id_seq"), primary_key=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    text = Column(String, nullable=False)
    lasttime = Column(DateTime, nullable=False)
    messages_count = Column(Integer, nullable=False, default=0)

    @staticmethod
    def new(session, creator, title, text):
        new_thread = Thread(creator_id=creator.id, title=title, text=text,
                            lasttime=datetime.now())
        session.add(new_thread)
        return new_thread

    @staticmethod
    def find(session, thread_id):
        return session.query(Thread).filter_by(id=thread_id).first()

    def delete(self, session):
        session.query(Message).filter(Message.thread_id == self.id).delete()
        session.query(Thread).filter(Thread.id == self.id).delete()


Thread.creator = relationship("User", back_populates="threads")
User.threads = relationship("Thread", order_by=Thread.lasttime, back_populates="creator")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, Sequence("message_id_seq"), primary_key=True)
    thread_id = Column(Integer, ForeignKey("threads.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reply_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    time = Column(DateTime, nullable=False)
    text = Column(String, nullable=False)

    @staticmethod
    def new(session, thread, author, reply, text):
        time = datetime.now()
        reply_id = reply.id if reply is not None else None
        new_message = Message(thread_id=thread.id, author_id=author.id, reply_id=reply_id,
                              time=time, text=text)
        session.add(new_message)
        thread = session.query(Thread).filter(Thread.id == thread.id).first()
        thread.messages_count += 1
        thread.lasttime = time
        return new_message

    @staticmethod
    def find(session, message_id):
        return session.query(Message).filter_by(id=message_id).first()


Message.author = relationship("User", back_populates="messages")
User.messages = relationship("Message", order_by=Message.id, back_populates="author")


Message.thread = relationship("Thread", back_populates="messages")
Thread.messages = relationship("Message", order_by=Message.id, back_populates="thread")


class DbSession:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __call__(self, *args, **kwargs):
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.commit()


class Db:
    @staticmethod
    def read_flyway_config():
        config = dict()
        with open("flyway.conf") as f:
            for line in f.readlines():
                if "=" in line:
                    key, value = line.split("=")
                    config[key] = value.strip()
        return config

    def __init__(self):
        flyway_config = Db.read_flyway_config()
        driver_dialect, address = flyway_config["flyway.url"].split("//")
        driver = driver_dialect.split(":")[1]
        user = flyway_config["flyway.user"]
        password = flyway_config["flyway.password"]
        url = f'{driver}://{user}:{password}@{address}'
        self.engine = create_engine(url, echo=True)
        self.session = DbSession(sessionmaker(bind=self.engine, expire_on_commit=False)())
