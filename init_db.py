import sqlite3
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect("questions.db")
    cursor = conn.cursor()
    
    # Bảng câu hỏi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        answer_a TEXT NOT NULL,
        answer_b TEXT NOT NULL,
        answer_c TEXT NOT NULL,
        answer_d TEXT NOT NULL,
        answer_e TEXT,
        correct_answer TEXT NOT NULL,
        explanation TEXT,
        topic TEXT NOT NULL,
        level TEXT NOT NULL,
        exam_code TEXT
    )
    """)

    # Bảng kết quả thi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        topic TEXT,
        level TEXT,
        exam_code TEXT,
        num_questions INTEGER,
        correct_answers INTEGER,
        duration INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        rewarded INTEGER DEFAULT 0
    )
    """)

    # Bảng người dùng
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT CHECK(role IN ('admin', 'user')),
        stickers INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 1
    )
    """)

    # Bảng phần quà có thể đổi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        sticker_cost INTEGER,
        stock INTEGER
    )
    """)

    # Bảng lịch sử đổi quà
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reward_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reward_id INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Bảng yêu cầu đổi thưởng (Admin xử lý)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS gift_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reward_id INTEGER,
        status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
        request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        response_time TIMESTAMP
    )
    """)
    
    # Cập nhật bảng lessons
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        content TEXT,
        content_type TEXT,
        lesson_topic_id INTEGER,  
        chapter_id INTEGER,  
        level TEXT,
        is_interactive BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lesson_topic_id) REFERENCES lesson_topics(id),
        FOREIGN KEY (chapter_id) REFERENCES chapters(id)
    )
    """)

    # Thêm bảng lesson_topics (chủ đề lớn)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lesson_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        thumbnail_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Thêm bảng chapters (chương/bài)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_topic_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        order_num INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lesson_topic_id) REFERENCES lesson_topics(id)
    )
    """)

    # Thêm bảng interactive_content (nội dung tương tác)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS interactive_content (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lesson_id INTEGER NOT NULL,
        content_type TEXT NOT NULL,  
        content_data TEXT NOT NULL,  
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lesson_id) REFERENCES lessons(id)
    )
    """)

    # Thêm bảng user_learning_progress (theo dõi tiến độ học tập)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_learning_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        lesson_id INTEGER NOT NULL,
        is_completed BOOLEAN DEFAULT 0,
        last_accessed TIMESTAMP,
        progress_percent INTEGER DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (lesson_id) REFERENCES lessons(id),
        UNIQUE(user_id, lesson_id)
    )
    """)
    

    conn.commit()
    conn.close()
    print("✅ Database đã được khởi tạo thành công.")

if __name__ == "__main__":
    init_db()
