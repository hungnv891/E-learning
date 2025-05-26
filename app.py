import streamlit as st
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import time
import random
import requests
from gtts import gTTS
import base64
import os
from fpdf import FPDF
import json
import uuid
import re
from io import BytesIO
from xhtml2pdf import pisa
from PIL import Image

st.set_page_config(page_title="Thi trắc nghiệm", layout="wide")

# Áp dụng CSS tùy chỉnh
def local_css():
    st.markdown("""
    <style>
        /* Xóa phần định dạng ô chữ nhật */
        .question-block {
            padding: 0;
            margin-bottom: 0;
            border: none;
            background-color: transparent;
        }
        .question-block:hover {
            background-color: transparent;
        }
        .explanation {
            color: #1a73e8;
            font-style: italic;
        }
        .correct {
            color: green;
            font-weight: bold;
        }
        .incorrect {
            color: red;
            font-weight: bold;
        }
        #progress-counter {
            position: fixed;
            top: 130px;
            right: 30px;
            background-color: #f9f9f9;
            color: #333;
            padding: 10px 16px;
            border-radius: 10px;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.2);
            z-index: 9999;
            font-weight: bold;
        }
        #floating-timer {
            position: fixed;
            top: 80px;
            right: 30px;
            background-color: #f9f9f9;
            color: #333;
            padding: 10px 16px;
            border-radius: 10px;
            box-shadow: 0px 2px 6px rgba(0,0,0,0.2);
            z-index: 9999;
            font-weight: bold;
        }
        .reward-item {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 10px;
            margin: 5px 0;
            background-color: #f9f9f9;
        }
    </style>
    """, unsafe_allow_html=True)

local_css()

# Kết nối SQLite
def get_connection():
    return sqlite3.connect("questions.db")

# Khởi tạo database
def init_db(conn):
    cursor = conn.cursor()
    
    # Tạo bảng câu hỏi
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT,
        level TEXT,
        exam_code TEXT,
        question TEXT,
        answer_a TEXT,
        answer_b TEXT,
        answer_c TEXT,
        answer_d TEXT,
        answer_e TEXT,
        correct_answer TEXT,
        explanation TEXT
    )
    """)
    
    # Tạo bảng kết quả thi
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
    
    # Tạo bảng người dùng
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,  
        stickers INTEGER DEFAULT 0,
        is_approved BOOLEAN DEFAULT 0
    )
    """)
    
    # Tạo bảng phần quà
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        sticker_cost INTEGER,
        stock INTEGER
    )
    """)
    
    # Tạo bảng lịch sử đổi quà
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reward_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reward_id INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Thêm admin va user mặc định nếu chưa có
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      ("admin", "admin123", "admin"))
    cursor.execute("SELECT * FROM users WHERE username = 'danvy'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
            ("danvy", "123456", "user")
        )                  
                      
                      
    # Tạo bảng cho Hangman
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hangman_words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT NOT NULL,
        hint TEXT NOT NULL,
        topic TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        added_by INTEGER,
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(added_by) REFERENCES users(id)
    )
    """)
    
    # Tạo bảng lịch sử chơi Hangman
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hangman_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        word_id INTEGER,
        session_id TEXT,
        result TEXT,  
        wrong_guesses INTEGER,
        date_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(word_id) REFERENCES hangman_words(id)
    )
    """) 

    # Tạo bảng lưu chuỗi thắng dài nhất của mỗi phiên
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS hangman_session_streaks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_id TEXT,
        longest_win_streak INTEGER,
        date_played TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Tạo bảng cho Image game
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guess_image_game (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_path TEXT NOT NULL,
        answer TEXT NOT NULL,
        hint1 TEXT NOT NULL,
        hint2 TEXT NOT NULL,
        hint3 TEXT NOT NULL,
        topic TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        added_by INTEGER,
        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(added_by) REFERENCES users(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,        
        topic TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )    
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS game_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        question_id INTEGER NOT NULL,
        guessed_correctly BOOLEAN NOT NULL,
        score_earned INTEGER NOT NULL,
        hints_used INTEGER DEFAULT 0,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(question_id) REFERENCES guess_image_game(id)
    )
    """)    
    
    conn.commit()

# Hàm đăng nhập
def login(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, stickers FROM users WHERE username = ? AND password = ?", 
                  (username, password))
    user = cursor.fetchone()
    conn.close()
    return user

# Hàm đăng ký
def register(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                      (username, password, "user"))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# Hàm thêm sticker cho user
def add_stickers(conn, user_id, count):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET stickers = stickers + ? WHERE id = ?", (count, user_id))
    conn.commit()

# Hàm lấy danh sách phần quà
def get_rewards(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rewards")
    return cursor.fetchall()

# Hàm đổi quà
def redeem_reward(conn, user_id, reward_id, reduce_sticker=True):
    cursor = conn.cursor()
    
    # Kiểm tra số sticker và stock
    cursor.execute("SELECT sticker_cost, stock FROM rewards WHERE id = ?", (reward_id,))
    reward = cursor.fetchone()
    if not reward:
        return False, "Phần quà không tồn tại"
    
    cost, stock = reward
    if stock <= 0:
        return False, "Hết hàng"
    
    if reduce_sticker:
        cursor.execute("SELECT stickers FROM users WHERE id = ?", (user_id,))
        user_stickers = cursor.fetchone()[0]
        if user_stickers < cost:
            return False, "Không đủ sticker"
        cursor.execute("UPDATE users SET stickers = stickers - ? WHERE id = ?", (cost, user_id))
    
    # Cập nhật kho và lưu lịch sử
    cursor.execute("UPDATE rewards SET stock = stock - 1 WHERE id = ?", (reward_id,))
    cursor.execute("INSERT INTO reward_history (user_id, reward_id) VALUES (?, ?)", (user_id, reward_id))
    conn.commit()
    
    return True, "Đổi quà thành công"

# Hàm thêm phần quà (cho admin)
def add_reward(conn, name, description, sticker_cost, stock):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO rewards (name, description, sticker_cost, stock)
    VALUES (?, ?, ?, ?)
    """, (name, description, sticker_cost, stock))
    conn.commit()

# Hàm xóa phần quà (cho admin)
def delete_reward(conn, reward_id):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))
    conn.commit()

# Hàm lấy lịch sử đổi quà của user
def get_user_reward_history(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT rh.date, r.name, r.description 
    FROM reward_history rh
    JOIN rewards r ON rh.reward_id = r.id
    WHERE rh.user_id = ?
    ORDER BY rh.date DESC
    """, (user_id,))
    return cursor.fetchall()
    
# Lấy danh sách tất cả người dùng
def get_all_users(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users")
    return cursor.fetchall()

# Lấy số sticker hiện tại của người dùng
def get_stickers(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("SELECT stickers FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

# Cập nhật số sticker mới cho người dùng
def update_stickers(conn, user_id, new_sticker_count):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET stickers = ? WHERE id = ?", (new_sticker_count, user_id))
    conn.commit()    
    
#################Game##################
###Hangman####
# Hàm quản lý từ cho Hangman
def add_hangman_word(conn, word, hint, topic, difficulty, added_by):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO hangman_words (word, hint, topic, difficulty, added_by)
    VALUES (?, ?, ?, ?, ?)
    """, (word.upper(), hint, topic, difficulty, added_by))
    conn.commit()

def get_hangman_words(conn, topic=None, difficulty=None):
    cursor = conn.cursor()
    query = "SELECT id, word, hint, topic, difficulty FROM hangman_words"
    params = []
    
    if topic or difficulty:
        query += " WHERE"
        conditions = []
        if topic:
            conditions.append(" topic = ?")
            params.append(topic)
        if difficulty:
            conditions.append(" difficulty = ?")
            params.append(difficulty)
        query += " AND".join(conditions)
    
    cursor.execute(query, params)
    return cursor.fetchall()
    
def get_distinct_difficulties(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT difficulty FROM hangman_words WHERE difficulty IS NOT NULL")
    rows = cursor.fetchall()
    return sorted([row[0] for row in rows if row[0]])    

def get_random_hangman_word(conn, topic=None, difficulty=None):
    words = get_hangman_words(conn, topic, difficulty)
    if words:
        return random.choice(words)
    return None

def save_hangman_result(conn, user_id, word_id, session_id, result, wrong_guesses):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO hangman_history (user_id, word_id, session_id, result, wrong_guesses)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, word_id, session_id, result, wrong_guesses))
    conn.commit()
    
#Hàm lưu chuỗi thắng dài nhất:    
def save_session_streak(conn, user_id, session_id, longest_win_streak):
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO hangman_session_streaks (user_id, session_id, longest_win_streak)
    VALUES (?, ?, ?)
    """, (user_id, session_id, longest_win_streak))
    conn.commit()    

import streamlit as st

def display_hangman_svg(wrong_guesses):
    # Giới hạn wrong_guesses trong phạm vi 0-6
    wrong_guesses = min(max(wrong_guesses, 0), 6)
    
    # Đường dẫn file SVG tương ứng
    filename = f"assets/stage{wrong_guesses}.svg"
    
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            svg_content = f.read()
        st.markdown(svg_content, unsafe_allow_html=True)
    else:
        st.error(f"File {filename} không tồn tại!")


def play_hangman():
    st.title("🧍 Hangman")
    
    conn = get_connection()
    
    # Hiển thị bảng xếp hạng chuỗi thắng dài nhất
    show_longest_win_streak(conn)
    
    difficulty_options = get_distinct_difficulties(conn)
    if not difficulty_options:
        difficulty_options = ["Dễ", "Trung bình", "Khó"]  # fallback nếu DB chưa có dữ liệu
    
    # Phần admin - thêm từ mới
    if st.session_state.user['role'] == 'admin':
        with st.expander("🔧 Công cụ quản lý (Admin Only)"):
            tab1, tab2, tab3 = st.tabs(["Thêm từ thủ công", "Import từ CSV", "Danh sách từ hiện có"])
            
            with tab1:
                with st.form("add_hangman_word"):
                    word = st.text_input("Từ", max_chars=20).strip().upper()
                    hint = st.text_input("Gợi ý")
                    topic = st.text_input("Chủ đề")
                    difficulty = st.selectbox("Độ khó", difficulty_options)
                    
                    if st.form_submit_button("Thêm từ"):
                        if word and hint and topic:
                            add_hangman_word(conn, word, hint, topic, difficulty, st.session_state.user['id'])
                            st.success("Đã thêm từ mới!")
                        else:
                            st.error("Vui lòng điền đầy đủ thông tin")
            
            with tab2:
                st.write("Import nhiều từ cùng lúc từ file CSV")
                st.info("File CSV cần có cấu trúc: word,hint,topic,difficulty")
                
                template = {
                    'word': ['EXAMPLE', 'SAMPLE'],
                    'hint': ['Ví dụ', 'Mẫu'],
                    'topic': ['Chung', 'Chung'],
                    'difficulty': difficulty_options[:2] if len(difficulty_options) >= 2 else difficulty_options
                }
                
                import pandas as pd
                import io
                df_template = pd.DataFrame(template)
                
                csv_buffer = io.StringIO()
                df_template.to_csv(csv_buffer, index=False)
                csv_str = csv_buffer.getvalue()
                
                st.download_button(
                    label="Tải template CSV mẫu",
                    data=csv_str,
                    file_name="hangman_words_template.csv",
                    mime="text/csv"
                )
                
                uploaded_file = st.file_uploader("Chọn file CSV", type="csv")
                if uploaded_file is not None:
                    try:
                        df = pd.read_csv(uploaded_file)

                        required_columns = ['word', 'hint', 'topic', 'difficulty']
                        if not all(col in df.columns for col in required_columns):
                            st.error("File CSV không đúng định dạng. Cần có các cột: word, hint, topic, difficulty")
                        else:
                            df = df.dropna(subset=['word', 'hint', 'topic'])
                            df['word'] = df['word'].astype(str).str.strip().str.upper()
                            df['hint'] = df['hint'].astype(str).str.strip()
                            df['topic'] = df['topic'].astype(str).str.strip()
                            df['difficulty'] = df['difficulty'].astype(str).str.strip()  # Giữ nguyên giá trị difficulty

                            # ==== BẮT ĐẦU: PHẦN KIỂM TRA TRÙNG (ĐƯỢC COMMENT) ====
                            # existing_words = [w[1] for w in get_hangman_words(conn)]
                            # df['is_duplicate'] = df['word'].isin(existing_words)

                            # if df['is_duplicate'].any():
                            #     st.warning("Một số từ đã tồn tại trong hệ thống:")
                            #     st.dataframe(df[df['is_duplicate']][['word', 'hint']])

                            #     overwrite_option = st.radio(
                            #         "Xử lý từ trùng lặp:",
                            #         ["Bỏ qua các từ trùng", "Ghi đè từ trùng"]
                            #     )

                            #     if overwrite_option == "Ghi đè từ trùng":
                            #         cursor = conn.cursor()
                            #         for word in df[df['is_duplicate']]['word']:
                            #             cursor.execute("DELETE FROM hangman_words WHERE word = ?", (word,))
                            #         conn.commit()
                            #         st.info("Đã xóa các từ trùng lặp trước khi thêm mới")

                            # if 'overwrite_option' in locals() and overwrite_option == "Bỏ qua các từ trùng":
                            #     df = df[~df['is_duplicate']]


                            success_count = 0
                            error_rows = []

                            for index, row in df.iterrows():
                                try:
                                    add_hangman_word(
                                        conn, 
                                        row['word'], 
                                        row['hint'], 
                                        row['topic'], 
                                        row['difficulty'],  # Dùng difficulty trực tiếp từ CSV
                                        st.session_state.user['id']
                                    )
                                    success_count += 1
                                except Exception as e:
                                    error_rows.append((index + 2, str(e)))

                            st.success(f"Import thành công {success_count} từ")

                            if error_rows:
                                st.warning(f"Có {len(error_rows)} từ không hợp lệ:")
                                error_df = pd.DataFrame(error_rows, columns=['Dòng', 'Lỗi'])
                                st.dataframe(error_df)

                            st.subheader("Dữ liệu đã import")
                            st.dataframe(df.head())
                    except Exception as e:
                        st.error(f"Lỗi khi đọc file CSV: {str(e)}")
            
            with tab3:
                st.subheader("Danh sách từ trong hệ thống")
                
                col1, col2 = st.columns(2)
                with col1:
                    filter_topic = st.selectbox(
                        "Lọc theo chủ đề", 
                        ["Tất cả"] + list(set([w[3] for w in get_hangman_words(conn)]))
                    )
                with col2:
                    filter_difficulty = st.selectbox(
                        "Lọc theo độ khó",
                        ["Tất cả"] + difficulty_options
                    )
                
                words = get_hangman_words(conn)
                if filter_topic != "Tất cả":
                    words = [w for w in words if w[3] == filter_topic]
                if filter_difficulty != "Tất cả":
                    words = [w for w in words if w[4] == filter_difficulty]
                
                if words:
                    df_words = pd.DataFrame(words, columns=['ID', 'Từ', 'Gợi ý', 'Chủ đề', 'Độ khó'])
                    st.dataframe(df_words.drop(columns=['ID']), height=400)
                    
                    csv = df_words.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Xuất danh sách ra CSV",
                        data=csv,
                        file_name="hangman_words_export.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("Không có từ nào trong hệ thống")
    
    # Khởi tạo session state nếu chưa có
    if 'hangman' not in st.session_state:
        st.session_state.hangman = {
            'game_started': False,
            'word': '',
            'hint': '',
            'guessed_letters': [],
            'wrong_guesses': 0,
            'game_over': False,
            'result': None,
            'current_topic': None,
            'current_difficulty': None,
            'used_words': [],
            'score': {
                'total_words': 0,
                'correct_words': 0,
                'total_wrong_guesses': 0
            },
            'session_id': None,  # ID của phiên chơi
            'current_win_streak': 0,  # Chuỗi thắng hiện tại trong phiên
            'longest_win_streak': 0   # Chuỗi thắng dài nhất trong phiên
        }

    # Hiển thị màn hình tổng kết nếu đã hoàn thành hoặc thua
    if st.session_state.hangman.get('result') in ['completed', 'lose']:
        # Lưu chuỗi thắng dài nhất của phiên
        if st.session_state.hangman['session_id']:
            save_session_streak(
                conn,
                st.session_state.user['id'],
                st.session_state.hangman['session_id'],
                st.session_state.hangman['longest_win_streak']
            )
        show_summary(conn)
        if st.button("Chơi lại"):
            reset_game()
            st.rerun()
        conn.close()
        return

    # Topic and difficulty selection
    col1, col2 = st.columns(2)
    with col1:
        topics = set([word[3] for word in get_hangman_words(conn)])
        selected_topic = st.selectbox("Chọn chủ đề", ["Tất cả"] + sorted(list(topics)))
    with col2:
        difficulties = set([word[4] for word in get_hangman_words(conn)])
        selected_difficulty = st.selectbox("Chọn độ khó", ["Tất cả"] + sorted(list(difficulties)))

    # Start game button
    if st.button("Bắt đầu chơi") and not st.session_state.hangman['game_started']:
        session_id = str(uuid.uuid4())  # Tạo session_id duy nhất
        st.session_state.hangman.update({
            'current_topic': selected_topic if selected_topic != "Tất cả" else None,
            'current_difficulty': selected_difficulty if selected_difficulty != "Tất cả" else None,
            'used_words': [],
            'score': {'total_words': 0, 'correct_words': 0, 'total_wrong_guesses': 0},
            'session_id': session_id,
            'current_win_streak': 0,
            'longest_win_streak': 0
        })
        start_new_word(conn)        
    
  

    # Game display
    # Game display
    if st.session_state.hangman['game_started'] and not st.session_state.hangman['game_over']:
        word = st.session_state.hangman['word']
        hint = st.session_state.hangman['hint']
        guessed_letters = st.session_state.hangman['guessed_letters']
        wrong_guesses = st.session_state.hangman['wrong_guesses']
        
        # Function to display the word as square cells
        def display_hangman_word(word, guessed_letters):
            display = ""
            for char in word:
                if char in guessed_letters or not char.isalpha():
                    display += f"<div class='cell'>{char.upper()}</div>"
                else:
                    display += "<div class='cell'>&nbsp;</div>"

            st.markdown("""
            <style>
            .cell {
                display: inline-block;
                width: 40px;
                height: 40px;
                border: 2px solid #007ACC;
                margin: 4px;
                text-align: center;
                line-height: 40px;
                font-size: 24px;
                font-weight: bold;
                border-radius: 8px;
                background-color: #e0f0ff;
            }
            
            @media (max-width: 768px) {
                .cell {
                    width: 30px;
                    height: 30px;
                    line-height: 30px;
                    font-size: 18px;
                }
            }
            </style>
            """, unsafe_allow_html=True)

            st.markdown(f"<div style='display: flex; flex-wrap: wrap; '>{display}</div>", unsafe_allow_html=True)
            
        st.write(f"Current win streak: {st.session_state.hangman['current_win_streak']}")
        st.write(f"Longest win streak: {st.session_state.hangman['longest_win_streak']}")
        st.write(f"Wrong guesses: {wrong_guesses}/6")
        st.subheader(f"Hint: {hint}")
        display_hangman_svg(wrong_guesses)
        
        # Display the word using the new function
        display_hangman_word(word, guessed_letters)        
        
        # Display used letters
        if guessed_letters:
            used_letters = [letter for letter in guessed_letters if letter not in word]
            correct_letters = [letter for letter in guessed_letters if letter in word]
            
            if used_letters:
                st.markdown(
                    f"<p style='font-size:16px; color:#b20000; background-color:#ffe6e6; padding:8px; border-radius:5px; margin-bottom:4px;'>"
                    f"Wrong letters: {', '.join(used_letters)}</p>",
                    unsafe_allow_html=True
                )
            if correct_letters:
                st.markdown(
                    f"<p style='font-size:16px; color:#006600; background-color:#e6ffe6; padding:8px; border-radius:5px; margin-bottom:0px;'>"
                    f"Correct letters: {', '.join(correct_letters)}</p>",
                    unsafe_allow_html=True
                )

        
        # Responsive input method
        st.markdown("""
        <style>
        @media (min-width: 769px) {
            .mobile-input { display: none; }
        }
        @media (max-width: 768px) {
            .desktop-keyboard { display: none; }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Mobile input (shown only on mobile)
        with st.container():
            st.markdown('<div class="mobile-input">', unsafe_allow_html=True)
            st.subheader("Enter a letter")
            col1, col2 = st.columns([3, 1])
            with col1:
                user_input = st.text_input("Type a letter", max_chars=1, key="mobile_letter_input", 
                                         label_visibility="collapsed")
            with col2:
                if st.button("Submit", key="mobile_submit"):
                    if user_input and user_input.isalpha():
                        letter = user_input.upper()
                        if letter not in guessed_letters:
                            st.session_state.hangman['guessed_letters'].append(letter)
                            if letter not in word:
                                st.session_state.hangman['wrong_guesses'] += 1
                            st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Desktop keyboard (shown only on desktop)
        with st.container():
            st.markdown('<div class="desktop-keyboard">', unsafe_allow_html=True)
            st.subheader("Select a letter")
            alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            cols = 14
            rows = [alphabet[i:i+cols] for i in range(0, len(alphabet), cols)]
            
            for row in rows:
                columns = st.columns(cols)
                for i, letter in enumerate(row):
                    with columns[i]:
                        if letter in guessed_letters:
                            st.button(letter, disabled=True, key=f"letter_{letter}")
                        else:
                            if st.button(letter, key=f"letter_{letter}"):
                                st.session_state.hangman['guessed_letters'].append(letter)
                                if letter not in word:
                                    st.session_state.hangman['wrong_guesses'] += 1
                                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)  
        
        # Nút chơi lại ngay trong màn hình
        if st.button("🔄 Đổi từ"):
            # Đặt lại thông tin cần thiết cho từ mới
            st.session_state.hangman.update({
                'word': '',
                'hint': '',
                'guessed_letters': [],
                'wrong_guesses': 0,
                'game_over': False,
                'result': None
            })
            start_new_word(conn)  # Hàm này đã sử dụng current_topic và current_difficulty trong session
            st.rerun()
            
        # Nút "Chọn chủ đề khác"
        if st.button("🚀 Chủ đề khác"):
            st.session_state.hangman.update({
                'game_started': False,
                'word': '',
                'hint': '',
                'guessed_letters': [],
                'wrong_guesses': 0,
                'game_over': False,
                'result': None,
                'current_topic': None,
                'current_difficulty': None,
                'used_words': [],
                'score': {
                    'total_words': 0,
                    'correct_words': 0,
                    'total_wrong_guesses': 0
                },
                'session_id': None,
                'current_win_streak': 0,
                'longest_win_streak': 0
            })
            st.rerun()    
            
        
        # Check win/lose conditions
        word_guessed = all(letter in guessed_letters or not letter.isalpha() for letter in word)
        if word_guessed:
            st.session_state.hangman['score']['total_words'] += 1
            st.session_state.hangman['score']['correct_words'] += 1
            st.session_state.hangman['score']['total_wrong_guesses'] += st.session_state.hangman['wrong_guesses']
            st.session_state.hangman['current_win_streak'] += 1
            st.session_state.hangman['longest_win_streak'] = max(
                st.session_state.hangman['longest_win_streak'],
                st.session_state.hangman['current_win_streak']
            )
            
            save_hangman_result(
                conn, 
                st.session_state.user['id'], 
                st.session_state.hangman['word_id'], 
                st.session_state.hangman['session_id'],
                'win', 
                st.session_state.hangman['wrong_guesses']
            )
            st.balloons()
            st.success(f"Congratulations! You guessed the word: {word}")
            
            st.session_state.hangman['used_words'].append(st.session_state.hangman['word_id'])
            
            if has_available_words(conn):
                time.sleep(2)
                start_new_word(conn)
                st.rerun()
            else:
                st.session_state.hangman.update({
                    'game_over': True,
                    'result': 'completed'
                })
                st.rerun()
                
        elif st.session_state.hangman['wrong_guesses'] >= 6:
            st.session_state.hangman['wrong_guesses'] = 6
            st.session_state.hangman['score']['total_words'] += 1
            st.session_state.hangman['score']['total_wrong_guesses'] += st.session_state.hangman['wrong_guesses']
            st.session_state.hangman['current_win_streak'] = 0  # Reset win streak
            
            save_hangman_result(
                conn, 
                st.session_state.user['id'], 
                st.session_state.hangman['word_id'], 
                st.session_state.hangman['session_id'],
                'lose', 
                st.session_state.hangman['wrong_guesses']
            )
            st.session_state.hangman.update({
                'game_over': True,
                'result': 'lose',
                'word': word
            })
            st.rerun()

    conn.close()

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def show_longest_win_streak(conn):
    st.markdown("### 🏆 Bảng xếp hạng - Chuỗi thắng dài nhất")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.user_id, u.username, MAX(s.longest_win_streak) as max_streak
        FROM hangman_session_streaks s
        JOIN users u ON s.user_id = u.id
        GROUP BY s.user_id, u.username
        ORDER BY max_streak DESC
    """)
    streak_list = cursor.fetchall()
    
    if not streak_list:
        st.info("Chưa có dữ liệu thành tích.")
        return
    
    # Tạo dataframe
    df = pd.DataFrame(streak_list, columns=['User ID', 'Người chơi', 'Chuỗi thắng dài nhất'])
    df = df[['Người chơi', 'Chuỗi thắng dài nhất']]
    df.index = df.index + 1
    df.index.name = 'Thứ tự'
    
    # Thêm biểu tượng xếp hạng
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    df['Xếp hạng'] = [medals.get(i, "") for i in df.index]
    df = df[['Xếp hạng', 'Người chơi', 'Chuỗi thắng dài nhất']]

    # Hàm tô màu nền top 3
    def style_ranking(row):
        colors = {1: '#FFD700', 2: '#C0C0C0', 3: '#CD7F32'}  # vàng, bạc, đồng
        color = colors.get(row.name, '')
        return ['background-color: ' + color if color else '' for _ in row]

    # Apply style: căn giữa, tô màu header và top 3
    styled_df = (
        df.style
        .apply(style_ranking, axis=1)
        .set_properties(**{
            'text-align': 'center',
            'vertical-align': 'middle'
        })
        .set_table_styles([
            {
                'selector': 'th',
                'props': [('text-align', 'center'), ('background-color', '#f0f2f6'), ('font-weight', 'bold')]
            },
            {
                'selector': 'td',
                'props': [('text-align', 'center'), ('vertical-align', 'middle')]
            }
        ])
    )

    # Hiển thị bảng với chiều cao hợp lý
    st.dataframe(styled_df, height=200)  

def show_summary(conn):
    """Hiển thị màn hình tổng kết cho cả trường hợp thắng và thua"""
    score = st.session_state.hangman['score']
    result = st.session_state.hangman['result']
    correct_word = st.session_state.hangman.get('word')  # Lấy từ đúng
    
    if result == 'completed':
        st.balloons()
        st.title("🎉 Hoàn thành chủ đề!")
    else:  # result == 'lose'
        st.title("😢 Game Over")
        if correct_word:
            st.error(f"Từ đúng là: **{correct_word}**")
    
    st.subheader(f"Chủ đề: {st.session_state.hangman['current_topic'] or 'Tất cả'}")
    st.subheader(f"Độ khó: {st.session_state.hangman['current_difficulty'] or 'Tất cả'}")
    
    # Thống kê
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tổng số từ", score['total_words'])
    with col2:
        st.metric("Đoán đúng", score['correct_words'])
    with col3:
        success_rate = round((score['correct_words']/score['total_words'])*100) if score['total_words'] > 0 else 0
        st.metric("Tỷ lệ thành công", f"{success_rate}%")
    
    st.write("---")
    st.subheader("Thống kê chi tiết")
    st.write(f"- Tổng số lần đoán sai: {score['total_wrong_guesses']}")
    st.write(f"- Số từ chưa đoán được: {score['total_words'] - score['correct_words']}")

    # Kiểm tra nếu người chơi giữ chuỗi thắng dài nhất toàn hệ thống
    longest_streak = st.session_state.hangman.get('longest_win_streak', 0)
    if longest_streak > 0:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(longest_win_streak) FROM hangman_session_streaks")
        max_record = cursor.fetchone()[0] or 0

        if longest_streak >= max_record:
            st.success("🎉")
            st.markdown(
                "<div style='font-size: 24px; font-weight: bold; color: green;'>👑 Bạn đang giữ chuỗi thắng dài nhất hiện tại! Chúc mừng!</div>",
                unsafe_allow_html=True
            )


    # Phần thưởng (chỉ khi hoàn thành chủ đề với tỷ lệ >= 80%)
    if result == 'completed' and score['total_words'] > 0 and score['correct_words']/score['total_words'] >= 0.8:
        reward = min(10, max(5, score['correct_words']))
        add_stickers(conn, st.session_state.user['id'], reward)
        st.success(f"🏆 Bạn nhận được {reward} sticker thưởng!")

    


def has_available_words(conn):
    """Check if there are available words left"""
    used_ids = st.session_state.hangman['used_words']
    all_words = get_hangman_words(
        conn,
        st.session_state.hangman['current_topic'],
        st.session_state.hangman['current_difficulty']
    )
    return any(word[0] not in used_ids for word in all_words)

def start_new_word(conn):
    """Start a new word in current topic/difficulty"""
    available_words = get_hangman_words(
        conn,
        st.session_state.hangman['current_topic'],
        st.session_state.hangman['current_difficulty']
    )
    available_words = [word for word in available_words if word[0] not in st.session_state.hangman['used_words']]
    
    if available_words:
        word_id, word, hint, topic, difficulty = random.choice(available_words)
        st.session_state.hangman.update({
            'game_started': True,
            'word': word.upper(),
            'hint': hint,
            'word_id': word_id,
            'guessed_letters': [],
            'wrong_guesses': 0,
            'game_over': False,
            'result': None
        })
    else:
        # No more words, show summary
        st.session_state.hangman.update({
            'game_over': True,
            'result': 'completed'
        })

def reset_game():
    """Reset game state"""
    st.session_state.hangman = {
        'game_started': False,
        'word': '',
        'hint': '',
        'guessed_letters': [],
        'wrong_guesses': 0,
        'game_over': False,
        'result': None,
        'current_topic': None,
        'current_difficulty': None,
        'used_words': [],
        'score': {
            'total_words': 0,
            'correct_words': 0,
            'total_wrong_guesses': 0
        },
        'session_id': None,
        'current_win_streak': 0,
        'longest_win_streak': 0
    }

def game_section():
    st.title("🎮 Trò chơi")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Hangman", "Crossword Puzzle", "Matrix Word", "Guess Image"])
    
    with tab1:
        play_hangman()
    
    with tab2:
        # Thêm chức năng Crossword Puzzle từ code trước đó
        if 'user' not in st.session_state:
            st.warning("Vui lòng đăng nhập trước khi chơi Crossword Puzzle.")
        else:
            # Khởi tạo session state
            if 'crossword' not in st.session_state:
                st.session_state.crossword = {
                    'screen': 'setup',
                    'submitted': False,
                    'grid': None,
                    'words': [],
                    'answers': {},
                    'topic': None,
                    'difficulty': None,
                    'start_time': None,
                    'end_time': None
                }

            crossword = st.session_state.crossword
            screen = crossword['screen']
            conn = get_connection()

            def generate_crossword(words):
                grid_size = max(len(word['word']) for word in words) + 4
                grid = [[' ' for _ in range(grid_size)] for _ in range(grid_size)]
                placed_words = []

                if words:
                    first = words[0]
                    word_text = first['word'].upper()
                    row = grid_size // 2
                    col = (grid_size - len(word_text)) // 2
                    for i, ch in enumerate(word_text):
                        grid[row][col + i] = ch
                    placed_words.append({'word': word_text, 'hint': first['hint'], 'row': row, 'col': col, 'direction': 'across'})

                for word_data in words[1:]:
                    word_text = word_data['word'].upper()
                    placed = False
                    for placed_word in placed_words:
                        for i, letter in enumerate(word_text):
                            for j, placed_letter in enumerate(placed_word['word']):
                                if letter == placed_letter:
                                    if placed_word['direction'] == 'across':
                                        new_row = placed_word['row'] - i
                                        new_col = placed_word['col'] + j
                                        if 0 <= new_row <= grid_size - len(word_text) and 0 <= new_col < grid_size:
                                            if all(grid[new_row + k][new_col] in [' ', word_text[k]] for k in range(len(word_text))):
                                                for k in range(len(word_text)):
                                                    grid[new_row + k][new_col] = word_text[k]
                                                placed_words.append({'word': word_text, 'hint': word_data['hint'], 'row': new_row, 'col': new_col, 'direction': 'down'})
                                                placed = True
                                                break
                                    else:
                                        new_row = placed_word['row'] + j
                                        new_col = placed_word['col'] - i
                                        if 0 <= new_col <= grid_size - len(word_text) and 0 <= new_row < grid_size:
                                            if all(grid[new_row][new_col + k] in [' ', word_text[k]] for k in range(len(word_text))):
                                                for k in range(len(word_text)):
                                                    grid[new_row][new_col + k] = word_text[k]
                                                placed_words.append({'word': word_text, 'hint': word_data['hint'], 'row': new_row, 'col': new_col, 'direction': 'across'})
                                                placed = True
                                                break
                            if placed: break
                        if placed: break
                return grid, placed_words

            if screen == 'setup':
                st.title("🧩 Crossword Puzzle")
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT topic FROM hangman_words")
                topics = [row[0] for row in cursor.fetchall()]
                selected_topic = st.selectbox("📚 Chọn chủ đề", topics, key="crossword_topic")

                cursor.execute("SELECT DISTINCT difficulty FROM hangman_words")
                difficulties = [row[0] for row in cursor.fetchall()]
                selected_difficulty = st.selectbox("🎯 Chọn độ khó", difficulties, key="crossword_difficulty")

                if st.button("🚀 Bắt đầu chơi", key="start_crossword"):
                    cursor.execute("""
                        SELECT word, hint FROM hangman_words
                        WHERE topic = ? AND difficulty = ?
                        ORDER BY RANDOM() LIMIT 10
                    """, (selected_topic, selected_difficulty))
                    words_data = [{'word': row[0], 'hint': row[1]} for row in cursor.fetchall()]

                    if len(words_data) < 5:
                        st.error("Không đủ từ cho chủ đề và độ khó này!")
                    else:
                        grid, placed_words = generate_crossword(words_data)
                        crossword.update({
                            'grid': grid,
                            'words': placed_words,
                            'answers': {w['word']: '' for w in placed_words},
                            'topic': selected_topic,
                            'difficulty': selected_difficulty,
                            'start_time': datetime.now(),
                            'screen': 'game',
                            'submitted': False
                        })
                        st.rerun()

            if screen == 'game' and not crossword.get('submitted', False):
                st.subheader("🧩 Crossword Puzzle")
                st.markdown(f"**Chủ đề:** {crossword['topic']} | **Độ khó:** {crossword['difficulty']}")

                # Thêm CSS tùy chỉnh để đổi màu ô input
                st.markdown("""
                <style>
                /* Định dạng cho ô input */
                input[type="text"] {
                    background-color: #e6f3ff !important; /* Màu nền xanh nhạt */
                    color: #000000 !important; /* Màu chữ đen */
                    border: 1px solid #4CAF50 !important; /* Viền xanh */
                    text-align: center !important; /* Căn giữa chữ */
                    font-size: 18px !important; /* Kích thước chữ */
                    padding: 0px !important; /* Khoảng cách bên trong */
                    border-radius: 0 !important; /* Góc vuông, không bo tròn */
                    box-sizing: border-box !important; /* Đảm bảo viền được tính toán chính xác */

                }
                /* Định dạng placeholder */
                input[type="text"]::placeholder {
                    color: #000000 !important; /* Màu chữ placeholder */
                    font-size: 16px !important; /* Kích thước chữ placeholder */
                    padding-left: 3px !important; /* 👈 Thêm dòng này để lùi chữ vào bên trái */
                    text-align: left !important;   /* 👈 Đảm bảo placeholder căn trái */
                }
                </style>
            """, unsafe_allow_html=True)

                grid = crossword['grid']
                words = crossword['words']
                answers = crossword['answers']
                grid_size = len(grid)

                # Tạo dict đánh số từ
                word_numbers = {word['word']: idx for idx, word in enumerate(words, 1)}

                user_inputs = {}

                for i in range(grid_size):
                    cols = st.columns(grid_size)
                    for j in range(grid_size):
                        letter = grid[i][j]
                        cell_key = f"cell_{i}_{j}"
                        word_start = None
                        placeholder = ""

                        word_starts = [word for word in words if word['row'] == i and word['col'] == j]
                        placeholder = " ".join(str(word_numbers[word['word']]) for word in word_starts)

                        if letter == ' ':
                            cols[j].markdown(" ")  # Ô trống
                            continue

                        if word_starts:
                            word_start = word_starts[0]  # Lấy từ đầu tiên (nếu có nhiều từ bắt đầu tại ô này)
                            placeholder = f"{word_numbers[word_start['word']]}"  # Số gợi ý làm placeholder

                        input_val = cols[j].text_input(
                            label="",  # Không dùng label để tránh ảnh hưởng chiều cao
                            max_chars=1,
                            key=cell_key,
                            label_visibility="collapsed",
                            placeholder=placeholder  # Gợi ý nhỏ hiển thị trong ô
                        ).upper()

                        user_inputs[(i, j)] = input_val

                        if word_start:
                            direction = word_start['direction']
                            pos = j - word_start['col'] if direction == 'across' else i - word_start['row']
                            if word_start['word'] not in answers:
                                answers[word_start['word']] = [''] * len(word_start['word'])
                            if 0 <= pos < len(answers[word_start['word']]):
                                answers[word_start['word']][pos] = input_val
                                
                # Sau vòng for thu thập user_inputs
                st.session_state['crossword_user_inputs'] = user_inputs                

                # Cập nhật chuỗi hoàn chỉnh cho từng từ
                for word in answers:
                    crossword['answers'][word] = ''.join(answers[word])

                def generate_crossword_and_hints_html(grid, words, word_numbers):
                    html = """
                    <style>
                    .crossword-container {
                        display: flex;
                        flex-direction: row;
                        justify-content: center;   /* căn giữa toàn bộ container theo chiều ngang */
                        align-items: flex-start;   /* canh trên cùng theo chiều dọc */
                        gap: 40px;
                        font-family: Arial, sans-serif;
                        margin: 0 auto;
                        max-width: 900px;          /* giới hạn chiều rộng */
                    }
                    .crossword-container table {
                        border-collapse: collapse;
                        box-shadow: 0 0 5px rgba(0,0,0,0.15);
                    }
                    .crossword-container td {
                        width: 45px;
                        height: 45px;
                        text-align: center;
                        border: 1px solid black;
                        font-size: 14px;
                        color: #888888;
                        vertical-align: middle;
                        user-select: none;
                    }
                    .crossword-container .black-cell {
                        background-color: #000;
                    }
                    .hint-section {
                        max-width: 320px;
                        font-size: 18px;
                        line-height: 1.5;
                    }
                    .hint-section h4 {
                        margin-bottom: 8px;
                        font-size: 20px;
                        text-align: center;
                    }
                    .hint-item {
                        margin-bottom: 10px;
                    }
                    </style>

                    <div class="crossword-container">
                        <table>
                    """

                    for i in range(len(grid)):
                        html += "<tr>"
                        for j in range(len(grid[0])):
                            cell = grid[i][j]
                            is_black = (cell == ' ')
                            number = ""

                            for word in words:
                                if word['row'] == i and word['col'] == j:
                                    number = str(word_numbers[word['word']])
                                    break

                            if is_black:
                                html += "<td class='black-cell'></td>"
                            else:
                                html += f"<td>{number}</td>" if number else "<td></td>"
                        html += "</tr>"

                    html += "</table>"

                    # Phần gợi ý bên phải
                    html += """
                        <div class="hint-section">
                            <h4>📌 Gợi ý</h4>
                            <ol>
                    """
                    for word in words:
                        number = word_numbers[word['word']]
                        hint_html = word['hint']  # Giữ nguyên HTML (ví dụ có ảnh)
                        html += f"<li class='hint-item'><b>{word['direction'].capitalize()}</b>: {hint_html}</li>"
                    html += """
                            </ol>
                        </div>
                    </div>
                    """

                    return html

                # --- Phần hiển thị ---
                grid = crossword['grid']
                words = crossword['words']
                word_numbers = {word['word']: idx for idx, word in enumerate(words, 1)}

                html_content = generate_crossword_and_hints_html(grid, words, word_numbers)

                # Hiển thị luôn trên app
                st.markdown(html_content, unsafe_allow_html=True)

                # Nút in PDF                
                pdf_buffer = BytesIO()
                pisa_status = pisa.CreatePDF(src=html_content, dest=pdf_buffer)
                pdf_buffer.seek(0)

                if pisa_status.err:
                    st.error("Lỗi tạo PDF. Vui lòng thử lại.")
                else:
                    st.download_button(
                        label="📥 Tải PDF ô chữ",
                        data=pdf_buffer,
                        file_name="crossword_empty_with_hints.pdf",
                        mime="application/pdf"
                    )
                
                #Tạo bảng mới:
                if st.button("🔄 Tạo bảng mới", key="new_crossword"):
                    # Reset về màn hình setup để chọn lại chủ đề và độ khó
                    crossword.update({
                        'screen': 'setup',
                        'submitted': False
                    })
                    st.rerun()
                
                # Nút nộp bài
                if st.button("✅ Nộp bài Crossword"):
                    crossword['submitted'] = True
                    crossword['end_time'] = datetime.now()
                    crossword['screen'] = 'result'
                    st.rerun()           

                    
            elif screen == 'result' or crossword['submitted']:
                st.subheader("📊 Kết quả Crossword Puzzle")

                correct_count = 0
                total_words = len(crossword['words'])

                st.markdown(f"""
                **Chủ đề:** {crossword['topic']}  
                **Độ khó:** {crossword['difficulty']}  
                **Thời gian hoàn thành:** {(crossword['end_time'] - crossword['start_time']).seconds} giây
                """)              
            
                st.subheader("📝 Kết quả từng từ")
                user_inputs = {}
                for i in range(len(crossword['grid'])):
                    for j in range(len(crossword['grid'][0])):
                        key = f"cell_{i}_{j}"
                        user_inputs[(i, j)] = st.session_state.get(key, "").upper()

                for word in crossword['words']:
                    correct_word = word['word'].upper()
                    user_word = ""

                    for idx in range(len(correct_word)):
                        row = word['row'] + idx if word['direction'] == 'down' else word['row']
                        col = word['col'] + idx if word['direction'] == 'across' else word['col']
                        user_word += user_inputs.get((row, col), '')

                    is_correct = user_word == correct_word
                    if is_correct:
                        correct_count += 1
                        st.success(f"✅ {correct_word}: Đúng!")
                    else:
                        st.error(f"❌ {user_word} ≠ {correct_word}. Đáp án đúng: {correct_word}")
                    st.markdown(f"*Gợi ý:* {word['hint']}")

                score = (correct_count / total_words) * 100
                st.success(f"🎉 Bạn đã đúng {correct_count}/{total_words} từ ({score:.1f}%)") 
                
                # Hiển thị bảng đã điền để đối chiếu
                st.subheader("🔍 Bảng ô chữ đã điền")
                grid_size = len(crossword['grid'])

                table_html = """
                <style>
                .crossword-table td {
                    width: 40px;
                    height: 40px;
                    text-align: center;
                    vertical-align: middle;
                    border: 1px solid #999;
                    font-size: 16px;
                    font-weight: bold;
                    padding: 0;
                }
                .crossword-table .filled {
                    background-color: #a8d0ff;
                }
                .crossword-table .empty {
                    background-color: #e0e0e0;
                }
                </style>
                <table class='crossword-table' style='border-collapse: collapse;'>
                """

                for i in range(grid_size):
                    table_html += "<tr>"
                    for j in range(grid_size):
                        letter = crossword['grid'][i][j]
                        if letter == ' ':
                            table_html += "<td class='empty'></td>"
                        else:
                            cell_value = user_inputs.get((i, j), '')
                            table_html += f"<td class='filled'>{cell_value}</td>"
                    table_html += "</tr>"

                table_html += "</table>"

                st.markdown(table_html, unsafe_allow_html=True)

                # Thưởng sticker
                if score == 100 and not crossword.get('added_sticker', False):
                    add_stickers(conn, st.session_state.user['id'], 1)
                    crossword['added_sticker'] = True
                    st.balloons()
                    st.success("🌟 Xuất sắc! Bạn đã nhận được 1 sticker cho thành tích hoàn hảo!")

                # Lưu kết quả vào CSDL
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS crossword_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        topic TEXT NOT NULL,
                        difficulty TEXT NOT NULL,
                        total_words INTEGER NOT NULL,
                        correct_words INTEGER NOT NULL,
                        time_seconds INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )
                """)
                
                cursor.execute("""
                    INSERT INTO crossword_results 
                    (user_id, topic, difficulty, total_words, correct_words, time_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    st.session_state.user['id'],
                    crossword['topic'],
                    crossword['difficulty'],
                    total_words,
                    correct_count,
                    (crossword['end_time'] - crossword['start_time']).seconds
                ))
                conn.commit()

                if st.button("🔄 Chơi lại"):
                    st.session_state.crossword = {
                        'screen': 'setup',
                        'submitted': False,
                        'grid': None,
                        'words': [],
                        'answers': {},
                        'topic': None,
                        'difficulty': None,
                        'start_time': None,
                        'end_time': None,
                        'added_sticker': False
                    }
                    st.rerun()

                conn.close()

  
    with tab3:
        # Thêm chức năng Matrix Word Game
        if 'user' not in st.session_state:
            st.warning("Vui lòng đăng nhập trước khi chơi Matrix Word Game.")
        else:
            # Khởi tạo session state
            if 'matrix_word' not in st.session_state:
                st.session_state.matrix_word = {
                    'screen': 'setup',
                    'grid': None,
                    'words': [],
                    'hints': [],
                    'topic': None,
                    'difficulty': None,
                    'size': None,
                    'word_count': None,
                    'show_solution': False
                }

            matrix_word = st.session_state.matrix_word
            screen = matrix_word['screen']
            conn = get_connection()

            def generate_matrix_word(words, size, word_count):
                # Chọn ngẫu nhiên số lượng từ yêu cầu
                selected_words = random.sample(words, min(word_count, len(words)))
                word_list = [{'word': word['word'].upper(), 'hint': word['hint']} for word in selected_words]
                
                # Tạo ma trận rỗng
                grid = [[' ' for _ in range(size)] for _ in range(size)]
                placed_words = []
                
                # Danh sách màu sắc có thể sử dụng (màu pastel để dễ nhìn)
                color_palette = [
                    (255, 179, 186),  # Light pink
                    (255, 223, 186),  # Light orange
                    (255, 255, 186),  # Light yellow
                    (186, 255, 201),  # Light green
                    (186, 225, 255),  # Light blue
                    (225, 186, 255),  # Light purple
                    (255, 186, 239),  # Light magenta
                    (204, 204, 255),  # Lavender
                    (204, 255, 204),  # Mint
                    (255, 204, 204)   # Peach
                ]
                
                # Các hướng có thể đặt từ
                directions = [
                    (1, 0), (0, 1), (1, 1), (1, -1),
                    (-1, 0), (0, -1), (-1, -1), (-1, 1)
                ]
                
                for idx, word_data in enumerate(word_list):
                    word = word_data['word']
                    word_length = len(word)
                    
                    if word_length > size:
                        st.warning(f"Từ '{word}' quá dài so với kích thước bảng {size}x{size} và sẽ bị bỏ qua.")
                        continue
                        
                    placed = False
                    attempts = 0
                    max_attempts = 100
                    
                    # Chọn màu cho từ này (lặp lại palette nếu cần)
                    color = color_palette[idx % len(color_palette)]
                    
                    while not placed and attempts < max_attempts:
                        attempts += 1
                        direction = random.choice(directions)
                        dx, dy = direction
                        
                        # Tính toán phạm vi hợp lệ
                        if dx == 1:
                            max_row = size - word_length
                            min_row = 0
                        elif dx == -1:
                            max_row = size - 1
                            min_row = word_length - 1
                        else:
                            max_row = size - 1
                            min_row = 0
                            
                        if dy == 1:
                            max_col = size - word_length
                            min_col = 0
                        elif dy == -1:
                            max_col = size - 1
                            min_col = word_length - 1
                        else:
                            max_col = size - 1
                            min_col = 0
                        
                        if min_row > max_row or min_col > max_col:
                            continue
                            
                        row = random.randint(min_row, max_row)
                        col = random.randint(min_col, max_col)
                        
                        can_place = True
                        for i in range(word_length):
                            r = row + i * dx
                            c = col + i * dy
                            if r < 0 or r >= size or c < 0 or c >= size:
                                can_place = False
                                break
                            if grid[r][c] not in (' ', word[i]):
                                can_place = False
                                break
                        
                        if can_place:
                            for i in range(word_length):
                                r = row + i * dx
                                c = col + i * dy
                                grid[r][c] = word[i]
                            
                            placed_words.append({
                                'word': word,
                                'row': row,
                                'col': col,
                                'dx': dx,
                                'dy': dy,
                                'color': color  # Lưu màu sắc của từ
                            })
                            placed = True
                    
                    if not placed:
                        st.warning(f"Không thể đặt từ '{word}' vào bảng sau {max_attempts} lần thử.")
                
                # Điền các ô trống bằng chữ cái ngẫu nhiên
                letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                for i in range(size):
                    for j in range(size):
                        if grid[i][j] == ' ':
                            grid[i][j] = random.choice(letters)
                
                return grid, placed_words, [w['hint'] for w in word_list]
                
                # Điền các ô trống bằng chữ cái ngẫu nhiên
                letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                for i in range(size):
                    for j in range(size):
                        if grid[i][j] == ' ':
                            grid[i][j] = random.choice(letters)
                
                return grid, placed_words, [w['hint'] for w in word_list]

            def create_pdf(grid, words, hints, show_solution=False):
                pdf = FPDF()
                pdf.add_page()

                # Thêm font Unicode (chỉ cần một lần)
                pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
                pdf.set_font("DejaVu", size=12)
                
                # Tiêu đề
                pdf.cell(200, 10, txt="Matrix Word Game", ln=1, align="C")
                pdf.cell(200, 10, txt=f"Chủ đề: {matrix_word['topic']}", ln=1, align="C")
                pdf.cell(200, 10, txt=f"Độ khó: {matrix_word['difficulty']}", ln=1, align="C")
                pdf.ln(10)
                
                # Vẽ bảng ô chữ
                size = matrix_word['size']
                cell_size = 10
                start_x = (210 - size * cell_size) / 2
                
                for i in range(size):
                    for j in range(size):
                        pdf.rect(start_x + j * cell_size, 60 + i * cell_size, cell_size, cell_size)
                        if show_solution:
                            # Kiểm tra xem ô này thuộc từ nào
                            for word_info in matrix_word['words']:
                                word = word_info['word']
                                dx, dy = word_info['dx'], word_info['dy']
                                for k in range(len(word)):
                                    r = word_info['row'] + k * dx
                                    c = word_info['col'] + k * dy
                                    if i == r and j == c:
                                        # Sử dụng màu đã lưu cho từ này
                                        color = word_info['color']
                                        pdf.set_fill_color(*color)
                                        pdf.rect(start_x + j * cell_size, 60 + i * cell_size, 
                                                cell_size, cell_size, 'F')
                                        pdf.set_fill_color(255, 255, 255)
                                        break
                        pdf.text(start_x + j * cell_size + 3, 60 + i * cell_size + 7, grid[i][j])
                
                pdf.ln(size * cell_size + 20)
                
                # Danh sách từ hoặc gợi ý
                if show_solution:
                    pdf.cell(200, 10, txt="ĐÁP ÁN:", ln=1)
                    for word_info in matrix_word['words']:
                        # Hiển thị từ với màu tương ứng
                        color = word_info['color']
                        pdf.set_text_color(*color)
                        pdf.cell(200, 10, txt=f"{word_info['word']}", ln=1)
                        pdf.set_text_color(0, 0, 0)  # Reset về màu đen
                else:
                    if st.session_state.show_hints:
                        pdf.cell(200, 10, txt="GỢI Ý:", ln=1)
                        for hint in matrix_word['hints']:
                            pdf.cell(200, 10, txt=f"- {hint}", ln=1)
                    else:
                        pdf.cell(200, 10, txt="CÁC TỪ CẦN TÌM:", ln=1)
                        for word_info in matrix_word['words']:
                            pdf.cell(200, 10, txt=f"- {word_info['word']}", ln=1)
                
                return pdf

            if screen == 'setup':
                st.title("🔠 Matrix Word Game")
                cursor = conn.cursor()
                
                # Chọn chủ đề
                cursor.execute("SELECT DISTINCT topic FROM hangman_words")
                topics = [row[0] for row in cursor.fetchall()]
                selected_topic = st.selectbox("📚 Chọn chủ đề", topics, key="matrix_topic")
                
                # Chọn độ khó
                cursor.execute("SELECT DISTINCT difficulty FROM hangman_words")
                difficulties = [row[0] for row in cursor.fetchall()]
                selected_difficulty = st.selectbox("🎯 Chọn độ khó", difficulties, key="matrix_difficulty")
                
                # Chọn số lượng từ
                word_count = st.slider("🔢 Số lượng từ (5-20)", 5, 30, 10, key="matrix_word_count")
                
                # Chọn kích thước bảng
                grid_size = st.selectbox("📏 Kích thước bảng", [10, 12, 15], key="matrix_grid_size")
                
                if st.button("🚀 Tạo ô chữ", key="generate_matrix"):
                    cursor.execute("""
                        SELECT word, hint FROM hangman_words
                        WHERE topic = ? AND difficulty = ?
                        ORDER BY RANDOM() LIMIT ?
                    """, (selected_topic, selected_difficulty, word_count + 3))  # Lấy thêm 3 từ phòng trường hợp không đặt được
                    
                    words_data = [{'word': row[0], 'hint': row[1]} for row in cursor.fetchall()]
                    
                    if len(words_data) < 5:
                        st.error("Không đủ từ cho chủ đề và độ khó này!")
                    else:
                        grid, placed_words, hints = generate_matrix_word(words_data, grid_size, word_count)
                        matrix_word.update({
                            'grid': grid,
                            'words': placed_words,
                            'hints': hints,
                            'topic': selected_topic,
                            'difficulty': selected_difficulty,
                            'size': grid_size,
                            'word_count': word_count,
                            'screen': 'game',
                            'show_solution': False
                        })
                        st.session_state.show_hints = False
                        st.rerun()

            elif screen == 'game':
                st.title("🔠 Matrix Word Game")
                st.subheader(f"Chủ đề: {matrix_word['topic']} - Độ khó: {matrix_word['difficulty']}")

                # Bố cục: bảng ô chữ phía trên, thông tin bên dưới
                st.markdown("### Bảng ô chữ")

                # Tạo bảng HTML
                grid_html = "<div style='display: inline-block; border: 2px solid #333;'>"
                for i in range(matrix_word['size']):
                    grid_html += "<div style='display: flex;'>"
                    for j in range(matrix_word['size']):
                        cell_style = (
                            "border: 1px solid #ddd; "
                            "width: 50px; height: 50px; "
                            "display: flex; align-items: center; justify-content: center; "
                            "font-weight: bold; font-size: 20px;"
                        )
                        if matrix_word['show_solution']:
                            for word_info in matrix_word['words']:
                                word = word_info['word']
                                dx, dy = word_info['dx'], word_info['dy']
                                color = word_info['color']
                                for k in range(len(word)):
                                    r = word_info['row'] + k * dx
                                    c = word_info['col'] + k * dy
                                    if i == r and j == c:
                                        hex_color = '#%02x%02x%02x' % color
                                        cell_style += f" background-color: {hex_color};"
                                        break
                        grid_html += f"<div style='{cell_style}'>{matrix_word['grid'][i][j]}</div>"
                    grid_html += "</div>"
                grid_html += "</div>"

                st.markdown(grid_html, unsafe_allow_html=True)

                # --- Thông tin bên dưới ---
                if 'show_words' not in st.session_state:
                    st.session_state.show_words = False

                # Checkbox chuyển chế độ hiển thị
                st.session_state.show_words = st.checkbox("Hiển thị các từ cần tìm thay vì gợi ý", value=st.session_state.show_words)

                # Hiển thị gợi ý hoặc từ
                if st.session_state.show_words:
                    st.markdown("**<span style='font-size:20px;'>Các từ cần tìm:</span>**", unsafe_allow_html=True)
                    for word_info in matrix_word['words']:
                        st.markdown(f"<span style='font-size:18px;'>- {word_info['word']}</span>", unsafe_allow_html=True)
                else:
                    st.markdown("**<span style='font-size:20px;'>Gợi ý:</span>**", unsafe_allow_html=True)
                    for hint in matrix_word['hints']:
                        st.markdown(f"<span style='font-size:18px;'>- {hint}</span>", unsafe_allow_html=True)



                # Nút in và điều khiển phía dưới
                col1, col2, col3 = st.columns(3)

                with col2:
                    if st.button("🖨️ In bảng chữ + từ"):
                        pdf = create_pdf(matrix_word['grid'], matrix_word['words'], matrix_word['hints'])
                        pdf_bytes = bytes(pdf.output(dest='S'))  # Chuyển bytearray -> bytes
                        st.download_button(
                            label="📥 Tải về PDF",
                            data=pdf_bytes,
                            file_name="matrix_word_game.pdf",
                            mime="application/pdf"
                        )

                with col1:
                    if st.button("🖨️ In bảng chữ + gợi ý"):
                        st.session_state.show_hints = True
                        pdf = create_pdf(matrix_word['grid'], matrix_word['words'], matrix_word['hints'])
                        pdf_bytes = bytes(pdf.output(dest='S'))  # Chuyển bytearray -> bytes
                        st.download_button(
                            label="📥 Tải về PDF",
                            data=pdf_bytes,
                            file_name="matrix_word_game_with_hints.pdf",
                            mime="application/pdf"
                        )

                with col3:
                    if st.button("🔍 Hiển thị đáp án"):
                        matrix_word['show_solution'] = not matrix_word['show_solution']
                        st.rerun()

                if matrix_word['show_solution']:
                    st.write("### Đáp án")
                    pdf = create_pdf(matrix_word['grid'], matrix_word['words'], matrix_word['hints'], show_solution=True)
                    pdf_bytes = bytes(pdf.output(dest='S'))  # Chuyển bytearray -> bytes
                    st.download_button(
                        label="📥 Tải đáp án PDF",
                        data=pdf_bytes,
                        file_name="matrix_word_game_solution.pdf",
                        mime="application/pdf"
                    )

                if st.button("🔄 Tạo ô chữ mới"):
                    matrix_word['screen'] = 'setup'
                    st.rerun()
                    
                    
    with tab4:
        if 'user' not in st.session_state:
            st.warning("Vui lòng đăng nhập trước khi chơi game đoán từ.")
        else:
            # Khởi tạo session state
            if 'word_guess' not in st.session_state:
                st.session_state.word_guess = {
                    'screen': 'setup',
                    'current_question': None,
                    'questions': [],
                    'score': 0,
                    'start_time': None,
                    'hints_shown': 0,
                    'game_over': False,
                    'user_guess': '',
                    'topic': None,
                    'difficulty': None,
                    'remaining_hearts': 5,
                    'wrong_guesses': 0,
                    'current_answer': '',
                    'current_hints': [],
                    'current_image_url': '',
                    'questions_answered': 0,
                    'total_questions': 5
                }

            game = st.session_state.word_guess
            screen = game['screen']
            conn = get_connection()

            def load_questions(topic=None, difficulty=None, limit=5):
                cursor = conn.cursor()
                if topic and difficulty:
                    cursor.execute("""
                        SELECT * FROM guess_image_game
                        WHERE topic = ? AND difficulty = ?
                        ORDER BY RANDOM()
                        LIMIT ?
                    """, (topic, difficulty, limit))
                elif topic:
                    cursor.execute("""
                        SELECT * FROM guess_image_game
                        WHERE topic = ?
                        ORDER BY RANDOM()
                        LIMIT ?
                    """, (topic, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM guess_image_game 
                        ORDER BY RANDOM()
                        LIMIT ?
                    """, (limit,))
                return cursor.fetchall()

            def start_game():
                questions = load_questions(game['topic'], game['difficulty'], game['total_questions'])
                if len(questions) < 1:
                    st.error("Không đủ câu hỏi cho chủ đề và độ khó này!")
                    return False
                
                game.update({
                    'questions': questions,
                    'current_question': 0,
                    'score': 0,
                    'start_time': time.time(),
                    'hints_shown': 1,  # Bắt đầu với gợi ý 1
                    'game_over': False,
                    'user_guess': '',
                    'remaining_hearts': 5,
                    'wrong_guesses': 0,
                    'questions_answered': 0,
                    'current_answer': questions[0][2],
                    'current_hints': [questions[0][3], questions[0][4], questions[0][5]],
                    'current_image_url': questions[0][1],
                    'screen': 'game'
                })
                return True

            def calculate_score(hint_level):
                # Điểm càng cao nếu đoán đúng sớm
                return {1: 50, 2: 30, 3: 10}.get(hint_level, 0)

            def end_question(success):
                if success:
                    score_earned = calculate_score(game['hints_shown'])
                    game['score'] += score_earned
                    game['questions_answered'] += 1
                    
                    # Lưu lịch sử
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO game_history 
                        (user_id, question_id, guessed_correctly, score_earned, hints_used)
                        VALUES (?, ?, ?, ?, ?)
                    """, (st.session_state.user['id'], 
                         game['questions'][game['current_question']][0], 
                         True, score_earned, game['hints_shown']))
                    conn.commit()
                
                # Chuyển câu hỏi tiếp theo hoặc kết thúc game
                next_question = game['current_question'] + 1
                if next_question < len(game['questions']) and game['remaining_hearts'] > 0:
                    # Reset tất cả trạng thái về ban đầu
                    game['current_question'] = next_question
                    game['start_time'] = time.time()  # Reset thời gian
                    game['hints_shown'] = 1  # Reset về gợi ý 1
                    game['revealed_indices'] = []  # Reset số chữ cái đã mở
                    game['user_guess'] = ''  # Reset câu trả lời người dùng
                    game['current_answer'] = game['questions'][next_question][2]
                    game['current_hints'] = [
                        game['questions'][next_question][3],
                        game['questions'][next_question][4],
                        game['questions'][next_question][5]
                    ]
                    game['current_image_url'] = game['questions'][next_question][1]
                    game['wrong_guesses'] = 0  # Reset số lần đoán sai
                    
                    # Reset session state
                    if 'start_time' in st.session_state:
                        st.session_state.start_time = time.time()
                    if 'user_guess' in st.session_state:
                        st.session_state.user_guess = ''

                else:
                    # Lưu điểm tổng nếu kết thúc game
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO game_scores (user_id, score, topic, difficulty)
                        VALUES (?, ?, ?, ?)
                    """, (st.session_state.user['id'], game['score'], game['topic'], game['difficulty']))
                    conn.commit()
                    
                    game['game_over'] = True
                
                st.rerun()

            def display_hearts():
                hearts = "❤️ " * game['remaining_hearts'] + "💔 " * (5 - game['remaining_hearts'])
                st.markdown(f"<div style='font-size: 24px; margin-bottom: 10px;'>{hearts}</div>", 
                           unsafe_allow_html=True)

            def display_word_length():
                answer = game['current_answer']
                revealed = game.get('revealed_indices', [])

                display = ""
                for i, char in enumerate(answer):
                    if i in revealed:
                        display += f"<div class='cell'>{char.upper()}</div>"
                    else:
                        display += "<div class='cell'>&nbsp;</div>"

                st.markdown("""
                <style>
                .cell {
                    display: inline-block;
                    width: 40px;
                    height: 40px;
                    border: 2px solid #007ACC;
                    margin: 4px;
                    text-align: center;
                    line-height: 40px;
                    font-size: 24px;
                    font-weight: bold;
                    border-radius: 8px;
                    background-color: #e0f0ff;
                }
                </style>
                """, unsafe_allow_html=True)

                st.markdown(f"<div style='display: flex; flex-wrap: wrap;'>{display}</div>", unsafe_allow_html=True)

                st.markdown(f"""
                    <div style='font-size: 20px; font-weight: bold; margin-top: 10px;'>
                        Từ này gồm {len(answer)} chữ cái
                    </div>
                """, unsafe_allow_html=True)

            def reveal_random_letter(answer, revealed_indices):
                available_indices = [i for i in range(len(answer)) if i not in revealed_indices]
                if available_indices:
                    index = random.choice(available_indices)
                    revealed_indices.append(index)
                return revealed_indices


            if screen == 'setup':
                st.title("🖼️ Guess Image")
                
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT topic FROM guess_image_game ORDER BY topic")
                topics = [row[0] for row in cursor.fetchall()]
                game['topic'] = st.selectbox("📚 Chọn chủ đề", topics, key="word_topic")

                cursor.execute("SELECT DISTINCT difficulty FROM guess_image_game ORDER BY difficulty")
                difficulties = [row[0] for row in cursor.fetchall()]
                game['difficulty'] = st.selectbox("🎯 Chọn độ khó", difficulties, key="word_difficulty")

                game['total_questions'] = st.slider("Số lượng câu hỏi", 3, 10, 5)

                if st.button("🚀 Bắt đầu chơi", key="start_word_game"):
                    if start_game():
                        st.rerun()

                # Phần admin - quản lý câu hỏi
                if st.session_state.user.get('role') == 'admin':
                    st.markdown("---")
                    st.subheader("🔧 Quản lý câu hỏi (Admin)")
                    
                    tab_admin1, tab_admin2, tab_admin3 = st.tabs(["Thêm câu hỏi", "Danh sách câu hỏi", "Import từ CSV"])
                    
                    with tab_admin1:
                        with st.form("add_question_form"):
                            image_url = st.text_input("URL hình ảnh (hiển thị sau cùng)")
                            answer = st.text_input("Đáp án")
                            hint1 = st.text_input("Gợi ý 1 (hiển thị đầu tiên)")
                            hint2 = st.text_input("Gợi ý 2 (hiển thị sau 20s)")
                            hint3 = st.text_input("Gợi ý 3 (hiển thị sau 40s)")
                            topic = st.text_input("Chủ đề")
                            difficulty = st.selectbox("Độ khó", difficulties + ["Thêm mới..."])
                            
                            if difficulty == "Thêm mới...":
                                difficulty = st.text_input("Nhập độ khó mới")
                            
                            if st.form_submit_button("Thêm câu hỏi"):
                                if answer and hint1 and hint2 and hint3 and topic and difficulty:
                                    try:
                                        # Thêm vào database
                                        cursor.execute("""
                                            INSERT INTO guess_image_game 
                                            (image_path, answer, hint1, hint2, hint3, topic, difficulty, added_by)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                        """, (image_url, answer, hint1, hint2, hint3, topic, difficulty, st.session_state.user['id']))
                                        conn.commit()
                                        st.success("Đã thêm câu hỏi mới!")
                                    except Exception as e:
                                        st.error(f"Lỗi khi thêm câu hỏi: {e}")
                                else:
                                    st.error("Vui lòng điền đầy đủ thông tin (trừ URL hình ảnh)")
                    
                    with tab_admin2:
                        st.subheader("Danh sách câu hỏi hiện có")
                        cursor.execute("""
                            SELECT id, topic, difficulty, answer, hint1, hint2, hint3 
                            FROM guess_image_game 
                            ORDER BY date_added DESC
                            LIMIT 50
                        """)
                        questions = cursor.fetchall()
                        
                        if questions:
                            df = pd.DataFrame(questions, columns=["ID", "Chủ đề", "Độ khó", "Đáp án", "Gợi ý 1", "Gợi ý 2", "Gợi ý 3"])
                            st.dataframe(df)
                        else:
                            st.info("Chưa có câu hỏi nào trong hệ thống.")
                            
                    with tab_admin3:
                        st.subheader("Import câu hỏi từ CSV")
                        st.info("""
                            Tải lên file CSV chứa danh sách câu hỏi. File cần có các cột sau:
                            - answer: Đáp án (bắt buộc)
                            - hint1: Gợi ý 1 (bắt buộc)
                            - hint2: Gợi ý 2 (bắt buộc)
                            - hint3: Gợi ý 3 (bắt buộc)
                            - topic: Chủ đề (bắt buộc)
                            - difficulty: Độ khó (bắt buộc)
                            - image_path: URL hình ảnh (không bắt buộc)
                        """)
                        
                        # Tạo và cung cấp template CSV
                        template_data = {
                            'answer': ['Ví dụ 1', 'Ví dụ 2'],
                            'hint1': ['Gợi ý 1-1', 'Gợi ý 1-2'],
                            'hint2': ['Gợi ý 2-1', 'Gợi ý 2-2'],
                            'hint3': ['Gợi ý 3-1', 'Gợi ý 3-2'],
                            'topic': ['Chủ đề 1', 'Chủ đề 2'],
                            'difficulty': ['Dễ', 'Trung bình'],
                            'image_path': ['', 'https://example.com/image.jpg']
                        }
                        template_df = pd.DataFrame(template_data)
                        
                        # Tạo nút tải template
                        csv = template_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="Tải template CSV",
                            data=csv,
                            file_name="template_import_cau_hoi.csv",
                            mime="text/csv",
                            help="Tải về file mẫu để nhập liệu"
                        )
                        
                        uploaded_file = st.file_uploader("Chọn file CSV", type=["csv"])
                        
                        if uploaded_file is not None:
                            try:
                                df = pd.read_csv(uploaded_file)
                                required_columns = ['answer', 'hint1', 'hint2', 'hint3', 'topic', 'difficulty']
                                
                                # Kiểm tra các cột bắt buộc
                                missing_columns = [col for col in required_columns if col not in df.columns]
                                if missing_columns:
                                    st.error(f"Thiếu các cột bắt buộc: {', '.join(missing_columns)}")
                                else:
                                    st.success("File CSV hợp lệ!")
                                    st.write("Xem trước dữ liệu (5 dòng đầu):")
                                    st.dataframe(df.head())
                                    
                                    if st.button("Import dữ liệu vào hệ thống"):
                                        try:
                                            # Thêm từng câu hỏi vào database
                                            success_count = 0
                                            error_count = 0
                                            error_messages = []
                                            
                                            for index, row in df.iterrows():
                                                try:
                                                    cursor.execute("""
                                                        INSERT INTO guess_image_game 
                                                        (image_path, answer, hint1, hint2, hint3, topic, difficulty, added_by)
                                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                                    """, (
                                                        row.get('image_path', ''),
                                                        row['answer'],
                                                        row['hint1'],
                                                        row['hint2'],
                                                        row['hint3'],
                                                        row['topic'],
                                                        row['difficulty'],
                                                        st.session_state.user['id']
                                                    ))
                                                    success_count += 1
                                                except Exception as e:
                                                    error_count += 1
                                                    error_messages.append(f"Dòng {index+1}: {row['answer']} - {str(e)}")
                                            
                                            conn.commit()
                                            
                                            if error_count > 0:
                                                with st.expander(f"Xem chi tiết {error_count} lỗi"):
                                                    for msg in error_messages:
                                                        st.warning(msg)
                                            
                                            st.success(f"Import hoàn tất! Thành công: {success_count}, Lỗi: {error_count}")
                                        except Exception as e:
                                            conn.rollback()
                                            st.error(f"Lỗi khi import dữ liệu: {e}")
                            except Exception as e:
                                st.error(f"Lỗi khi đọc file CSV: {e}")        

            elif screen == 'game' and not game['game_over']:
                # Khởi tạo các biến trò chơi
                game.setdefault('max_time', 60)
                game.setdefault('start_time', time.time())
                game.setdefault('user_guess', '')
                game.setdefault('revealed_indices', [])
                game.setdefault('wrong_guesses', 0)

                # Tính thời gian còn lại
                elapsed = time.time() - game['start_time']
                remaining = max(0, game['max_time'] - elapsed)

                st.title("🔤 Guess Image")
                st.write(f"Chủ đề: {game['topic']} | Độ khó: {game['difficulty']}")
                st.markdown(
                    f"""
                    <div style='display: flex; justify-content: start; gap: 20px; font-size: 16px;'>
                        <div>📊 Câu hỏi: {game['questions_answered'] + 1}/{len(game['questions'])}</div>
                        <div>🎯 Điểm hiện tại: {game['score']}</div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Hiển thị số tim
                display_hearts()

                # Hiển thị đồng hồ
                st.markdown(f"⏳ **Thời gian còn lại:** {int(remaining)} giây")

                # Hiển thị ảnh
                image_ph = st.empty()
                if elapsed < 40:
                    image_path = "assets/white.jpg"
                    image_ph.image(image_path, width=400)
                elif game['current_image_url']:
                    try:
                        image_ph.image(game['current_image_url'], width=400)
                    except Exception:
                        image_ph.error("Không thể tải hình ảnh")

                # Hiển thị độ dài từ
                display_word_length()

                # Tạo các placeholder cố định
                st.markdown("<div style='font-size: 20px; font-weight: bold;'>💡 Gợi ý:</div>", unsafe_allow_html=True)
                hint1_ph = st.empty()
                hint2_ph = st.empty()
                hint3_ph = st.empty()

                # Hiển thị nội dung tùy theo thời gian
                hint1_ph.write(f"1. {game['current_hints'][0]}")
                hint2_ph.write(f"2. {'' if elapsed < 20 else game['current_hints'][1]}")
                hint3_ph.write(f"3. {'' if elapsed < 40 else game['current_hints'][2]}")

                # Logic cập nhật gợi ý
                if elapsed >= 40 and game['hints_shown'] < 3:
                    game['hints_shown'] = 3
                    game['revealed_indices'] = reveal_random_letter(game['current_answer'], game['revealed_indices'])
                    st.rerun()
                elif elapsed >= 20 and game['hints_shown'] < 2:
                    game['hints_shown'] = 2
                    game['revealed_indices'] = reveal_random_letter(game['current_answer'], game['revealed_indices'])
                    st.rerun()

                # Ô nhập đáp án
                user_guess = st.text_input("Nhập đáp án của bạn:", 
                                           value=game['user_guess'], 
                                           key=f"guess_{game['current_question']}")
                
                if user_guess != game['user_guess']:
                    game['user_guess'] = user_guess
                    st.rerun()

                if st.button("Kiểm tra", key=f"check_{game['current_question']}"):
                    if user_guess.lower() == game['current_answer'].lower():
                        score_earned = calculate_score(game['hints_shown'])
                        st.success(f"🎉 Chính xác! +{score_earned} điểm")
                        time.sleep(1)
                        end_question(True)
                    else:
                        game['wrong_guesses'] += 1
                        game['remaining_hearts'] -= 1
                        st.error(f"Sai rồi! Bạn còn {game['remaining_hearts']} ❤️")
                        
                        if game['remaining_hearts'] <= 0:
                            st.error("💔 Bạn đã hết tim! Trò chơi kết thúc.")
                            time.sleep(2)
                            game['game_over'] = True
                            st.rerun()
                        else:
                            st.rerun()

                # Kiểm tra hết giờ
                if remaining <= 0:
                    st.warning("⏰ Hết giờ!")
                    game['game_over'] = True
                    st.rerun()

                # Cập nhật đồng hồ
                if not game['game_over']:
                    time.sleep(1)
                    st.rerun()


            elif game['game_over']:
                st.title("🏁 Kết thúc game!")
                
                if game['questions_answered'] == len(game['questions']):
                    st.balloons()
                    st.success("🎉 CHÚC MỪNG! Bạn đã hoàn thành tất cả câu hỏi!")

                st.write(f"🎯 Tổng điểm của bạn: {game['score']}")
                st.write(f"✅ Số câu trả lời đúng: {game['questions_answered']}/{len(game['questions'])}")
                
                # Đảm bảo cột topic và difficulty tồn tại trong game_scores
                cursor = conn.cursor()
                try:
                    cursor.execute("ALTER TABLE game_scores ADD COLUMN topic TEXT")
                except sqlite3.OperationalError:
                    pass
                try:
                    cursor.execute("ALTER TABLE game_scores ADD COLUMN difficulty TEXT")
                except sqlite3.OperationalError:
                    pass

                
                # Hiển thị bảng xếp hạng
                st.subheader("🏆 Bảng xếp hạng")
                cursor.execute("""
                    SELECT u.username, g.score, g.topic, g.difficulty
                    FROM game_scores g
                    JOIN users u ON g.user_id = u.id
                    WHERE g.topic = ? AND g.difficulty = ?
                    ORDER BY g.score DESC
                    LIMIT 10
                """, (game['topic'], game['difficulty']))
                leaderboard = cursor.fetchall()
                
                if leaderboard:
                    df = pd.DataFrame(leaderboard, columns=["Tên", "Điểm", "Chủ đề", "Độ khó"])
                    st.dataframe(df.style.highlight_max(subset=["Điểm"], color='lightgreen'))
                else:
                    st.write("Chưa có dữ liệu xếp hạng cho chủ đề này")
                
                # Hiển thị lịch sử chơi
                st.subheader("📜 Lịch sử chơi của bạn")
                cursor.execute("""
                    SELECT g.answer, h.guessed_correctly, h.score_earned, h.hints_used, h.timestamp
                    FROM game_history h
                    JOIN guess_image_game g ON h.question_id = g.id
                    WHERE h.user_id = ?
                    ORDER BY h.timestamp DESC
                    LIMIT 10
                """, (st.session_state.user['id'],))
                history = cursor.fetchall()
                
                if history:
                    df_history = pd.DataFrame(history, 
                                              columns=["Câu hỏi", "Đúng", "Điểm","Gợi ý đã dùng", "Thời gian"])
                    st.dataframe(df_history)
                else:
                    st.write("Chưa có lịch sử chơi")
                
                if st.button("🔄 Chơi lại"):
                    game['screen'] = 'setup'
                    game['game_over'] = False
                    game['score'] = 0
                    game['questions_answered'] = 0
                    game['current_question'] = 0
                    game['hints_shown'] = 1          # reset hint
                    game['revealed_indices'] = []    # reset ô chữ mở
                    game['user_guess'] = ''
                    game['remaining_hearts'] = 3     # hoặc giá trị bạn muốn mặc định
                    if 'start_time' in st.session_state:
                        del st.session_state['start_time']  # xóa để khởi tạo lại thời gian khi vào lại game
                    st.rerun()


             

    
    
#API từ điển
def fetch_definition(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        meanings = data[0].get("meanings", [])
        definitions = []
        for meaning in meanings:
            part_of_speech = meaning.get("partOfSpeech", "")
            for def_item in meaning.get("definitions", []):
                definition = def_item.get("definition", "")
                example = def_item.get("example", "")
                definitions.append((part_of_speech, definition, example))
        return definitions
    else:
        return None 

#phát âm từ điển
# Hàm tạo audio mp3 từ text
def generate_audio(word, lang='en'):
    tts = gTTS(text=word, lang=lang)
    file_path = f"{word}.mp3"
    tts.save(file_path)
    with open(file_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
    os.remove(file_path)
    return audio_bytes

# Khởi tạo session_state cho lịch sử từ nếu chưa có
if 'dict_history_words' not in st.session_state:
    st.session_state['dict_history_words'] = []

if 'dict_audio_bytes' not in st.session_state:
    st.session_state['dict_audio_bytes'] = None

if 'dict_last_word' not in st.session_state:
    st.session_state['dict_last_word'] = ""

if 'dict_last_results' not in st.session_state:
    st.session_state['dict_last_results'] = None

if 'dict_flashcards' not in st.session_state:
    st.session_state['dict_flashcards'] = []  # Mảng các dict: {'word':..., 'definitions':..., 'examples':...}
    

# Khởi tạo database
conn = get_connection()
init_db(conn)
conn.close()

# Màn hình đăng nhập/đăng ký
if 'user' not in st.session_state:
    st.title("🔐 Đăng nhập/Đăng ký")
    
    tab1, tab2 = st.tabs(["Đăng nhập", "Đăng ký"])
    
    with tab1:
        username = st.text_input("Tên đăng nhập")
        password = st.text_input("Mật khẩu", type="password")
        
        if st.button("Đăng nhập"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, username, role, stickers, is_approved 
                FROM users 
                WHERE username = ? AND password = ?
            """, (username, password))
            user = cursor.fetchone()
            conn.close()
            
            if user:
                if user[4]:  # Check is_approved status
                    st.session_state.user = {
                        'id': user[0],
                        'username': user[1],
                        'role': user[2],
                        'stickers': user[3]
                    }
                    st.rerun()
                else:
                    st.error("Tài khoản của bạn chưa được phê duyệt. Vui lòng chờ admin xét duyệt.")
            else:
                st.error("Tên đăng nhập hoặc mật khẩu không đúng")
    
    with tab2:
        new_username = st.text_input("Tên đăng nhập mới")
        new_password = st.text_input("Mật khẩu mới", type="password")
        confirm_password = st.text_input("Xác nhận mật khẩu", type="password")
        
        if st.button("Đăng ký"):
            if new_password != confirm_password:
                st.error("Mật khẩu xác nhận không khớp")
            elif not new_username or not new_password:
                st.error("Vui lòng nhập đầy đủ thông tin")
            else:
                conn = get_connection()
                cursor = conn.cursor()
                try:
                    # Default is_approved = False for new users
                    cursor.execute("""
                        INSERT INTO users (username, password, role, stickers, is_approved)
                        VALUES (?, ?, 'user', 0, 0)
                    """, (new_username, new_password))
                    conn.commit()
                    st.success("Đăng ký thành công! Tài khoản của bạn đang chờ phê duyệt từ admin.")
                except:
                    st.error("Tên đăng nhập đã tồn tại")
                finally:
                    conn.close()
    
    st.stop()

# Kiểm tra role để hiển thị chức năng phù hợp
if st.session_state.user['role'] == 'admin':
    st.sidebar.title(f"👨‍💼 Quản trị viên: {st.session_state.user['username']}")
    option = st.sidebar.radio("📌 Chọn chức năng", [
        "📝 Làm bài thi trắc nghiệm", 
        "📚 Quản lý câu hỏi",
        "👥 Quản lý người dùng",
        "🎁 Quản lý phần quà",
        "📖 Quản lý bài học",
        "🎮 Game"
    ])
else:
    st.sidebar.title(f"👤 Người dùng: {st.session_state.user['username']}")
    option = st.sidebar.radio("📌 Chọn chức năng", [
        "📚 Bài học",
        "📝 Làm bài thi trắc nghiệm", 
        "🏆 Lịch sử thi",
        "🎁 Đổi điểm thưởng",
        "📙 Từ điển",
        "🎮 Game"    
        
    ])

# Các hàm chung (lấy câu hỏi, lưu kết quả, v.v.)
def get_topics(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT topic FROM questions")
    return [row[0] for row in cursor.fetchall()]

def get_levels_by_topic(conn, topic):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT level FROM questions WHERE topic = ?", (topic,))
    return [row[0] for row in cursor.fetchall()]

def get_exam_codes_by_topic_level(conn, topic, level):
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT exam_code FROM questions WHERE topic = ? AND level = ? AND exam_code IS NOT NULL", (topic, level))
    return [row[0] for row in cursor.fetchall()]

def get_questions(conn, topic, level, exam_code, limit):
    cursor = conn.cursor()
    if exam_code:
        cursor.execute("""
            SELECT question, answer_a, answer_b, answer_c, answer_d, answer_e,
                   correct_answer, explanation, topic, level, exam_code
            FROM questions 
            WHERE topic = ? AND level = ? AND exam_code = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (topic, level, exam_code, limit))
    else:
        cursor.execute("""
            SELECT question, answer_a, answer_b, answer_c, answer_d, answer_e,
                   correct_answer, explanation, topic, level, exam_code
            FROM questions 
            WHERE topic = ? AND level = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (topic, level, limit))
    return cursor.fetchall()


def save_results(conn, user_id, topic, level, exam_code, num_questions, correct_answers, duration):
    cursor = conn.cursor()
    
    # Thêm kết quả mới với rewarded = 0
    cursor.execute("""
    INSERT INTO results (
        user_id, topic, level, exam_code, num_questions, correct_answers, duration, rewarded
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (user_id, topic, level, exam_code, num_questions, correct_answers, duration))
    
    conn.commit()


def get_last_10_results(conn, user_id):
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM results
    WHERE user_id = ?
    ORDER BY date DESC
    LIMIT 10
    """, (user_id,))
    return cursor.fetchall()

def add_questions_from_csv(conn, csv_file):
    df = pd.read_csv(csv_file)
    expected_columns = ['question', 'answer_a', 'answer_b', 'answer_c', 'answer_d', 'answer_e',
        'correct_answer', 'explanation', 'topic', 'level', 'exam_code']
    if not all(col in df.columns for col in expected_columns):
        st.error("❌ CSV không hợp lệ! Các cột yêu cầu: " + ", ".join(expected_columns))
        return
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute("""
        INSERT INTO questions (topic, level, exam_code, question, answer_a, answer_b, answer_c, answer_d, answer_e, correct_answer, explanation)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['topic'], row['level'], row['exam_code'], row['question'], 
            row['answer_a'], row['answer_b'], row['answer_c'],
            row['answer_d'], row['answer_e'], row['correct_answer'], row['explanation']
        ))
    conn.commit()
    st.success("Đã thêm các câu hỏi từ CSV thành công!")

# Chức năng quản lý câu hỏi (dành cho admin)
if option == "📚 Quản lý câu hỏi" and st.session_state.user['role'] == 'admin':
    st.title("📚 Quản lý câu hỏi trắc nghiệm")
    conn = get_connection()
    operation = st.radio("Chọn thao tác", ["Thêm câu hỏi từ CSV", "Thêm câu hỏi thủ công", "Sửa câu hỏi", "Xóa câu hỏi", "Xóa toàn bộ câu hỏi", "In đề thi + đáp án"])

    if operation == "Thêm câu hỏi từ CSV":
        st.subheader("📥 Thêm câu hỏi từ CSV")
        csv_file = st.file_uploader("Chọn file CSV", type=["csv"])
        if csv_file:
            add_questions_from_csv(conn, csv_file)

    elif operation == "Thêm câu hỏi thủ công":
        st.subheader("✍️ Thêm câu hỏi thủ công")

        # Chủ đề có thể chọn hoặc nhập mới
        topics = get_topics(conn)
        selected_topic = st.selectbox("📚 Chọn chủ đề", topics + ["🔸 Nhập chủ đề mới"])
        if selected_topic == "🔸 Nhập chủ đề mới":
            selected_topic = st.text_input("Nhập chủ đề mới")

        # Độ khó có thể chọn hoặc nhập mới
        levels = get_levels_by_topic(conn, selected_topic)
        selected_level = st.selectbox("🎯 Chọn độ khó", levels + ["🔸 Nhập độ khó mới"])
        if selected_level == "🔸 Nhập độ khó mới":
            selected_level = st.text_input("Nhập độ khó mới")

        # Mã đề có thể để trống
        exam_code = st.text_input("🔢 Mã đề (có thể để trống)")

        # Nội dung câu hỏi
        question = st.text_area("Câu hỏi")
        answer_a = st.text_input("Đáp án A")
        answer_b = st.text_input("Đáp án B")
        answer_c = st.text_input("Đáp án C")
        answer_d = st.text_input("Đáp án D")
        answer_e = st.text_input("Đáp án E (nếu có, có thể để trống)")
        correct_answer = st.radio("Đáp án đúng", ["A", "B", "C", "D", "E"])
        explanation = st.text_area("Giải thích")

        if st.button("➕ Thêm câu hỏi"):
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO questions (
                    question, answer_a, answer_b, answer_c, answer_d, answer_e,
                    correct_answer, explanation, topic, level, exam_code
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question, answer_a, answer_b, answer_c, answer_d, answer_e if answer_e else None,
                correct_answer, explanation, selected_topic, selected_level, exam_code if exam_code else None
            ))
            conn.commit()
            st.success("✅ Câu hỏi đã được thêm thành công!")



    elif operation == "Sửa câu hỏi":
        st.subheader("🛠️ Sửa câu hỏi")

        # Lấy danh sách câu hỏi (id và nội dung)
        cursor = conn.cursor()
        cursor.execute("SELECT id, question FROM questions")
        question_rows = cursor.fetchall()

        # Hiển thị danh sách câu hỏi để chọn
        question_options = {f"[{row[0]}] {row[1]}": row[0] for row in question_rows}
        selected_question_label = st.selectbox("🧠 Chọn câu hỏi để sửa", list(question_options.keys()))
        selected_question_id = question_options[selected_question_label]

        # Truy vấn chi tiết câu hỏi theo đúng thứ tự dữ liệu mẫu
        cursor.execute("""
            SELECT question, answer_a, answer_b, answer_c, answer_d, answer_e, correct_answer, explanation, topic, level, exam_code
            FROM questions WHERE id = ?
        """, (selected_question_id,))
        q = cursor.fetchone()

        # Lấy danh sách chủ đề và cấp độ
        topics = get_topics(conn)
        levels = get_levels_by_topic(conn, q[8])

        # Hiển thị topic và cho phép nhập mới
        selected_topic = st.selectbox("📚 Chủ đề", topics + ["🔸 Nhập mới"], index=topics.index(q[8]) if q[8] in topics else 0)
        if selected_topic == "🔸 Nhập mới":
            selected_topic = st.text_input("Nhập chủ đề mới", value=q[8])

        # Hiển thị level và cho phép nhập mới
        selected_level = st.selectbox("🎯 Độ khó", levels + ["🔸 Nhập mới"], index=levels.index(q[9]) if q[9] in levels else 0)
        if selected_level == "🔸 Nhập mới":
            selected_level = st.text_input("Nhập độ khó mới", value=q[9])

        # Mã đề (có thể rỗng)
        exam_code = st.text_input("🔢 Mã đề", value=q[10] or "")

        # Hiển thị nội dung câu hỏi và đáp án theo đúng thứ tự index
        question = st.text_area("📝 Câu hỏi", value=q[0])
        answer_a = st.text_input("Đáp án A", value=q[1])
        answer_b = st.text_input("Đáp án B", value=q[2])
        answer_c = st.text_input("Đáp án C", value=q[3])
        answer_d = st.text_input("Đáp án D", value=q[4])
        answer_e = st.text_input("Đáp án E (nếu có)", value=q[5] if q[5] is not None else "")

        # Chọn đáp án đúng
        correct_answer = st.radio(
            "✅ Đáp án đúng",
            ["A", "B", "C", "D", "E"],
            index=["A", "B", "C", "D", "E"].index(q[6]) if q[6] in ["A", "B", "C", "D", "E"] else 0
        )

        explanation = st.text_area("💡 Giải thích", value=q[7] or "")



        # Nút cập nhật
        if st.button("💾 Cập nhật câu hỏi"):
            cursor.execute("""
                UPDATE questions 
                SET topic = ?, level = ?, exam_code = ?, question = ?, 
                    answer_a = ?, answer_b = ?, answer_c = ?, answer_d = ?, answer_e = ?, 
                    correct_answer = ?, explanation = ?
                WHERE id = ?
            """, (
                selected_topic, selected_level, exam_code if exam_code else None,
                question, answer_a, answer_b, answer_c, answer_d,
                answer_e if answer_e else None,
                correct_answer, explanation,
                selected_question_id
            ))
            conn.commit()
            st.success("✅ Câu hỏi đã được cập nhật!")


    elif operation == "Xóa câu hỏi":
        st.subheader("🗑️ Xóa câu hỏi")
        question_id = st.number_input("ID câu hỏi cần xóa", min_value=1)
        if st.button("🗑️ Xóa câu hỏi"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
            conn.commit()
            st.success("✅ Câu hỏi đã được xóa!")

    elif operation == "Xóa toàn bộ câu hỏi":
        st.subheader("🗑️ Xóa toàn bộ câu hỏi")
        confirm = st.checkbox("Xác nhận xóa toàn bộ câu hỏi")
        if confirm and st.button("🗑️ Xóa toàn bộ câu hỏi"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM questions")
            conn.commit()
            st.success("✅ Tất cả câu hỏi đã được xóa!")
            
    elif operation == "In đề thi + đáp án":
        st.subheader("🖨️ In đề thi và đáp án")
        
        # Chọn tiêu chí lọc
        col1, col2, col3 = st.columns(3)
        with col1:
            topics = get_topics(conn)
            selected_topic = st.selectbox("📚 Chọn chủ đề", topics, key='topic_select')
        with col2:
            levels = get_levels_by_topic(conn, selected_topic)
            selected_level = st.selectbox("🎯 Chọn độ khó", levels, key='level_select')
        with col3:
            exam_codes = get_exam_codes_by_topic_level(conn, selected_topic, selected_level)
            selected_exam_code = st.selectbox("🔢 Chọn mã đề", [""] + exam_codes, key='exam_select')
        
        # Chọn số lượng câu hỏi
        num_questions = st.number_input("Số lượng câu hỏi", min_value=1, max_value=100, value=20, key='num_questions')
        
        # Hàm tạo PDF hỗ trợ UTF-8
        def create_pdf(filename, title, questions, selected_topic, selected_level, selected_exam_code=None, show_answers=False):
            pdf = FPDF()
            pdf.add_page()
            try:
                pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
            except:
                pdf.add_font("DejaVu", "", "arialuni.ttf", uni=True)  # Fallback font
            pdf.set_font("DejaVu", size=11)

            margin = 10
            col_width = (210 - 2 * margin) / 2  # A4 width = 210mm
            y_start = 40
            y_limit = 280
            line_spacing = 5

            x_left = margin
            x_right = margin + col_width
            y_left = y_start
            y_right = y_start

            # Tiêu đề
            pdf.set_xy(0, 10)
            pdf.cell(0, 10, f"{title.upper()}: {selected_topic} - {selected_level}", ln=1, align="C")
            if selected_exam_code:
                pdf.cell(0, 10, f"Mã đề: {selected_exam_code}", ln=1, align="C")
            pdf.ln(5)

            for i, q in enumerate(questions, 1):
                # Soạn nội dung câu hỏi
                content = f"Câu {i}: {q[0]}\nA. {q[1]}\nB. {q[2]}\nC. {q[3]}\nD. {q[4]}"
                if q[5]:
                    content += f"\nE. {q[5]}"
                if show_answers:
                    content += f"\nĐáp án đúng: {q[6]}"
                    if q[7]:
                        content += f"\nGiải thích: {q[7]}"

                # Ước lượng chiều cao nội dung
                height = pdf.get_string_width(content) / (col_width - 5) * line_spacing + 20
                height = max(30, height)  # đảm bảo chiều cao tối thiểu

                # In vào cột trái nếu còn chỗ
                if y_left + height < y_limit:
                    pdf.set_xy(x_left, y_left)
                    pdf.multi_cell(col_width - 5, line_spacing, content)
                    y_left = pdf.get_y() + 5
                # Nếu cột trái đầy, thử in sang cột phải
                elif y_right + height < y_limit:
                    pdf.set_xy(x_right, y_right)
                    pdf.multi_cell(col_width - 5, line_spacing, content)
                    y_right = pdf.get_y() + 5
                # Nếu cả hai cột đều đầy, sang trang mới
                else:
                    pdf.add_page()
                    y_left = y_start
                    y_right = y_start
                    pdf.set_xy(x_left, y_left)
                    pdf.multi_cell(col_width - 5, line_spacing, content)
                    y_left = pdf.get_y() + 5

            pdf.output(filename)
            return filename


        # Hàm callback để lưu questions vào session state
        def generate_exam():
            conn = get_connection()
            if selected_exam_code:
                questions = get_questions(conn, selected_topic, selected_level, selected_exam_code, num_questions)
            else:
                questions = get_questions(conn, selected_topic, selected_level, None, num_questions)
            conn.close()
            
            if questions:
                st.session_state['exam_questions'] = questions
                st.session_state['exam_generated'] = True
            else:
                st.warning("Không tìm thấy câu hỏi nào phù hợp!")
                st.session_state['exam_generated'] = False

        # Nút tạo đề thi
        if st.button("🖨️ Tạo đề thi và đáp án", on_click=generate_exam):
            pass  # Logic đã được xử lý trong callback

        # Hiển thị kết quả nếu đã generate
        if st.session_state.get('exam_generated', False):
            questions = st.session_state['exam_questions']
            
            tab1, tab2 = st.tabs(["📝 Đề thi", "✅ Đáp án"])

            with tab1:
                st.subheader(f"ĐỀ THI: {selected_topic} - {selected_level}")
                if selected_exam_code:
                    st.caption(f"Mã đề: {selected_exam_code}")

                for i, q in enumerate(questions, 1):
                    st.markdown(f"**Câu {i}:** {q[0]}")
                    st.markdown(f"A. {q[1]}")
                    st.markdown(f"B. {q[2]}")
                    st.markdown(f"C. {q[3]}")
                    st.markdown(f"D. {q[4]}")
                    if q[5]:
                        st.markdown(f"E. {q[5]}")
                    st.write("---")

                # Tạo file PDF tạm thời
                if st.button("Tạo file PDF đề thi"):
                    pdf_output = f"de_thi_{selected_topic}_{selected_level}.pdf"
                    create_pdf(pdf_output, "ĐỀ THI", questions, selected_topic, selected_level, selected_exam_code, False)
                    st.session_state['exam_pdf'] = pdf_output

                # Nút download
                if 'exam_pdf' in st.session_state:
                    with open(st.session_state['exam_pdf'], "rb") as f:
                        st.download_button(
                            label="📥 Tải đề thi (PDF)",
                            data=f,
                            file_name=st.session_state['exam_pdf'],
                            mime="application/pdf",
                            key='download_exam'
                        )

            with tab2:
                st.subheader(f"ĐÁP ÁN: {selected_topic} - {selected_level}")
                if selected_exam_code:
                    st.caption(f"Mã đề: {selected_exam_code}")

                col1, col2 = st.columns(2)
                total = len(questions)
                half = (total + 1) // 2  # Chia làm 2 cột, cột trái nhiều hơn nếu lẻ

                left_questions = questions[:half]
                right_questions = questions[half:]

                with col1:
                    for i, q in enumerate(left_questions, 1):
                        st.markdown(f"**Câu {i}:** {q[0]}")
                        st.success(f"Đáp án đúng: {q[6]}")
                        if q[7]:
                            st.info(f"Giải thích: {q[7]}")
                        st.write("---")

                with col2:
                    for j, q in enumerate(right_questions, half + 1):
                        st.markdown(f"**Câu {j}:** {q[0]}")
                        st.success(f"Đáp án đúng: {q[6]}")
                        if q[7]:
                            st.info(f"Giải thích: {q[7]}")
                        st.write("---")

                # Tạo file PDF tạm thời
                if st.button("Tạo file PDF đáp án"):
                    ans_output = f"dap_an_{selected_topic}_{selected_level}.pdf"
                    create_pdf(ans_output, "ĐÁP ÁN", questions, selected_topic, selected_level, selected_exam_code, True)
                    st.session_state['answer_pdf'] = ans_output

                # Nút download
                if 'answer_pdf' in st.session_state:
                    with open(st.session_state['answer_pdf'], "rb") as f:
                        st.download_button(
                            label="📥 Tải đáp án (PDF)",
                            data=f,
                            file_name=st.session_state['answer_pdf'],
                            mime="application/pdf",
                            key='download_answer'
                        )        
    
    conn.close()

# Chức năng quản lý người dùng (dành cho admin)
elif option == "👥 Quản lý người dùng" and st.session_state.user['role'] == 'admin':
    st.title("👥 Quản lý người dùng")
    conn = get_connection()
    
    # Thêm tab mới cho phê duyệt tài khoản
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Danh sách người dùng", 
        "➕ Thêm người dùng", 
        "❌ Xóa người dùng", 
        "✅ Phê duyệt tài khoản",
        "📝 Quản lý sticker"
    ])
    
    with tab1:  # Danh sách người dùng
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, stickers, is_approved FROM users")
        users = cursor.fetchall()
        
        if users:
            st.write("### Danh sách người dùng")
            for user in users:
                status = "✅ Đã duyệt" if user[4] else "🕒 Chờ duyệt"
                st.write(f"""
                - **ID:** {user[0]}  
                - **Tên:** {user[1]}  
                - **Vai trò:** {user[2]}  
                - **Sticker:** {user[3]}  
                - **Trạng thái:** {status}
                """)
                st.write("---")
        else:
            st.warning("Không có người dùng nào")
    
    with tab2:  # Thêm người dùng
        st.write("### Thêm người dùng mới")
        new_username = st.text_input("Tên đăng nhập", key="new_user_username")
        new_password = st.text_input("Mật khẩu", type="password", key="new_user_password")
        role = st.selectbox("Vai trò", ["user", "admin"], key="new_user_role")
        auto_approve = st.checkbox("Tự động phê duyệt", value=True, key="auto_approve")
        
        if st.button("Thêm người dùng", key="add_user_button"):
            if not new_username or not new_password:
                st.error("Vui lòng nhập đầy đủ thông tin")
            else:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO users (username, password, role, is_approved) 
                        VALUES (?, ?, ?, ?)
                    """, (new_username, new_password, role, 1 if auto_approve else 0))
                    conn.commit()
                    st.success(f"Thêm người dùng thành công! {'(Đã tự động phê duyệt)' if auto_approve else '(Chờ phê duyệt)'}")
                except sqlite3.IntegrityError:
                    st.error("Tên đăng nhập đã tồn tại")
    
    with tab3:  # Xóa người dùng
        st.write("### Xóa người dùng")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username FROM users WHERE id != ?", (st.session_state.user['id'],))
        users = cursor.fetchall()
        
        if users:
            user_options = {f"{user[1]} (ID: {user[0]})": user[0] for user in users}
            selected_user = st.selectbox("Chọn người dùng", list(user_options.keys()), key="delete_user_select")
            
            if st.button("Xóa người dùng", key="delete_user_button"):
                user_id = user_options[selected_user]
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
                st.success(f"Đã xóa người dùng {selected_user}")
        else:
            st.warning("Không có người dùng nào để xóa")
    
    with tab4:  # Phê duyệt tài khoản
        st.write("### Danh sách tài khoản chờ duyệt")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users WHERE is_approved = 0")
        pending_users = cursor.fetchall()
        
        if pending_users:
            for user in pending_users:
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"👤 {user[1]} (Vai trò: {user[2]})")
                with col2:
                    if st.button("Duyệt", key=f"approve_{user[0]}"):
                        cursor.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user[0],))
                        conn.commit()
                        st.success(f"Đã duyệt tài khoản {user[1]}")
                        st.rerun()
                with col3:
                    if st.button("Từ chối", key=f"reject_{user[0]}"):
                        cursor.execute("DELETE FROM users WHERE id = ?", (user[0],))
                        conn.commit()
                        st.success(f"Đã từ chối tài khoản {user[1]}")
                        st.rerun()
                st.write("---")
        else:
            st.info("Không có tài khoản nào chờ duyệt")
                
    with tab5:
        st.write("### Sửa số lượng sticker của người dùng")
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, stickers FROM users")
        users = cursor.fetchall()

        user_dict = {f"{user[1]} (ID: {user[0]})": user for user in users}
        selected_user = st.selectbox("Chọn người dùng", list(user_dict.keys()))

        user_id = user_dict[selected_user][0]
        current_stickers = user_dict[selected_user][2]

        st.info(f"🎫 Sticker hiện tại: {current_stickers}")
        new_stickers = st.number_input("Nhập số sticker mới", min_value=0, value=current_stickers, step=1)

        if st.button("Cập nhật sticker"):
            cursor.execute("UPDATE users SET stickers = ? WHERE id = ?", (new_stickers, user_id))
            conn.commit()
            st.success(f"Đã cập nhật sticker cho {selected_user} thành {new_stickers}")            
    
    conn.close()
    
# Chức năng game  
if option == "🎮 Game":
    game_section()    
    
# Chức năng quản lý bài học (dành cho admin)
if option == "📖 Quản lý bài học" and st.session_state.user['role'] == 'admin':
    st.title("📖 Quản lý bài học")
    conn = get_connection()
    
    operation = st.radio("Chọn thao tác", [
        "Quản lý chủ đề", 
        "Quản lý chương", 
        "Tạo bài học mới",
        "Quản lý bài học",
        "Tìm kiếm nâng cao"
    ])
    
    if operation == "Quản lý chủ đề":
        st.subheader("📚 Quản lý chủ đề")
        
        # Thêm tab cho các thao tác
        tab1, tab2, tab3 = st.tabs(["Thêm chủ đề mới", "Danh sách chủ đề", "Sửa/Xóa chủ đề"])
        
        with tab1:
            with st.form("add_lesson_topic_form"):
                name = st.text_input("Tên chủ đề*")
                description = st.text_area("Mô tả")
                thumbnail_url = st.text_input("URL hình ảnh đại diện")
                
                if st.form_submit_button("Thêm chủ đề"):
                    if not name:
                        st.error("Vui lòng nhập tên chủ đề")
                    else:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO lesson_topics (name, description, thumbnail_url) VALUES (?, ?, ?)",
                                (name, description, thumbnail_url if thumbnail_url else None)
                            )
                            conn.commit()
                            st.success("✅ Chủ đề đã được thêm thành công!")
                        except Exception as e:
                            st.error(f"Lỗi: {str(e)}")
        
        with tab2:
            st.subheader("Danh sách chủ đề")
            lesson_topics = conn.execute("SELECT * FROM lesson_topics ORDER BY name").fetchall()
            
            if not lesson_topics:
                st.info("Chưa có chủ đề nào")
            else:
                for lesson_topic in lesson_topics:
                    with st.expander(f"{lesson_topic[1]}"):
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            if lesson_topic[3]:
                                st.image(lesson_topic[3], width=150)
                        with col2:
                            st.write(f"**Mô tả:** {lesson_topic[2] or 'Không có mô tả'}")
                            st.write(f"**Số chương:** {conn.execute('SELECT COUNT(*) FROM chapters WHERE lesson_topic_id = ?', (lesson_topic[0],)).fetchone()[0]}")
                            st.write(f"**Ngày tạo:** {lesson_topic[4]}")
        
        with tab3:
            st.subheader("Sửa/Xóa chủ đề")
            lesson_topics = conn.execute("SELECT id, name FROM lesson_topics ORDER BY name").fetchall()
            
            if not lesson_topics:
                st.info("Không có chủ đề để chỉnh sửa")
            else:
                selected_lesson_topic = st.selectbox(
                    "Chọn chủ đề",
                    [f"{t[0]} - {t[1]}" for t in lesson_topics]
                )
                
                if selected_lesson_topic:
                    lesson_topic_id = int(selected_lesson_topic.split(" - ")[0])
                    lesson_topic = conn.execute("SELECT * FROM lesson_topics WHERE id = ?", (lesson_topic_id,)).fetchone()
                    
                    with st.form("edit_lesson_topic_form"):
                        new_name = st.text_input("Tên chủ đề", value=lesson_topic[1])
                        new_description = st.text_area("Mô tả", value=lesson_topic[2] or "")
                        new_thumbnail = st.text_input("URL hình ảnh đại diện", value=lesson_topic[3] or "")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("Cập nhật"):
                                try:
                                    conn.execute(
                                        "UPDATE lesson_topics SET name = ?, description = ?, thumbnail_url = ? WHERE id = ?",
                                        (new_name, new_description, new_thumbnail if new_thumbnail else None, lesson_topic_id)
                                    )
                                    conn.commit()
                                    st.success("✅ Chủ đề đã được cập nhật!")
                                except Exception as e:
                                    st.error(f"Lỗi: {str(e)}")
                        with col2:
                            if st.form_submit_button("Xóa chủ đề"):
                                try:
                                    # Kiểm tra xem có chương nào thuộc chủ đề này không
                                    chapter_count = conn.execute(
                                        "SELECT COUNT(*) FROM chapters WHERE lesson_topic_id = ?", 
                                        (lesson_topic_id,)
                                    ).fetchone()[0]
                                    
                                    if chapter_count > 0:
                                        st.error("Không thể xóa chủ đề đã có chương học! Hãy xóa các chương trước.")
                                    else:
                                        conn.execute("DELETE FROM lesson_topics WHERE id = ?", (lesson_topic_id,))
                                        conn.commit()
                                        st.success("✅ Chủ đề đã được xóa!")
                                        st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi: {str(e)}")
    
    elif operation == "Quản lý chương":
        st.subheader("📑 Quản lý chương học")
        
        # Lấy danh sách chủ đề để lọc
        lesson_topics = conn.execute("SELECT id, name FROM lesson_topics ORDER BY name").fetchall()
        selected_lesson_topic = st.selectbox(
            "Chọn chủ đề",
            [""] + [f"{t[0]} - {t[1]}" for t in lesson_topics],
            key="chapter_lesson_topic_select"
        )
        
        if selected_lesson_topic:
            lesson_topic_id = int(selected_lesson_topic.split(" - ")[0])
            
            # Tab quản lý
            tab1, tab2 = st.tabs(["Thêm chương mới", "Danh sách chương"])
            
            with tab1:
                with st.form("add_chapter_form"):
                    title = st.text_input("Tiêu đề chương*")
                    description = st.text_area("Mô tả")
                    order_num = st.number_input("Thứ tự", min_value=1, value=1)
                    
                    if st.form_submit_button("Thêm chương"):
                        if not title:
                            st.error("Vui lòng nhập tiêu đề chương")
                        else:
                            try:
                                conn.execute(
                                    "INSERT INTO chapters (lesson_topic_id, title, description, order_num) VALUES (?, ?, ?, ?)",
                                    (lesson_topic_id, title, description, order_num)
                                )
                                conn.commit()
                                st.success("✅ Chương đã được thêm thành công!")
                            except Exception as e:
                                st.error(f"Lỗi: {str(e)}")
            
            with tab2:
                chapters = conn.execute(
                    "SELECT * FROM chapters WHERE lesson_topic_id = ? ORDER BY order_num",
                    (lesson_topic_id,)
                ).fetchall()
                
                if not chapters:
                    st.info("Chưa có chương nào trong chủ đề này")
                else:
                    for chapter in chapters:
                        with st.expander(f"{chapter[3]} (Thứ tự: {chapter[4]})"):
                            st.write(f"**Mô tả:** {chapter[3] or 'Không có mô tả'}")
                            st.write(f"**Số bài học:** {conn.execute('SELECT COUNT(*) FROM lessons WHERE chapter_id = ?', (chapter[0],)).fetchone()[0]}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"Sửa chương {chapter[0]}", key=f"edit_chapter_{chapter[0]}"):
                                    st.session_state['editing_chapter'] = chapter[0]
                            with col2:
                                if st.button(f"Xóa chương {chapter[0]}", key=f"delete_chapter_{chapter[0]}"):
                                    # Kiểm tra xem có bài học nào thuộc chương này không
                                    lesson_count = conn.execute(
                                        "SELECT COUNT(*) FROM lessons WHERE chapter_id = ?", 
                                        (chapter[0],)
                                    ).fetchone()[0]
                                    
                                    if lesson_count > 0:
                                        st.error("Không thể xóa chương đã có bài học! Hãy xóa các bài học trước.")
                                    else:
                                        conn.execute("DELETE FROM chapters WHERE id = ?", (chapter[0],))
                                        conn.commit()
                                        st.success("✅ Chương đã được xóa!")
                                        st.rerun()
                    
                    # Form sửa chương
                    if 'editing_chapter' in st.session_state:
                        chapter = conn.execute(
                            "SELECT * FROM chapters WHERE id = ?",
                            (st.session_state['editing_chapter'],)
                        ).fetchone()
                        
                        with st.form("edit_chapter_form"):
                            new_title = st.text_input("Tiêu đề", value=chapter[2])
                            new_description = st.text_area("Mô tả", value=chapter[3] or "")
                            new_order = st.number_input("Thứ tự", min_value=1, value=chapter[4])
                            
                            if st.form_submit_button("Cập nhật"):
                                try:
                                    conn.execute(
                                        "UPDATE chapters SET title = ?, description = ?, order_num = ? WHERE id = ?",
                                        (new_title, new_description, new_order, chapter[0])
                                    )
                                    conn.commit()
                                    del st.session_state['editing_chapter']
                                    st.success("✅ Chương đã được cập nhật!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi: {str(e)}")
    
    elif operation == "Tạo bài học mới":
        st.subheader("🆕 Tạo bài học mới")

        # Chọn chủ đề và chương
        lesson_topics = conn.execute("SELECT id, name FROM lesson_topics ORDER BY name").fetchall()
        selected_lesson_topic = st.selectbox(
            "Chọn chủ đề*",
            [""] + [f"{t[0]} - {t[1]}" for t in lesson_topics],
            key="lesson_topic_select"
        )

        if selected_lesson_topic:
            lesson_topic_id = int(selected_lesson_topic.split(" - ")[0])
            chapters = conn.execute(
                "SELECT id, title FROM chapters WHERE lesson_topic_id = ? ORDER BY order_num",
                (lesson_topic_id,)
            ).fetchall()

            selected_chapter = st.selectbox(
                "Chọn chương*",
                [""] + [f"{c[0]} - {c[1]}" for c in chapters],
                key="lesson_chapter_select"
            )

            if selected_chapter:
                chapter_id = int(selected_chapter.split(" - ")[0])

                # Khởi tạo session state cho các khối nội dung
                if "content_blocks" not in st.session_state:
                    st.session_state.content_blocks = []

                st.markdown("### ➕ Thêm nội dung bài học")
                content_type_list = ["text", "image", "audio", "video", "pdf", "embed", "file"]  # Thêm loại "file"
                content_type = st.selectbox("Loại khối nội dung*", content_type_list)

                # Nhập nội dung theo loại
                block_value = ""
                if content_type == "text":
                    block_value = st.text_area("Nội dung văn bản*")
                elif content_type == "file":
                    # Thêm phần upload file
                    uploaded_file = st.file_uploader("Tải lên tài liệu*", type=["pdf", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip"])
                    if uploaded_file is not None:
                        # Lưu file vào thư mục uploads
                        os.makedirs("uploads", exist_ok=True)
                        file_path = os.path.join("uploads", uploaded_file.name)
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        block_value = file_path
                        st.success(f"Đã tải lên: {uploaded_file.name}")
                else:
                    block_value = st.text_input(f"URL {content_type}*")

                # Nút thêm khối nội dung
                if st.button("➕ Thêm khối nội dung"):
                    if not block_value.strip():
                        st.warning("⚠️ Vui lòng nhập nội dung trước khi thêm.")
                    else:
                        st.session_state.content_blocks.append({
                            "type": content_type,
                            "value": block_value.strip(),
                            "file_name": uploaded_file.name if content_type == "file" else None  # Lưu tên file nếu là file
                        })
                        st.success("✅ Đã thêm khối nội dung.")
                        st.rerun()

                # Hiển thị các khối nội dung đã thêm
                if st.session_state.content_blocks:
                    st.markdown("### 📄 Danh sách nội dung đã thêm")
                    for i, block in enumerate(st.session_state.content_blocks):
                        with st.expander(f"Khối {i+1}: {block['type']}"):
                            block_type = block["type"]
                            block_value = block["value"]

                            # Hiển thị theo loại nội dung
                            if block_type == "text":
                                st.write(block_value)
                            elif block_type == "image":
                                st.image(block_value, use_container_width=True)  # ✅ Cập nhật tại đây
                            elif block_type == "audio":
                                st.audio(block_value)
                            elif block_type == "video":
                                st.video(block_value)
                            elif block_type == "pdf":
                                st.components.v1.iframe(block_value, height=600, scrolling=True)
                            elif block_type == "embed":
                                st.components.v1.iframe(block_value, height=400, scrolling=True)
                            elif block_type == "file":
                                with open(block_value, "rb") as f:
                                    st.download_button(
                                        label=f"📥 Tải về {block['file_name']}",
                                        data=f,
                                        file_name=block['file_name'],
                                        mime="application/octet-stream"
                                    )
                            else:
                                st.write(f"🔗 {block_value}")

                            # Nút xoá
                            if st.button(f"🗑️ Xoá khối {i + 1}", key=f"delete_block_{i}"):
                                # Xóa file vật lý nếu là loại file
                                if block_type == "file" and os.path.exists(block_value):
                                    os.remove(block_value)
                                del st.session_state.content_blocks[i]
                                st.rerun()


                # Thiết lập bài học tương tác
                if 'is_interactive' not in st.session_state:
                    st.session_state.is_interactive = False

                is_interactive = st.checkbox(
                    "Bài học tương tác",
                    value=st.session_state.is_interactive,
                    key="interactive_checkbox"
                )

                # Form tạo bài học
                with st.form("add_lesson_form"):
                    title = st.text_input("Tiêu đề bài học*")
                    description = st.text_area("Mô tả")
                    level = st.selectbox("Độ khó", ["", "Dễ", "Trung bình", "Khó"])

                    submitted = st.form_submit_button("✅ Tạo bài học")

                    if submitted:
                        if not title:
                            st.error("Vui lòng nhập tiêu đề bài học")
                        elif not st.session_state.content_blocks:
                            st.error("Vui lòng thêm ít nhất một khối nội dung")
                        else:
                            try:
                                # Lưu bài học vào database
                                cursor = conn.execute(
                                    """
                                    INSERT INTO lessons (
                                        title, description, content, content_type,
                                        lesson_topic_id, chapter_id, level, is_interactive
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        title,
                                        description,
                                        json.dumps(st.session_state.content_blocks),
                                        "multiple",  # Loại nội dung tổng hợp
                                        lesson_topic_id,
                                        chapter_id,
                                        level if level else None,
                                        1 if is_interactive else 0
                                    )
                                )
                                lesson_id = cursor.lastrowid
                                conn.commit()

                                # Xử lý nếu là bài học tương tác
                                if is_interactive:
                                    st.session_state['adding_interactive'] = lesson_id
                                    st.session_state['interactive_type'] = None
                                    st.session_state.is_interactive = True
                                    st.rerun()
                                
                                st.success("✅ Bài học đã được tạo thành công!")
                                st.session_state.content_blocks = []  # Reset các khối nội dung
                            except Exception as e:
                                st.error(f"Lỗi khi lưu bài học: {e}")

                # Xử lý thêm nội dung tương tác nếu có
                if 'adding_interactive' in st.session_state:
                    lesson_id = st.session_state['adding_interactive']
                    
                    if 'interactive_type' not in st.session_state:
                        st.session_state.interactive_type = None
                    
                    if not st.session_state.interactive_type:
                        st.subheader("➕ Chọn loại nội dung tương tác")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            if st.button("Câu hỏi trắc nghiệm", key="select_quiz"):
                                st.session_state.interactive_type = "quiz"
                                st.rerun()
                        with col2:
                            if st.button("Flashcards", key="select_flashcard"):
                                st.session_state.interactive_type = "flashcard"
                                st.rerun()
                        with col3:
                            if st.button("Bài tập", key="select_exercise"):
                                st.session_state.interactive_type = "exercise"
                                st.rerun()
                        with col4:  # Thêm cột thứ 4
                            if st.button("Điền vào chỗ trống", key="select_fill_blank"):
                                st.session_state.interactive_type = "fill_blank"
                                st.rerun()        
                    else:
                        # Hiển thị form nhập nội dung tương tác tương ứng
                        if st.session_state.interactive_type == "quiz":
                            st.info("Thêm câu hỏi trắc nghiệm")

                            if "quiz_questions" not in st.session_state:
                                st.session_state.quiz_questions = []

                            with st.form("add_quiz_question_form"):
                                question_text = st.text_area("Câu hỏi*", key="q_text")
                                option_a = st.text_input("A", key="opt_a")
                                option_b = st.text_input("B", key="opt_b")
                                option_c = st.text_input("C", key="opt_c")
                                option_d = st.text_input("D", key="opt_d")
                                correct_answer = st.selectbox("Đáp án đúng*", ["A", "B", "C", "D"], key="correct")

                                if st.form_submit_button("➕ Thêm câu hỏi"):
                                    if not question_text or not option_a or not option_b or not option_c or not option_d:
                                        st.warning("Vui lòng nhập đầy đủ thông tin câu hỏi.")
                                    else:
                                        st.session_state.quiz_questions.append({
                                            "question": question_text,
                                            "options": {
                                                "A": option_a,
                                                "B": option_b,
                                                "C": option_c,
                                                "D": option_d
                                            },
                                            "correct": correct_answer
                                        })
                                        st.success("✅ Đã thêm câu hỏi!")

                            if st.session_state.get("quiz_questions"):
                                st.subheader("📋 Danh sách câu hỏi đã thêm")
                                for i, q in enumerate(st.session_state.quiz_questions, 1):
                                    st.markdown(f"**{i}. {q['question']}**")
                                    for opt, val in q['options'].items():
                                        st.markdown(f"- {opt}: {val}")
                                    st.markdown(f"✅ Đáp án: **{q['correct']}**")

                        elif st.session_state.interactive_type == "flashcard":
                            st.info("Thêm flashcards")

                            if "flashcards" not in st.session_state:
                                st.session_state.flashcards = []

                            with st.form("add_flashcard_form"):
                                term = st.text_input("Thuật ngữ*", key="term_input")
                                definition = st.text_area("Định nghĩa*", key="def_input")

                                if st.form_submit_button("➕ Thêm flashcard"):
                                    if not term or not definition:
                                        st.warning("Vui lòng nhập đầy đủ thuật ngữ và định nghĩa.")
                                    else:
                                        st.session_state.flashcards.append({
                                            "term": term,
                                            "definition": definition
                                        })
                                        st.success("✅ Đã thêm flashcard!")

                            if st.session_state.get("flashcards"):
                                st.subheader("📋 Danh sách flashcards đã thêm")
                                for i, card in enumerate(st.session_state.flashcards, 1):
                                    st.markdown(f"**{i}. {card['term']}**: {card['definition']}")

                        elif st.session_state.interactive_type == "exercise":
                            st.info("Thêm bài tập")

                            if "exercises" not in st.session_state:
                                st.session_state.exercises = []

                            with st.form("add_exercise_form"):
                                instruction = st.text_input("Yêu cầu*", key="ins_input")
                                content_ex = st.text_area("Nội dung bài tập*", key="ex_content_input")
                                answer = st.text_input("Đáp án (tuỳ chọn)", key="ex_ans_input")

                                if st.form_submit_button("➕ Thêm bài tập"):
                                    if not instruction or not content_ex:
                                        st.warning("Vui lòng nhập yêu cầu và nội dung bài tập.")
                                    else:
                                        st.session_state.exercises.append({
                                            "instruction": instruction,
                                            "content": content_ex,
                                            "answer": answer
                                        })
                                        st.success("✅ Đã thêm bài tập!")

                            if st.session_state.get("exercises"):
                                st.subheader("📋 Danh sách bài tập đã thêm")
                                for i, ex in enumerate(st.session_state.exercises, 1):
                                    st.markdown(f"**{i}. {ex['instruction']}**")
                                    st.code(ex["content"])
                                    if ex["answer"]:
                                        st.markdown(f"**Đáp án:** {ex['answer']}")
                        elif st.session_state.interactive_type == "fill_blank":
                            st.info("Thêm bài tập điền vào chỗ trống")

                            if "fill_blanks" not in st.session_state:
                                st.session_state.fill_blanks = []

                            with st.form("add_fill_blank_form"):
                                fb_instruction = st.text_input("Yêu cầu*", key="fb_instruction")
                                fb_content = st.text_area("Nội dung có chỗ trống (dùng ___ để đánh dấu khoảng trống)*", key="fb_content")
                                fb_answers = st.text_area("Đáp án tương ứng (phân cách bằng dấu phẩy)", key="fb_answers")

                                if st.form_submit_button("➕ Thêm bài điền chỗ trống"):
                                    if not fb_instruction or not fb_content or not fb_answers:
                                        st.warning("Vui lòng nhập đầy đủ thông tin.")
                                    else:
                                        answers = [ans.strip() for ans in fb_answers.split(",")]
                                        blanks = fb_content.count("___")
                                        if blanks != len(answers):
                                            st.warning(f"Số khoảng trống (___) là {blanks}, nhưng số đáp án là {len(answers)}.")
                                        else:
                                            st.session_state.fill_blanks.append({
                                                "instruction": fb_instruction,
                                                "content": fb_content,
                                                "answers": answers
                                            })
                                            st.success("✅ Đã thêm bài điền vào chỗ trống!")

                            if st.session_state.get("fill_blanks"):
                                st.subheader("📋 Danh sách bài điền vào chỗ trống đã thêm")
                                for i, fb in enumerate(st.session_state.fill_blanks, 1):
                                    st.markdown(f"**{i}. {fb['instruction']}**")
                                    st.code(fb["content"])
                                    st.markdown(f"**Đáp án:** {', '.join(fb['answers'])}")                

                        # Thêm nút "Quay lại" để chọn lại loại nội dung
                        if st.button("← Chọn lại loại nội dung"):
                            st.session_state.interactive_type = None
                            st.rerun()

                        # Nút lưu nội dung tương tác
                        if st.button("💾 Lưu nội dung tương tác"):
                            try:
                                if st.session_state.interactive_type == "quiz":
                                    if not st.session_state.quiz_questions:
                                        st.warning("Bạn chưa thêm câu hỏi nào.")
                                        st.stop()
                                    content_data = {"type": "quiz", "data": st.session_state.quiz_questions}

                                elif st.session_state.interactive_type == "flashcard":
                                    if not st.session_state.flashcards:
                                        st.warning("Bạn chưa thêm flashcard nào.")
                                        st.stop()
                                    content_data = {"type": "flashcard", "data": st.session_state.flashcards}

                                elif st.session_state.interactive_type == "exercise":
                                    if not st.session_state.exercises:
                                        st.warning("Bạn chưa thêm bài tập nào.")
                                        st.stop()
                                    content_data = {"type": "exercise", "data": st.session_state.exercises}
                                elif st.session_state.interactive_type == "fill_blank":
                                    if not st.session_state.fill_blanks:
                                        st.warning("Bạn chưa thêm bài nào.")
                                        st.stop()
                                    content_data = {"type": "fill_blank", "data": st.session_state.fill_blanks}    

                                # Sửa lỗi thiếu dấu đóng ngoặc ở đây
                                conn.execute(
                                    "INSERT INTO interactive_content (lesson_id, content_type, content_data) VALUES (?, ?, ?)",
                                    (lesson_id, st.session_state.interactive_type, json.dumps(content_data))
                                )
                                conn.commit()

                                # Reset các session state
                                keys_to_delete = ['adding_interactive', 'interactive_type', 
                                                 'quiz_questions', 'flashcards', 'exercises', 'fill_blanks']
                                for key in keys_to_delete:
                                    st.session_state.pop(key, None)

                                st.success("✅ Nội dung tương tác đã được thêm!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Lỗi: {str(e)}")

                        # Nút hủy bỏ
                        if st.button("❌ Hủy bỏ"):
                            keys_to_delete = ['adding_interactive', 'interactive_type', 
                                            'quiz_questions', 'flashcards', 'exercises', 'fill_blanks']
                            for key in keys_to_delete:
                                st.session_state.pop(key, None)
                            st.rerun()
                
                if st.session_state.get("content_blocks"):
                    st.markdown("---")
                    st.subheader("📚 Xem trước bài học")

                    for i, block in enumerate(st.session_state.content_blocks):
                        st.markdown(f"#### 🔹 Khối {i+1}: {block['type'].capitalize()}")
                        block_type = block["type"]
                        block_value = block["value"]

                        # Hiển thị theo loại nội dung
                        if block_type == "text":
                            st.write(block_value)
                        elif block_type == "image":
                            st.image(block_value, use_container_width=True)  # ✅ Cập nhật tại đây
                        elif block_type == "audio":
                            st.audio(block_value)
                        elif block_type == "video":
                            st.video(block_value)
                        elif block_type == "pdf":
                            st.components.v1.iframe(block_value, height=600, scrolling=True)
                        elif block_type == "embed":
                            st.components.v1.iframe(block_value, height=400, scrolling=True)
                        elif block_type == "file":
                            # Hiển thị nút tải file nếu file tồn tại
                            file_name = block.get("file_name", "tài liệu")
                            try:
                                with open(block_value, "rb") as f:
                                    st.download_button(
                                        label=f"📥 Tải về {file_name}",
                                        data=f,
                                        file_name=file_name,
                                        mime="application/octet-stream",
                                        key=f"download_button_{i}"
                                    )
                            except Exception as e:
                                st.error(f"❌ Không thể tải file: {e}")
                        else:
                            st.write(f"🔗 {block_value}")

                # Xem trước nội dung tương tác nếu có
                if st.session_state.get("interactive_type"):
                    st.markdown("### 🎮 Xem trước nội dung tương tác")

                    if st.session_state.interactive_type == "quiz":
                        for i, q in enumerate(st.session_state.get("quiz_questions", []), 1):
                            st.markdown(f"**{i}. {q['question']}**")
                            for opt, val in q['options'].items():
                                st.markdown(f"- {opt}: {val}")
                            st.markdown(f"✅ Đáp án đúng: **{q['correct']}**")

                    elif st.session_state.interactive_type == "flashcard":
                        for i, card in enumerate(st.session_state.get("flashcards", []), 1):
                            st.markdown(f"**{i}. {card['term']}** — *{card['definition']}*")

                    elif st.session_state.interactive_type == "exercise":
                        for i, ex in enumerate(st.session_state.get("exercises", []), 1):
                            st.markdown(f"**{i}. {ex['instruction']}**")
                            st.code(ex["content"])
                            if ex["answer"]:
                                st.markdown(f"✅ Đáp án: **{ex['answer']}**")

                    elif st.session_state.interactive_type == "fill_blank":
                        for i, fb in enumerate(st.session_state.get("fill_blanks", []), 1):
                            st.markdown(f"**{i}. {fb['instruction']}**")
                            st.markdown(f"📄 Nội dung: {fb['content']}")
                            st.markdown(f"✅ Đáp án: {', '.join(fb['answers'])}")    

    
    elif operation == "Quản lý bài học":
        st.subheader("📚 Quản lý bài học")
        
        # Bộ lọc nâng cao
        with st.expander("🔍 Bộ lọc nâng cao"):
            col1, col2, col3 = st.columns(3)
            with col1:
                lesson_topics = conn.execute("SELECT id, name FROM lesson_topics ORDER BY name").fetchall()
                filter_lesson_topic = st.selectbox(
                    "Chủ đề",
                    [""] + [f"{t[0]} - {t[1]}" for t in lesson_topics],
                    key="filter_topic_management"
                )
            with col2:
                if filter_lesson_topic:
                    lesson_topic_id = int(filter_lesson_topic.split(" - ")[0])
                    chapters = conn.execute(
                        "SELECT id, title FROM chapters WHERE lesson_topic_id = ? ORDER BY order_num", 
                        (lesson_topic_id,)
                    ).fetchall()
                    filter_chapter = st.selectbox(
                        "Chương",
                        [""] + [f"{c[0]} - {c[1]}" for c in chapters],
                        key="filter_chapter_management"
                    )
                else:
                    filter_chapter = st.selectbox("Chương", [""], disabled=True, key="disabled_chapter_filter")
            with col3:
                filter_level = st.selectbox(
                    "Độ khó",
                    ["", "Dễ", "Trung bình", "Khó"],
                    key="filter_level_management"
                )
        
        # Truy vấn dữ liệu bài học
        query = """
            SELECT l.id, l.title, t.name, c.title, l.content_type, l.level, 
                   l.is_interactive, l.created_at, l.content
            FROM lessons l
            LEFT JOIN lesson_topics t ON l.lesson_topic_id = t.id
            LEFT JOIN chapters c ON l.chapter_id = c.id
        """
        params = []
        conditions = []

        if filter_lesson_topic:
            lesson_topic_id = int(filter_lesson_topic.split(" - ")[0])
            conditions.append("l.lesson_topic_id = ?")
            params.append(lesson_topic_id)
            if filter_chapter:
                chapter_id = int(filter_chapter.split(" - ")[0])
                conditions.append("l.chapter_id = ?")
                params.append(chapter_id)

        if filter_level:
            conditions.append("l.level = ?")
            params.append(filter_level)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY l.created_at DESC"

        lessons = conn.execute(query, params).fetchall()

        if not lessons:
            st.info("📭 Không tìm thấy bài học nào phù hợp.")
        else:
            st.success(f"🔍 Tìm thấy {len(lessons)} bài học")
            
            for idx, lesson in enumerate(lessons):
                with st.expander(f"📖 {lesson[1]} (Chủ đề: {lesson[2]} - Chương: {lesson[3]})"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"""
                        - **Loại nội dung:** {lesson[4]}
                        - **Độ khó:** {lesson[5] or 'Chưa xác định'}
                        - **Tương tác:** {'✅ Có' if lesson[6] else '❌ Không'}
                        - **Ngày tạo:** {lesson[7]}
                        """)
                        
                        # Hiển thị xem trước nội dung với key duy nhất
                        if lesson[4] == "multiple":
                            try:
                                content_blocks = json.loads(lesson[8])
                                st.markdown("**Nội dung:**")
                                for block_idx, block in enumerate(content_blocks):
                                    if block["type"] == "text":
                                        st.text_area(
                                            "", 
                                            value=block["value"], 
                                            height=100, 
                                            disabled=True,
                                            key=f"text_block_{lesson[0]}_{block_idx}"
                                        )
                                    else:
                                        st.markdown(f"🔗 {block['type'].capitalize()}: {block['value']}")
                            except:
                                st.warning("Không thể phân tích nội dung bài học")
                        else:
                            st.text_area(
                                "Nội dung", 
                                value=lesson[8], 
                                height=100, 
                                disabled=True,
                                key=f"single_content_{lesson[0]}"
                            )
                    
                    with col2:
                        if st.button("✏️ Sửa", key=f"edit_btn_{lesson[0]}"):
                            # Lưu ID bài học đang chỉnh sửa
                            st.session_state['editing_lesson'] = lesson[0]
                            # Xóa các trạng thái cũ để tránh xung đột
                            if 'content_blocks' in st.session_state:
                                del st.session_state['content_blocks']
                            if 'is_interactive' in st.session_state:
                                del st.session_state['is_interactive']
                            # Khởi tạo content_blocks
                            try:
                                if lesson[4] == "multiple" and lesson[8]:
                                    st.session_state['content_blocks'] = json.loads(lesson[8])
                                else:
                                    st.session_state['content_blocks'] = []
                                st.session_state['current_content_type'] = lesson[4] if lesson[4] else "text"
                            except json.JSONDecodeError:
                                st.error("⚠️ Lỗi định dạng nội dung bài học!")
                                st.session_state['content_blocks'] = []
                                st.session_state['current_content_type'] = "text"
                            # Khởi tạo trạng thái tương tác
                            st.session_state['is_interactive'] = bool(lesson[6])
                            st.rerun()
                        
                        if st.button("🗑️ Xóa", key=f"delete_btn_{lesson[0]}"):
                            # Kiểm tra ràng buộc
                            interactive_count = conn.execute(
                                "SELECT COUNT(*) FROM interactive_content WHERE lesson_id = ?", 
                                (lesson[0],)
                            ).fetchone()[0]
                            progress_count = conn.execute(
                                "SELECT COUNT(*) FROM user_learning_progress WHERE lesson_id = ?", 
                                (lesson[0],)
                            ).fetchone()[0]
                            
                            if interactive_count > 0 or progress_count > 0:
                                st.error(f"⚠️ Không thể xóa bài học! Có {interactive_count} nội dung tương tác và {progress_count} tiến độ học tập liên quan.")
                            else:
                                # Xóa các file vật lý nếu có
                                if lesson[4] == "multiple" and lesson[8]:
                                    try:
                                        content_blocks = json.loads(lesson[8])
                                        for block in content_blocks:
                                            if block['type'] == "file" and 'value' in block and os.path.exists(block['value']):
                                                os.remove(block['value'])
                                    except json.JSONDecodeError:
                                        pass  # Bỏ qua nếu không phân tích được nội dung
                                # Xóa bài học
                                conn.execute("DELETE FROM lessons WHERE id = ?", (lesson[0],))
                                conn.commit()
                                st.success("✅ Đã xóa bài học thành công!")
                                st.rerun()

        # Form chỉnh sửa bài học
                # Xử lý chỉnh sửa bài học
        if 'editing_lesson' in st.session_state and st.session_state.editing_lesson:
            lesson_id = st.session_state.editing_lesson
            st.subheader("✏️ Chỉnh sửa bài học")

            # Lấy thông tin bài học hiện tại
            lesson = conn.execute(
                """
                SELECT title, description, content, content_type, lesson_topic_id, 
                       chapter_id, level, is_interactive 
                FROM lessons WHERE id = ?
                """,
                (lesson_id,)
            ).fetchone()

            if not lesson:
                st.error("Không tìm thấy bài học!")
                st.session_state.pop('editing_lesson', None)
                st.rerun()

            # Chọn chủ đề và chương
            lesson_topics = conn.execute("SELECT id, name FROM lesson_topics ORDER BY name").fetchall()
            selected_lesson_topic = st.selectbox(
                "Chọn chủ đề*",
                [""] + [f"{t[0]} - {t[1]}" for t in lesson_topics],
                index=[t[0] for t in lesson_topics].index(lesson[4]) + 1 if lesson[4] else 0,
                key=f"edit_lesson_topic_select_{lesson_id}"
            )

            if selected_lesson_topic:
                lesson_topic_id = int(selected_lesson_topic.split(" - ")[0])
                chapters = conn.execute(
                    "SELECT id, title FROM chapters WHERE lesson_topic_id = ? ORDER BY order_num",
                    (lesson_topic_id,)
                ).fetchall()

                selected_chapter = st.selectbox(
                    "Chọn chương*",
                    [""] + [f"{c[0]} - {c[1]}" for c in chapters],
                    index=[c[0] for c in chapters].index(lesson[5]) + 1 if lesson[5] else 0,
                    key=f"edit_lesson_chapter_select_{lesson_id}"
                )

                if selected_chapter:
                    chapter_id = int(selected_chapter.split(" - ")[0])

                    # Thêm khối nội dung mới
                    st.markdown("### ➕ Thêm nội dung bài học")
                    content_type_list = ["text", "image", "audio", "video", "pdf", "embed", "file"]
                    content_type = st.selectbox("Loại khối nội dung*", content_type_list, key=f"content_type_{lesson_id}")

                    block_value = ""
                    uploaded_file = None
                    if content_type == "text":
                        block_value = st.text_area("Nội dung văn bản*", key=f"text_area_{lesson_id}")
                    elif content_type == "file":
                        uploaded_file = st.file_uploader(
                            "Tải lên tài liệu*", 
                            type=["pdf", "docx", "ppt", "pptx", "xls", "xlsx", "txt", "zip"],
                            key=f"file_uploader_{lesson_id}"
                        )
                        if uploaded_file is not None:
                            os.makedirs("uploads", exist_ok=True)
                            file_path = os.path.join("uploads", uploaded_file.name)
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            block_value = file_path
                            st.success(f"Đã tải lên: {uploaded_file.name}")
                    else:
                        block_value = st.text_input(f"URL {content_type}*", key=f"url_input_{lesson_id}")

                    if st.button("➕ Thêm khối nội dung", key=f"add_block_{lesson_id}"):
                        if not block_value.strip():
                            st.warning("⚠️ Vui lòng nhập nội dung trước khi thêm.")
                        else:
                            st.session_state.content_blocks.append({
                                "type": content_type,
                                "value": block_value.strip(),
                                "file_name": uploaded_file.name if content_type == "file" else None
                            })
                            st.success("✅ Đã thêm khối nội dung.")
                            st.rerun()

                    # Hiển thị các khối nội dung đã thêm
                    if st.session_state.content_blocks:
                        st.markdown("### 📄 Danh sách nội dung đã thêm")
                        for i, block in enumerate(st.session_state.content_blocks):
                            with st.expander(f"Khối {i+1}: {block['type']}"):
                                block_type = block["type"]
                                block_value = block["value"]

                                if block_type == "text":
                                    st.write(block_value)
                                elif block_type == "image":
                                    st.image(block_value, use_container_width=True)
                                elif block_type == "audio":
                                    st.audio(block_value)
                                elif block_type == "video":
                                    st.video(block_value)
                                elif block_type == "pdf":
                                    st.components.v1.iframe(block_value, height=600, scrolling=True)
                                elif block_type == "embed":
                                    st.components.v1.iframe(block_value, height=400, scrolling=True)
                                elif block_type == "file":
                                    try:
                                        with open(block_value, "rb") as f:
                                            st.download_button(
                                                label=f"📥 Tải về {block['file_name']}",
                                                data=f,
                                                file_name=block['file_name'],
                                                mime="application/octet-stream",
                                                key=f"download_block_{lesson_id}_{i}"
                                            )
                                    except:
                                        st.error(f"Không thể tải file: {block['file_name']}")
                                else:
                                    st.write(f"🔗 {block_value}")

                                if st.button(f"🗑️ Xoá khối {i + 1}", key=f"edit_delete_block_{lesson_id}_{i}"):
                                    if block_type == "file" and os.path.exists(block_value):
                                        os.remove(block_value)
                                    del st.session_state.content_blocks[i]
                                    st.rerun()

                    # Thiết lập bài học tương tác
                    if 'is_interactive' not in st.session_state:
                        st.session_state.is_interactive = bool(lesson[7])

                    is_interactive = st.checkbox(
                        "Bài học tương tác",
                        value=st.session_state.is_interactive,
                        key=f"edit_interactive_checkbox_{lesson_id}"
                    )

                    # Form chỉnh sửa bài học
                    with st.form(f"edit_lesson_form_{lesson_id}"):
                        title = st.text_input("Tiêu đề bài học*", value=lesson[0], key=f"title_{lesson_id}")
                        description = st.text_area("Mô tả", value=lesson[1] or "", key=f"description_{lesson_id}")
                        level = st.selectbox(
                            "Độ khó", 
                            ["", "Dễ", "Trung bình", "Khó"], 
                            index=["", "Dễ", "Trung bình", "Khó"].index(lesson[6]) if lesson[6] else 0,
                            key=f"level_{lesson_id}"
                        )

                        submitted = st.form_submit_button("💾 Cập nhật bài học")

                        if submitted:
                            if not title:
                                st.error("Vui lòng nhập tiêu đề bài học")
                            elif not st.session_state.content_blocks:
                                st.error("Vui lòng thêm ít nhất một khối nội dung")
                            else:
                                try:
                                    conn.execute(
                                        """
                                        UPDATE lessons SET
                                            title = ?, description = ?, content = ?, content_type = ?,
                                            lesson_topic_id = ?, chapter_id = ?, level = ?, is_interactive = ?
                                        WHERE id = ?
                                        """,
                                        (
                                            title,
                                            description,
                                            json.dumps(st.session_state.content_blocks),
                                            "multiple",
                                            lesson_topic_id,
                                            chapter_id,
                                            level if level else None,
                                            1 if is_interactive else 0,
                                            lesson_id
                                        )
                                    )
                                    conn.commit()
                                    st.success("✅ Bài học đã được cập nhật thành công!")
                                    if is_interactive:
                                        st.session_state['editing_interactive'] = lesson_id
                                    else:
                                        st.session_state.content_blocks = []
                                        st.session_state.pop('editing_interactive', None)
                                        st.session_state.pop('editing_lesson', None)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi khi cập nhật bài học: {e}")

                    # Xử lý chỉnh sửa nội dung tương tác
                    if 'editing_interactive' in st.session_state and st.session_state.editing_interactive == lesson_id:
                        interactive_content = conn.execute(
                            "SELECT content_type, content_data FROM interactive_content WHERE lesson_id = ?",
                            (lesson_id,)
                        ).fetchone()

                        if interactive_content:
                            content_type, content_data = interactive_content
                            content_data = json.loads(content_data) if content_data else {"type": content_type, "data": []}
                        else:
                            content_type = None
                            content_data = {"type": None, "data": []}

                        if 'interactive_type' not in st.session_state:
                            st.session_state.interactive_type = content_type

                        if not st.session_state.interactive_type:
                            st.subheader("➕ Chọn loại nội dung tương tác")
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                if st.button("Câu hỏi trắc nghiệm", key=f"edit_select_quiz_{lesson_id}"):
                                    st.session_state.interactive_type = "quiz"
                                    st.session_state.quiz_questions = content_data["data"] if content_type == "quiz" else []
                                    st.rerun()
                            with col2:
                                if st.button("Flashcards", key=f"edit_select_flashcard_{lesson_id}"):
                                    st.session_state.interactive_type = "flashcard"
                                    st.session_state.flashcards = content_data["data"] if content_type == "flashcard" else []
                                    st.rerun()
                            with col3:
                                if st.button("Bài tập", key=f"edit_select_exercise_{lesson_id}"):
                                    st.session_state.interactive_type = "exercise"
                                    st.session_state.exercises = content_data["data"] if content_type == "exercise" else []
                                    st.rerun()
                            with col4:
                                if st.button("Điền vào chỗ trống", key=f"edit_select_fill_blank_{lesson_id}"):
                                    st.session_state.interactive_type = "fill_blank"
                                    st.session_state.fill_blanks = content_data["data"] if content_type == "fill_blank" else []
                                    st.rerun()
                        else:
                            if st.session_state.interactive_type == "quiz":
                                if "quiz_questions" not in st.session_state:
                                    st.session_state.quiz_questions = content_data["data"] if content_type == "quiz" else []

                                st.info("Chỉnh sửa câu hỏi trắc nghiệm")
                                with st.form(f"edit_quiz_question_form_{lesson_id}"):
                                    question_text = st.text_area("Câu hỏi*", key=f"edit_q_text_{lesson_id}")
                                    option_a = st.text_input("A", key=f"edit_opt_a_{lesson_id}")
                                    option_b = st.text_input("B", key=f"edit_opt_b_{lesson_id}")
                                    option_c = st.text_input("C", key=f"edit_opt_c_{lesson_id}")
                                    option_d = st.text_input("D", key=f"edit_opt_d_{lesson_id}")
                                    correct_answer = st.selectbox(
                                        "Đáp án đúng*", 
                                        ["A", "B", "C", "D"], 
                                        key=f"edit_correct_{lesson_id}"
                                    )

                                    if st.form_submit_button("➕ Thêm câu hỏi"):
                                        if not question_text or not option_a or not option_b or not option_c or not option_d:
                                            st.warning("Vui lòng nhập đầy đủ thông tin câu hỏi.")
                                        else:
                                            st.session_state.quiz_questions.append({
                                                "question": question_text,
                                                "options": {
                                                    "A": option_a,
                                                    "B": option_b,
                                                    "C": option_c,
                                                    "D": option_d
                                                },
                                                "correct": correct_answer
                                            })
                                            st.success("✅ Đã thêm câu hỏi!")
                                            st.rerun()

                                if st.session_state.quiz_questions:
                                    st.subheader("📋 Danh sách câu hỏi đã thêm")
                                    for i, q in enumerate(st.session_state.quiz_questions, 1):
                                        with st.expander(f"Câu hỏi {i}: {q['question'][:50]}..."):
                                            st.markdown(f"**{q['question']}**")
                                            for opt, val in q['options'].items():
                                                st.markdown(f"- {opt}: {val}")
                                            st.markdown(f"✅ Đáp án: **{q['correct']}**")
                                            if st.button(f"🗑️ Xoá câu hỏi {i}", key=f"delete_quiz_{lesson_id}_{i}"):
                                                del st.session_state.quiz_questions[i-1]
                                                st.rerun()

                            elif st.session_state.interactive_type == "flashcard":
                                if "flashcards" not in st.session_state:
                                    st.session_state.flashcards = content_data["data"] if content_type == "flashcard" else []

                                st.info("Chỉnh sửa flashcards")
                                with st.form(f"edit_flashcard_form_{lesson_id}"):
                                    term = st.text_input("Thuật ngữ*", key=f"edit_term_input_{lesson_id}")
                                    definition = st.text_area("Định nghĩa*", key=f"edit_def_input_{lesson_id}")

                                    if st.form_submit_button("➕ Thêm flashcard"):
                                        if not term or not definition:
                                            st.warning("Vui lòng nhập đầy đủ thuật ngữ và định nghĩa.")
                                        else:
                                            st.session_state.flashcards.append({
                                                "term": term,
                                                "definition": definition
                                            })
                                            st.success("✅ Đã thêm flashcard!")
                                            st.rerun()

                                if st.session_state.flashcards:
                                    st.subheader("📋 Danh sách flashcards đã thêm")
                                    for i, card in enumerate(st.session_state.flashcards, 1):
                                        with st.expander(f"Flashcard {i}: {card['term']}", key=f"flashcard_expander_{lesson_id}_{i}"):
                                            st.markdown(f"**{card['term']}**: {card['definition']}")
                                            if st.button(f"🗑️ Xoá flashcard {i}", key=f"delete_flashcard_{lesson_id}_{i}"):
                                                del st.session_state.flashcards[i-1]
                                                st.rerun()

                            elif st.session_state.interactive_type == "exercise":
                                if "exercises" not in st.session_state:
                                    st.session_state.exercises = content_data["data"] if content_type == "exercise" else []

                                st.info("Chỉnh sửa bài tập")
                                with st.form(f"edit_exercise_form_{lesson_id}"):
                                    instruction = st.text_input("Yêu cầu*", key=f"edit_ins_input_{lesson_id}")
                                    content_ex = st.text_area("Nội dung bài tập*", key=f"edit_ex_content_input_{lesson_id}")
                                    answer = st.text_input("Đáp án (tuỳ chọn)", key=f"edit_ex_ans_input_{lesson_id}")

                                    if st.form_submit_button("➕ Thêm bài tập"):
                                        if not instruction or not content_ex:
                                            st.warning("Vui lòng nhập yêu cầu và nội dung bài tập.")
                                        else:
                                            st.session_state.exercises.append({
                                                "instruction": instruction,
                                                "content": content_ex,
                                                "answer": answer
                                            })
                                            st.success("✅ Đã thêm bài tập!")
                                            st.rerun()

                                if st.session_state.exercises:
                                    st.subheader("📋 Danh sách bài tập đã thêm")
                                    for i, ex in enumerate(st.session_state.exercises, 1):
                                        with st.expander(f"Bài tập {i}: {ex['instruction'][:50]}...", key=f"exercise_expander_{lesson_id}_{i}"):
                                            st.markdown(f"**{ex['instruction']}**")
                                            st.code(ex["content"])
                                            if ex["answer"]:
                                                st.markdown(f"**Đáp án:** {ex['answer']}")
                                            if st.button(f"🗑️ Xoá bài tập {i}", key=f"delete_exercise_{lesson_id}_{i}"):
                                                del st.session_state.exercises[i-1]
                                                st.rerun()

                            elif st.session_state.interactive_type == "fill_blank":
                                if "fill_blanks" not in st.session_state:
                                    st.session_state.fill_blanks = content_data["data"] if content_type == "fill_blank" else []

                                st.info("Chỉnh sửa bài tập điền vào chỗ trống")
                                with st.form(f"edit_fill_blank_form_{lesson_id}"):
                                    fb_instruction = st.text_input("Yêu cầu*", key=f"edit_fb_instruction_{lesson_id}")
                                    fb_content = st.text_area(
                                        "Nội dung có chỗ trống (dùng ___ để đánh dấu khoảng trống)*", 
                                        key=f"edit_fb_content_{lesson_id}"
                                    )
                                    fb_answers = st.text_area(
                                        "Đáp án tương ứng (phân cách bằng dấu phẩy)", 
                                        key=f"edit_fb_answers_{lesson_id}"
                                    )

                                    if st.form_submit_button("➕ Thêm bài điền chỗ trống"):
                                        if not fb_instruction or not fb_content or not fb_answers:
                                            st.warning("Vui lòng nhập đầy đủ thông tin.")
                                        else:
                                            answers = [ans.strip() for ans in fb_answers.split(",")]
                                            blanks = fb_content.count("___")
                                            if blanks != len(answers):
                                                st.warning(f"Số khoảng trống (___) là {blanks}, nhưng số đáp án là {len(answers)}.")
                                            else:
                                                st.session_state.fill_blanks.append({
                                                    "instruction": fb_instruction,
                                                    "content": fb_content,
                                                    "answers": answers
                                                })
                                                st.success("✅ Đã thêm bài điền vào chỗ trống!")
                                                st.rerun()

                                if st.session_state.fill_blanks:
                                    st.subheader("📋 Danh sách bài điền vào chỗ trống đã thêm")
                                    for i, fb in enumerate(st.session_state.fill_blanks, 1):
                                        with st.expander(f"Bài {i}: {fb['instruction'][:50]}..."):
                                            st.markdown(f"**{fb['instruction']}**")
                                            st.code(fb["content"])
                                            st.markdown(f"**Đáp án:** {', '.join(fb['answers'])}")
                                            if st.button(f"🗑️ Xoá bài {i}", key=f"delete_fill_blank_{lesson_id}_{i}"):
                                                del st.session_state.fill_blanks[i-1]
                                                st.rerun()

                            if st.button("← Chọn lại loại nội dung", key=f"back_to_type_{lesson_id}"):
                                st.session_state.interactive_type = None
                                st.rerun()

                            if st.button("💾 Lưu nội dung tương tác", key=f"save_interactive_{lesson_id}"):
                                try:
                                    if st.session_state.interactive_type == "quiz":
                                        if not st.session_state.quiz_questions:
                                            st.warning("Bạn chưa thêm câu hỏi nào.")
                                            st.stop()
                                        content_data = {"type": "quiz", "data": st.session_state.quiz_questions}

                                    elif st.session_state.interactive_type == "flashcard":
                                        if not st.session_state.flashcards:
                                            st.warning("Bạn chưa thêm flashcard nào.")
                                            st.stop()
                                        content_data = {"type": "flashcard", "data": st.session_state.flashcards}

                                    elif st.session_state.interactive_type == "exercise":
                                        if not st.session_state.exercises:
                                            st.warning("Bạn chưa thêm bài tập nào.")
                                            st.stop()
                                        content_data = {"type": "exercise", "data": st.session_state.exercises}

                                    elif st.session_state.interactive_type == "fill_blank":
                                        if not st.session_state.fill_blanks:
                                            st.warning("Bạn chưa thêm bài nào.")
                                            st.stop()
                                        content_data = {"type": "fill_blank", "data": st.session_state.fill_blanks}

                                    conn.execute("DELETE FROM interactive_content WHERE lesson_id = ?", (lesson_id,))
                                    conn.execute(
                                        "INSERT INTO interactive_content (lesson_id, content_type, content_data) VALUES (?, ?, ?)",
                                        (lesson_id, st.session_state.interactive_type, json.dumps(content_data))
                                    )
                                    conn.commit()

                                    keys_to_delete = ['editing_interactive', 'interactive_type', 
                                                    'quiz_questions', 'flashcards', 'exercises', 'fill_blanks']
                                    for key in keys_to_delete:
                                        st.session_state.pop(key, None)

                                    st.success("✅ Nội dung tương tác đã được cập nhật!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Lỗi: {str(e)}")

                            if st.button("❌ Hủy bỏ", key=f"cancel_interactive_{lesson_id}"):
                                keys_to_delete = ['editing_interactive', 'interactive_type', 
                                                'quiz_questions', 'flashcards', 'exercises', 'fill_blanks']
                                for key in keys_to_delete:
                                    st.session_state.pop(key, None)
                                st.rerun()

                    # Xem trước bài học
                    if st.session_state.content_blocks:
                        st.markdown("---")
                        st.subheader("📚 Xem trước bài học")
                        for i, block in enumerate(st.session_state.content_blocks):
                            st.markdown(f"#### 🔹 Khối {i+1}: {block['type'].capitalize()}")
                            block_type = block["type"]
                            block_value = block["value"]

                            if block_type == "text":
                                st.write(block_value)
                            elif block_type == "image":
                                st.image(block_value, use_container_width=True)
                            elif block_type == "audio":
                                st.audio(block_value)
                            elif block_type == "video":
                                st.video(block_value)
                            elif block_type == "pdf":
                                st.components.v1.iframe(block_value, height=600, scrolling=True)
                            elif block_type == "embed":
                                st.components.v1.iframe(block_value, height=400, scrolling=True)
                            elif block_type == "file":
                                file_name = block.get("file_name", "tài liệu")
                                try:
                                    with open(block_value, "rb") as f:
                                        st.download_button(
                                            label=f"📥 Tải về {file_name}",
                                            data=f,
                                            file_name=file_name,
                                            mime="application/octet-stream",
                                            key=f"edit_download_button_{lesson_id}_{i}"
                                        )
                                except Exception as e:
                                    st.error(f"❌ Không thể tải file: {e}")
                            else:
                                st.write(f"🔗 {block_value}")

                    # Xem trước nội dung tương tác
                    if st.session_state.get("interactive_type"):
                        st.markdown("### 🎮 Xem trước nội dung tương tác")
                        if st.session_state.interactive_type == "quiz":
                            for i, q in enumerate(st.session_state.get("quiz_questions", []), 1):
                                st.markdown(f"**{i}. {q['question']}**")
                                for opt, val in q['options'].items():
                                    st.markdown(f"- {opt}: {val}")
                                st.markdown(f"✅ Đáp án đúng: **{q['correct']}**")

                        elif st.session_state.interactive_type == "flashcard":
                            for i, card in enumerate(st.session_state.get("flashcards", []), 1):
                                st.markdown(f"**{i}. {card['term']}** — *{card['definition']}*")

                        elif st.session_state.interactive_type == "exercise":
                            for i, ex in enumerate(st.session_state.get("exercises", []), 1):
                                st.markdown(f"**{i}. {ex['instruction']}**")
                                st.code(ex["content"])
                                if ex["answer"]:
                                    st.markdown(f"✅ Đáp án: **{ex['answer']}**")

                        elif st.session_state.interactive_type == "fill_blank":
                            for i, fb in enumerate(st.session_state.get("fill_blanks", []), 1):
                                st.markdown(f"**{i}. {fb['instruction']}**")
                                st.markdown(f"📄 Nội dung: {fb['content']}")
                                st.markdown(f"✅ Đáp án: {', '.join(fb['answers'])}")
    
    elif operation == "Tìm kiếm nâng cao":
        st.subheader("🔍 Tìm kiếm nâng cao")
        
        search_query = st.text_input("Từ khóa tìm kiếm")
        
        col1, col2 = st.columns(2)
        with col1:
            search_type = st.selectbox(
                "Tìm theo",
                ["Tiêu đề", "Nội dung", "Mô tả", "Tất cả"]
            )
        with col2:
            content_type_filter = st.multiselect(
                "Loại nội dung",
                ["text", "image", "audio", "video", "pdf", "embed"]
            )
        
        if st.button("Tìm kiếm"):
            if not search_query:
                st.warning("Vui lòng nhập từ khóa tìm kiếm")
            else:
                query = """
                    SELECT l.id, l.title, t.name as lesson_topic, c.title as chapter, 
                           l.content_type, l.level, l.created_at
                    FROM lessons l
                    LEFT JOIN lesson_topics t ON l.lesson_topic_id = t.id
                    LEFT JOIN chapters c ON l.chapter_id = c.id
                    WHERE (
                """
                
                params = [f"%{search_query}%"]
                
                if search_type == "Tiêu đề" or search_type == "Tất cả":
                    query += " l.title LIKE ? OR"
                if search_type == "Nội dung" or search_type == "Tất cả":
                    query += " l.content LIKE ? OR"
                if search_type == "Mô tả" or search_type == "Tất cả":
                    query += " l.description LIKE ? OR"
                
                # Bỏ OR cuối cùng
                query = query[:-3] + ")"
                
                # Thêm điều kiện loại nội dung nếu có
                if content_type_filter:
                    query += " AND l.content_type IN (" + ",".join(["?"]*len(content_type_filter)) + ")"
                    params.extend(content_type_filter)
                
                query += " ORDER BY l.created_at DESC"
                
                # Thực hiện tìm kiếm
                results = conn.execute(query, params).fetchall()
                
                if not results:
                    st.info("Không tìm thấy kết quả phù hợp")
                else:
                    st.write(f"Tìm thấy {len(results)} kết quả")
                    
                    for result in results:
                        with st.expander(f"{result[1]} ({result[2]} - {result[3]})"):
                            st.write(f"**Loại nội dung:** {result[4]}")
                            st.write(f"**Độ khó:** {result[5] or 'Không xác định'}")
                            st.write(f"**Ngày tạo:** {result[6]}")
    
    conn.close()      
    

# Chức năng quản lý phần quà (dành cho admin)
elif option == "🎁 Quản lý phần quà" and st.session_state.user['role'] == 'admin':
    st.title("🎁 Quản lý phần quà")
    conn = get_connection()
    
    action = st.radio("Chọn thao tác", ["Danh sách phần quà", "Thêm phần quà", "Xóa phần quà"])
    
    if action == "Danh sách phần quà":
        rewards = get_rewards(conn)
        
        if rewards:
            st.write("### Danh sách phần quà")
            for reward in rewards:
                st.markdown(f"""
                <div class="reward-item">
                    <b>{reward[1]}</b> (Giá: {reward[3]} sticker)
                    <p>{reward[2]}</p>
                    <small>Còn lại: {reward[4]}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Chưa có phần quà nào")
    
    elif action == "Thêm phần quà":
        st.write("### Thêm phần quà mới")
        name = st.text_input("Tên phần quà")
        description = st.text_area("Mô tả")
        sticker_cost = st.number_input("Giá (số sticker)", min_value=1)
        stock = st.number_input("Số lượng", min_value=1)
        
        if st.button("Thêm phần quà"):
            add_reward(conn, name, description, sticker_cost, stock)
            st.success("Đã thêm phần quà mới!")
    
    elif action == "Xóa phần quà":
        st.write("### Xóa phần quà")

        rewards = get_rewards(conn)
        if not rewards:
            st.warning("Hiện chưa có phần quà nào để xóa.")
        else:
            # Tạo danh sách hiển thị: "ID - Tên"
            reward_options = [f"{r[0]} - {r[1]}" for r in rewards]
            selected = st.selectbox("Chọn phần quà cần xóa", reward_options)

            # Tách lấy reward_id từ chuỗi "ID - Tên"
            reward_id = int(selected.split(" - ")[0])

            if st.button("❌ Xóa phần quà"):
                delete_reward(conn, reward_id)
                st.success(f"✅ Đã xóa phần quà: {selected}")
    
    conn.close()
    
# Chức năng quản lý người dùng (dành cho admin)
elif option == "🎁 Quản lý sticker người dùng":
    st.subheader("🎁 Quản lý sticker của người dùng")

    users = get_all_users(conn)
    usernames = [user[1] for user in users]
    selected_username = st.selectbox("Chọn người dùng:", usernames)

    selected_user = next(user for user in users if user[1] == selected_username)
    current_stickers = get_stickers(conn, selected_user[0])
    st.info(f"👤 Người dùng: **{selected_username}** - 🎫 Sticker hiện tại: **{current_stickers}**")

    col1, col2 = st.columns(2)
    with col1:
        new_sticker_count = st.number_input("🔢 Nhập số sticker mới:", min_value=0, value=current_stickers)
        if st.button("✅ Cập nhật sticker"):
            update_stickers(conn, selected_user[0], new_sticker_count)
            st.success(f"🎉 Đã cập nhật sticker cho {selected_username} thành {new_sticker_count}")

    with col2:
        amount = st.number_input("➕➖ Cộng / Trừ sticker:", value=0)
        if st.button("🔄 Áp dụng thay đổi (+/-)"):
            updated_value = max(0, current_stickers + amount)
            update_stickers(conn, selected_user[0], updated_value)
            st.success(f"🎉 Sticker mới của {selected_username} là {updated_value}")    

# Chức năng làm bài thi trắc nghiệm
elif option == "📝 Làm bài thi trắc nghiệm":
    if 'user' not in st.session_state:
        st.warning("Vui lòng đăng nhập trước khi làm bài thi.")
        st.stop()

    if 'current_screen' not in st.session_state:
        st.session_state['current_screen'] = 'setup'
        st.session_state['submitted'] = False
        st.session_state['num_questions'] = 20  # Giá trị mặc định

    conn = get_connection()
    screen = st.session_state['current_screen']

    if screen == 'setup':
        st.title("📝 Thiết lập bài thi")

        # Lấy danh sách chủ đề
        topics = get_topics(conn)
        selected_topic = st.selectbox("📚 Chọn chủ đề", topics, key="select_topic")

        # Lấy danh sách level theo chủ đề đã chọn
        levels = get_levels_by_topic(conn, selected_topic) if selected_topic else []
        selected_level = st.selectbox("🎯 Chọn độ khó", levels, key="select_level")

        # Checkbox chọn dùng mã đề hay không
        use_exam_code = st.checkbox("Chọn theo mã đề", key="checkbox_exam_code")

        selected_code = None
        if use_exam_code and selected_level:
            # Lấy danh sách mã đề theo topic và level đã chọn
            codes = get_exam_codes_by_topic_level(conn, selected_topic, selected_level)
            if codes:
                selected_code = st.selectbox("🔢 Chọn mã đề", codes, key="select_exam_code")
            else:
                st.warning("Không có mã đề nào cho chủ đề và độ khó này.")

        num_questions = st.slider("📝 Số câu hỏi", 5, 60, 20, key="num_questions_slider")
        duration_minutes = st.slider("⏰ Thời gian làm bài (phút)", 20, 60, 20, key="duration_slider")

        if st.button("🚀 Bắt đầu làm bài"):
            # ✅ Nếu không chọn mã đề thì truyền None
            questions = get_questions(
                conn, 
                selected_topic, 
                selected_level, 
                selected_code if use_exam_code else None, 
                num_questions
            )
            if not questions:
                st.error("Không đủ câu hỏi theo yêu cầu!")
            else:
                st.session_state.update({
                    'questions': questions,
                    'answers': [None] * len(questions),
                    'start_time': datetime.now(),
                    'end_time': datetime.now() + timedelta(minutes=duration_minutes),
                    'selected_topic': selected_topic,
                    'selected_level': selected_level,
                    'exam_code': selected_code if use_exam_code else None,
                    'num_questions': num_questions,
                    'current_screen': 'quiz',
                    'submitted': False
                })
                st.rerun()


    elif screen == 'quiz' and not st.session_state.get('submitted', False):
        st.title("📝 Làm bài thi")
        
        # Kiểm tra thời gian
        now = datetime.now()
        time_left = st.session_state['end_time'] - now

        if time_left.total_seconds() <= 0:
            st.warning("⏰ Hết giờ! Bài đã được tự động nộp.")
            st.session_state['submitted'] = True
            st.rerun()

        # Thêm JavaScript để tự động reload khi hết giờ
        st.components.v1.html(
            f"""
            <script>
            setTimeout(function() {{
                window.location.href = window.location.href;
            }}, {int(time_left.total_seconds() * 1000)});
            </script>
            """,
            height=0
        )

        # Hiển thị thông tin bài thi
        exam_info = f"""
        **Chủ đề:** {st.session_state['selected_topic']}  
        **Độ khó:** {st.session_state['selected_level']}  
        **Số câu:** {st.session_state['num_questions']}
        """
        if st.session_state['exam_code']:
            exam_info += f"**Mã đề:** {st.session_state['exam_code']}\n"
        st.markdown(exam_info)

        # Tạo placeholder cho đồng hồ
        time_placeholder = st.empty()
        
        # Hàm cập nhật đồng hồ
        def update_timer():
            now = datetime.now()
            time_left = st.session_state['end_time'] - now
            minutes, seconds = divmod(int(time_left.total_seconds()), 60)
            answered = sum(1 for ans in st.session_state['answers'] if ans is not None)
            
            time_placeholder.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; margin-bottom: 20px;">
                    <div style="background: #f0f2f6; padding: 10px 15px; border-radius: 10px;">
                        📝 Đã làm: {answered}/{len(st.session_state['questions'])}
                    </div>
                    <div style="background: #ff4b4b; color: white; padding: 10px 15px; border-radius: 10px;">
                        ⏳ Còn lại: {minutes:02d}:{seconds:02d}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

        # Cập nhật đồng hồ lần đầu
        update_timer()

        # Sử dụng st_autorefresh để tự động cập nhật mỗi giây
        from streamlit_autorefresh import st_autorefresh
        timer = st_autorefresh(interval=1000, key="timer_refresh")

        # Cập nhật lại đồng hồ mỗi khi autorefresh chạy
        if timer:
            update_timer()

        # Hiển thị các câu hỏi
        for idx, q in enumerate(st.session_state['questions']):
            with st.container():
                st.markdown(f"<div class='question-block'>", unsafe_allow_html=True)
                st.markdown(f"**Câu {idx+1}:** {q[0]}")

                options = [f"A. {q[1]}", f"B. {q[2]}", f"C. {q[3]}", f"D. {q[4]}"]
                if q[5]:  # answer_e
                    options.append(f"E. {q[5]}")

                selected = st.radio(
                    "Chọn đáp án:",
                    options,
                    index=None if st.session_state['answers'][idx] is None
                    else ["A", "B", "C", "D", "E"].index(st.session_state['answers'][idx]),
                    key=f"q_{idx}"
                )

                if selected is not None:
                    st.session_state['answers'][idx] = selected[0]

                st.markdown("</div>", unsafe_allow_html=True)

        # Nút nộp bài và về trang chủ
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("🏠 Về trang chủ"):
                user = st.session_state.get('user')
                keys_to_keep = {'user'}
                for key in list(st.session_state.keys()):
                    if key not in keys_to_keep:
                        del st.session_state[key]
                st.session_state['user'] = user
                st.session_state['current_screen'] = 'setup'
                st.rerun()
        with col2:
            if st.button("✅ Nộp bài"):
                unanswered = [i+1 for i, ans in enumerate(st.session_state['answers']) if ans is None]
                if unanswered:
                    st.warning(f"⚠️ Bạn chưa trả lời các câu hỏi số: {', '.join(map(str, unanswered))}")
                else:
                    st.session_state['submitted'] = True
                    st.session_state['current_screen'] = 'result'
                    st.rerun()

    elif screen == 'result' or st.session_state.get('submitted', False):
        st.title("📊 Kết quả bài thi")

        correct = 0
        results = []

        for idx, q in enumerate(st.session_state['questions']):
            user_answer = st.session_state['answers'][idx]
            correct_answer = q[6]

            is_correct = user_answer and correct_answer and user_answer.strip().upper() == correct_answer.strip().upper()
            if is_correct:
                correct += 1

            options = {}
            for i, key in enumerate(['A', 'B', 'C', 'D', 'E']):
                option_text = q[i + 1]  # Từ q[1] đến q[5]
                if option_text:  # Chỉ thêm nếu không rỗng
                    options[key] = option_text

            results.append({
                'question': q[0],
                'options': options,
                'user_answer': user_answer,
                'correct_answer': correct_answer,
                'is_correct': is_correct,
                'explanation': q[7]
            })

        percentage = (correct / len(st.session_state['questions'])) * 100

        result_text = f"""
        🎉 Kết quả: **{correct}/{len(st.session_state['questions'])}** câu đúng ({percentage:.1f}%)  
        ⏱ Thời gian làm bài: **{int((datetime.now() - st.session_state['start_time']).total_seconds())}** giây
        """
        if st.session_state['exam_code']:
            result_text += f"\n🔢 Mã đề: **{st.session_state['exam_code']}**"

        st.success(result_text)

        # Khởi tạo biến trạng thái nếu chưa có
        if 'reward_received' not in st.session_state:
            st.session_state['reward_received'] = False
        
        # Xử lý phần thưởng
        rewards = get_rewards(conn)
        if percentage == 100:
            if not st.session_state.get('added_sticker_for_100', False):
                add_stickers(conn, st.session_state.user['id'], 1)
                st.session_state['added_sticker_for_100'] = True

            rewards_eligible = [r for r in rewards if r[3] == 1 and r[4] > 0]  # sticker_cost == 1 và còn hàng

            if rewards_eligible:
                st.balloons()
                st.success("🎉 Chúc mừng! Bạn đã đạt 100% điểm và được chọn 1 phần quà trong 3 phần ngẫu nhiên!")

                sample_rewards = random.sample(rewards_eligible, min(3, len(rewards_eligible)))
                reward_names = [r[1] for r in sample_rewards]
                selected_reward_name = st.radio("🎁 Chọn phần quà bạn muốn nhận:", reward_names)

                if not st.session_state['reward_received']:
                    if st.button("🎉 Nhận phần quà"):
                        selected_reward = next((r for r in sample_rewards if r[1] == selected_reward_name), None)
                        if selected_reward:
                            success, message = redeem_reward(conn, st.session_state.user['id'], selected_reward[0], reduce_sticker=False)
                            if success:
                                st.success(f"✅ Bạn đã nhận được phần quà: **{selected_reward[1]}**")
                                st.session_state['reward_received'] = True  # Ẩn nút sau khi nhận quà
                            else:
                                st.warning(f"⚠ Không thể nhận phần quà: {message}")
                        else:
                            st.warning("⚠ Lỗi: Không tìm thấy phần quà đã chọn")
                else:
                    st.info("Bạn đã nhận phần quà rồi 🎁")
            else:
                st.warning("😢 Hiện không có phần quà nào phù hợp để nhận")

        elif 90 <= percentage < 100:
            if not st.session_state.get('added_sticker_for_90', False):
                add_stickers(conn, st.session_state.user['id'], 1)
                st.session_state['added_sticker_for_90'] = True
            st.success("🌟 Xuất sắc! Bạn đã đạt trên 90% và nhận được 1 sticker")

        # Lưu kết quả thi
        save_results(
            conn,
            st.session_state.user['id'],
            st.session_state['selected_topic'],
            st.session_state['selected_level'],
            st.session_state['exam_code'],
            st.session_state['num_questions'],
            correct,
            int((datetime.now() - st.session_state['start_time']).total_seconds())
        )
        
        # Nếu đúng 100%, cập nhật cột rewarded = 1 cho bản ghi kết quả mới nhất của user với bài thi đó
        if percentage == 100:
            cursor = conn.cursor()
            # Bước 1: Lấy id của bản ghi kết quả mới nhất chưa được rewarded
            cursor.execute("""
                SELECT id FROM results
                WHERE user_id = ? AND topic = ? AND level = ? AND exam_code = ? AND rewarded = 0
                ORDER BY id DESC
                LIMIT 1
            """, (
                st.session_state.user['id'],
                st.session_state['selected_topic'],
                st.session_state['selected_level'],
                st.session_state['exam_code']
            ))
            row = cursor.fetchone()
            if row:
                result_id = row[0]
                # Bước 2: Cập nhật cột rewarded = 1 cho bản ghi đó
                cursor.execute("""
                    UPDATE results
                    SET rewarded = 1
                    WHERE id = ?
                """, (result_id,))
                conn.commit()

        cursor = conn.cursor()
        cursor.execute("SELECT stickers FROM users WHERE id = ?", (st.session_state.user['id'],))
        st.session_state.user['stickers'] = cursor.fetchone()[0]

        st.markdown("---")
        st.subheader("📝 Chi tiết bài làm")
        for i, result in enumerate(results):
            with st.expander(f"Câu {i+1}: {'✅ Đúng' if result['is_correct'] else '❌ Sai'}"):
                st.markdown(f"**Câu hỏi:** {result['question']}")
                st.markdown("**Các lựa chọn:**")

                user_answer = result['user_answer'].strip().upper() if result['user_answer'] else None
                correct_answer = result['correct_answer'].strip().upper() if result['correct_answer'] else None

                for key, option_text in result['options'].items():
                    is_user_choice = (user_answer == key)
                    is_correct_answer = (correct_answer == key)

                    if user_answer == correct_answer:
                        # User trả lời đúng
                        if is_correct_answer:
                            color = "#4CAF50"  # xanh lá
                            prefix = "✅ "
                        else:
                            color = "#000000"
                            prefix = ""
                    else:
                        # User trả lời sai
                        if is_correct_answer:
                            color = "#4CAF50"  # xanh lá
                            prefix = "✅ "
                        elif is_user_choice:
                            color = "#F44336"  # đỏ
                            prefix = "👉 "
                        else:
                            color = "#000000"
                            prefix = ""

                    st.markdown(f"<span style='color:{color}'>{prefix}{key}: {option_text}</span>", unsafe_allow_html=True)

                #st.markdown(f"**Bạn chọn:** {result['user_answer'] or '❌ Không chọn'}")
                #st.markdown(f"**Đáp án đúng:** {result['correct_answer']}")
                if result.get('explanation'):
                    st.markdown(f"**Giải thích:** {result['explanation']}")

        st.markdown("---")
        st.subheader("📈 Lịch sử làm bài")
        history = get_last_10_results(conn, st.session_state.user['id'])
        for h in history:
            date = h[8]
            topic = h[2]
            level = h[3]
            exam_code = h[4]
            total_questions = h[5]
            correct_answers = h[6]
            duration = h[7]

            history_text = f"""
            📅 {date} | {topic} | {level} | Mã đề: {exam_code}  
            ✅ {correct_answers}/{total_questions} câu | ⏱ {duration}s
            """

            st.write(history_text)

        if st.button("🔄 Làm bài mới"):
            user = st.session_state.get('user')
            keys_to_keep = {'user'}
            keys_to_delete = [key for key in st.session_state.keys() if key not in keys_to_keep]
            for key in keys_to_delete:
                del st.session_state[key]
            st.session_state['user'] = user
            st.session_state['current_screen'] = 'setup'
            st.rerun()

    conn.close()

# Chức năng xem lịch sử thi (dành cho user)
elif option == "🏆 Lịch sử thi" and st.session_state.user['role'] == 'user':
    st.title("🏆 Lịch sử làm bài")
    conn = get_connection()
    
    history = get_last_10_results(conn, st.session_state.user['id'])
    
    if history:
        st.write("### 10 bài thi gần nhất")
        for h in history:
            correct = int(h[6])
            total = int(h[5])
            percentage = (correct / total) * 100 if total > 0 else 0
            exam_code = h[4]

            history_text = f"""
            <div style="border-left: 4px solid {'#4CAF50' if percentage >= 50 else '#F44336'}; padding-left: 10px; margin-bottom: 10px;">
                <b>📅 {h[8]}</b> | {h[2]} | {h[3]}<br> | Mã đề: {h[4]}<br>
                ✅ <b>{correct}/{total}</b> câu ({percentage:.1f}%) | ⏱ {h[7]}s 
            </div>
            """
            st.markdown(history_text, unsafe_allow_html=True)
    else:
        st.warning("Bạn chưa có bài thi nào")
    
    conn.close()

# Chức năng đổi điểm thưởng (dành cho user)
elif option == "🎁 Đổi điểm thưởng" and st.session_state.user['role'] == 'user':
    st.title("🎁 Đổi điểm thưởng")
    conn = get_connection()
    
    # Hiển thị số sticker hiện có
    st.success(f"🎖️ Bạn đang có: {st.session_state.user['stickers']} sticker")
    
    # Hiển thị các mốc đổi quà
    #st.write("### Các mốc đổi quà")
    #st.write("- 10 sticker: Đổi quà nhỏ")
    #st.write("- 20 sticker: Đổi quà trung bình")
    #st.write("- 30 sticker: Đổi quà lớn")
    
    # Lấy danh sách phần quà
    rewards = get_rewards(conn)
    
    if rewards:
        st.write("### Danh sách phần quà")
        for reward in rewards:
            can_afford = st.session_state.user['stickers'] >= reward[3]
            
            st.markdown(f"""
            <div class="reward-item" style="border-color: {'#4CAF50' if can_afford else '#F44336'};">
                <b>{reward[1]}</b> (Giá: {reward[3]} sticker)
                <p>{reward[2]}</p>
                <small>Còn lại: {reward[4]}</small>
                {"✅ Đủ điều kiện đổi" if can_afford else "❌ Không đủ sticker"}
            </div>
            """, unsafe_allow_html=True)
            
            if can_afford and st.button(f"Đổi {reward[1]}", key=f"redeem_{reward[0]}"):
                success, message = redeem_reward(conn, st.session_state.user['id'], reward[0])
                if success:
                    st.success(message)
                    # Cập nhật lại số sticker
                    cursor = conn.cursor()
                    cursor.execute("SELECT stickers FROM users WHERE id = ?", (st.session_state.user['id'],))
                    st.session_state.user['stickers'] = cursor.fetchone()[0]
                    st.rerun()
                else:
                    st.error(message)
    else:
        st.warning("Hiện không có phần quà nào để đổi")
    
    # Hiển thị lịch sử đổi quà
    st.markdown("---")
    st.subheader("📜 Lịch sử đổi quà")
    history = get_user_reward_history(conn, st.session_state.user['id'])
    
    if history:
        for h in history:
            st.write(f"📅 {h[0]} | {h[1]} - {h[2]}")
    else:
        st.write("Bạn chưa đổi phần quà nào")
    
    conn.close()
    
# Chức năng từ điển (dành cho user) 
elif option == "📙 Từ điển":
    st.title("📙 Tra từ điển Anh - Anh và Quản lý Flashcards")

    tab1, tab2 = st.tabs(["🔍 Tra từ điển", "📒 Quản lý Flashcards"])
    
    def generate_audio(word, lang='en'):
        from gtts import gTTS
        import os
        tts = gTTS(text=word, lang=lang)
        file_path = f"{word}.mp3"
        tts.save(file_path)
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        os.remove(file_path)
        return audio_bytes

    with tab1:
        st.title("📚 Tra từ điển Anh - Anh")

        word_input = st.text_input("Nhập từ tiếng Anh cần tra:", value=st.session_state.get('dict_last_word', ''))

        if st.button("🔍 Tra từ"):
            word = word_input.strip()
            if not word:
                st.warning("Vui lòng nhập từ cần tra.")
            else:
                results = fetch_definition(word)
                if results:
                    st.session_state['dict_last_word'] = word
                    st.session_state['dict_last_results'] = results
                    st.session_state['dict_audio_bytes'] = generate_audio(word)
                    if word not in st.session_state['dict_history_words']:
                        st.session_state['dict_history_words'].insert(0, word)
                        if len(st.session_state['dict_history_words']) > 20:
                            st.session_state['dict_history_words'].pop()
                else:
                    st.warning("Không tìm thấy định nghĩa cho từ này.")
                    st.session_state['dict_last_results'] = None
                    st.session_state['dict_audio_bytes'] = None
                    st.session_state['dict_last_word'] = ""

        # Hiển thị kết quả định nghĩa nếu có
        if st.session_state.get('dict_last_results'):
            st.markdown(f"### Định nghĩa cho từ: **{st.session_state['dict_last_word']}**")
            for pos, definition, example in st.session_state['dict_last_results']:
                st.markdown(f"**{pos}**: {definition}")
                if example:
                    st.markdown(f"*Ví dụ:* {example}")

            # Nút phát âm & lưu flashcard
            col1, col2 = st.columns([1,1])
            with col1:
                if st.button(f"🔊 Phát âm '{st.session_state['dict_last_word']}'"):
                    st.audio(st.session_state['dict_audio_bytes'], format='audio/mp3')
            with col2:
                if st.button("💾 Lưu flashcard"):
                    word = st.session_state['dict_last_word']
                    existing = any(fc['word'] == word for fc in st.session_state['dict_flashcards'])
                    if not existing:
                        flashcard_data = {
                            'word': word,
                            'definitions': st.session_state['dict_last_results']
                        }
                        st.session_state['dict_flashcards'].append(flashcard_data)
                        st.success(f"Đã lưu flashcard cho từ '{word}'.")
                    else:
                        st.info(f"Từ '{word}' đã có trong flashcard rồi.")

        # Hiển thị lịch sử từ đã tra
        if st.session_state['dict_history_words']:
            st.markdown("---")
            st.subheader("🔖 Lịch sử 20 từ gần nhất đã tra")
            for w in st.session_state['dict_history_words']:
                st.write(w)

        # Hiển thị flashcards đã lưu
        if st.session_state['dict_flashcards']:
            st.markdown("---")
            st.subheader("📒 Danh sách Flashcards đã lưu")
            for idx, fc in enumerate(st.session_state['dict_flashcards']):
                st.markdown(f"**{idx+1}. {fc['word']}**")
                for pos, definition, example in fc['definitions']:
                    st.markdown(f"- **{pos}**: {definition}")
                    if example:
                        st.markdown(f"  *Ví dụ:* {example}")
                    
    with tab2:
        st.title("📒 Quản lý Flashcards")

        flashcard_list_tab, flashcard_create_tab = st.tabs(["Danh sách flashcard", "Tạo flashcard mới"])

        with flashcard_list_tab:
            st.markdown("""
            <style>
            textarea {
                background-color: #ffffff !important;
                color: #000000 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            st.subheader("Danh sách flashcard đã lưu")
            if not st.session_state['dict_flashcards']:
                st.info("Chưa có flashcard nào được lưu.")
            else:
                for idx, fc in enumerate(st.session_state['dict_flashcards']):
                    word = fc['word']
                    definitions = fc['definitions']

                    flipped_key = f"flipped_{idx}"
                    if flipped_key not in st.session_state:
                        st.session_state[flipped_key] = False

                    with st.expander(f"🔖 Flashcard {idx+1}: {word}", expanded=True):
                        if not st.session_state[flipped_key]:
                            col1, col2 = st.columns([3,1])
                            with col1:
                                st.markdown(f"### {word}")
                            with col2:
                                if st.button("🔊", key=f"play_{idx}"):
                                    audio_bytes = generate_audio(word)
                                    st.audio(audio_bytes, format='audio/mp3')

                            if st.button("Lật flashcard 🔄", key=f"flip_{idx}"):
                                st.session_state[flipped_key] = True
                                st.rerun()
                        else:
                            st.markdown(f"### Định nghĩa và ví dụ của từ **{word}**")
                            for i, (pos, definition, example) in enumerate(definitions):
                                new_def = st.text_area(f"Định nghĩa ({pos})", value=definition, key=f"def_{idx}_{i}")
                                new_ex = st.text_area(f"Ví dụ ({pos})", value=example if example else "", key=f"ex_{idx}_{i}")
                                st.session_state['dict_flashcards'][idx]['definitions'][i] = (pos, new_def, new_ex)

                            if st.button("Lật lại mặt trước 🔄", key=f"flip_back_{idx}"):
                                st.session_state[flipped_key] = False
                                st.rerun()

                        if st.button("❌ Xóa flashcard", key=f"del_{idx}"):
                            st.session_state['dict_flashcards'].pop(idx)
                            st.success(f"Đã xóa flashcard '{word}'.")
                            st.rerun()

        with flashcard_create_tab:
            st.subheader("Tạo flashcard mới")
            new_word = st.text_input("Từ (Word)")
            new_pos = st.text_input("Loại từ (Part of speech)")
            new_definition = st.text_area("Định nghĩa")
            new_example = st.text_area("Ví dụ (có thể để trống)")

            if st.button("💾 Lưu flashcard mới"):
                if not new_word or not new_definition or not new_pos:
                    st.warning("Vui lòng nhập đủ từ, loại từ và định nghĩa.")
                else:
                    existing = any(fc['word'].lower() == new_word.lower() for fc in st.session_state['dict_flashcards'])
                    if existing:
                        st.warning(f"Flashcard cho từ '{new_word}' đã tồn tại.")
                    else:
                        new_flashcard = {
                            'word': new_word,
                            'definitions': [(new_pos, new_definition, new_example)]
                        }
                        st.session_state['dict_flashcards'].append(new_flashcard)
                        st.success(f"Đã lưu flashcard cho từ '{new_word}'.")
                        st.rerun()
                        
# Thêm chức năng bài học cho người dùng
if option == "📚 Bài học":
    st.title("📚 Bài học")
    conn = get_connection()
    
    # Lấy danh sách chủ đề với số lượng bài học
    lesson_topics = conn.execute("""
        SELECT t.id, t.name, t.description, t.thumbnail_url, 
               COUNT(l.id) as lesson_count
        FROM lesson_topics t
        LEFT JOIN chapters c ON t.id = c.lesson_topic_id
        LEFT JOIN lessons l ON c.id = l.chapter_id
        GROUP BY t.id
        ORDER BY t.name
    """).fetchall()
    
    if not lesson_topics:
        st.info("Hiện chưa có bài học nào")
    else:
        # Hiển thị danh sách chủ đề dưới dạng cards
        cols = st.columns(3)
        for i, lesson_topic in enumerate(lesson_topics):
            with cols[i % 3]:
                with st.container(border=True):
                    if lesson_topic[3]:  # thumbnail_url
                        st.image(lesson_topic[3], use_container_width=True)
                    st.subheader(lesson_topic[1])
                    st.caption(f"{lesson_topic[4]} bài học")
                    st.write(lesson_topic[2] or "Không có mô tả")
                    
                    if st.button(f"Xem chương học", key=f"view_topic_{lesson_topic[0]}"):
                        st.session_state['selected_lesson_topic_id'] = lesson_topic[0]
                        st.rerun()

        # Hiển thị chi tiết chủ đề được chọn
        if 'selected_lesson_topic_id' in st.session_state:
            lesson_topic_id = st.session_state['selected_lesson_topic_id']
            lesson_topic = next(t for t in lesson_topics if t[0] == lesson_topic_id)
            
            # Nút quay lại danh sách chủ đề
            if st.button("← Quay lại danh sách chủ đề"):
                del st.session_state['selected_lesson_topic_id']
                if 'selected_chapter_id' in st.session_state:
                    del st.session_state['selected_chapter_id']
                if 'current_lesson' in st.session_state:
                    del st.session_state['current_lesson']
                st.rerun()
            
            st.subheader(lesson_topic[1])
            
            # Lấy danh sách chương với tiến độ học tập
            chapters = conn.execute("""
                SELECT c.id, c.title, c.description, 
                       COUNT(l.id) as lesson_count,
                       COALESCE(SUM(ulp.is_completed), 0) as completed_count
                FROM chapters c
                LEFT JOIN lessons l ON c.id = l.chapter_id
                LEFT JOIN user_learning_progress ulp ON 
                    l.id = ulp.lesson_id AND ulp.user_id = ?
                WHERE c.lesson_topic_id = ?
                GROUP BY c.id
                ORDER BY c.order_num
            """, (st.session_state.user['id'], lesson_topic_id)).fetchall()
            
            if not chapters:
                st.info("Chủ đề này chưa có chương học nào")
            else:
                # Hiển thị danh sách chương học
                for chapter in chapters:
                    with st.expander(f"{chapter[1]} - Hoàn thành: {chapter[4]}/{chapter[3]}"):
                        st.write(chapter[2] or "Không có mô tả")
                        
                        # Lấy danh sách bài học trong chương
                        lessons = conn.execute("""
                            SELECT l.id, l.title, l.description, l.content_type, l.content,
                                   l.level, l.is_interactive,
                                   IFNULL(ulp.is_completed, 0) as is_completed,
                                   IFNULL(ulp.progress_percent, 0) as progress,
                                   IFNULL(ulp.last_accessed, 'Chưa học') as last_accessed
                            FROM lessons l
                            LEFT JOIN user_learning_progress ulp ON 
                                l.id = ulp.lesson_id AND ulp.user_id = ?
                            WHERE l.chapter_id = ?
                            ORDER BY l.created_at
                        """, (st.session_state.user['id'], chapter[0])).fetchall()
                        
                        if not lessons:
                            st.info("Chương này chưa có bài học nào")
                        else:
                            for lesson in lessons:
                                # Hiển thị thông tin bài học với trạng thái
                                status = "✅" if lesson[7] else "📌"
                                progress = f"▰" * int(lesson[8]/10) + f"▱" * (10 - int(lesson[8]/10))
                                
                                col1, col2 = st.columns([8, 2])
                                with col1:
                                    st.markdown(f"{status} **{lesson[1]}**  \n"
                                                f"*{lesson[2] or 'Không có mô tả'}*  \n"
                                                f"Lần cuối học: {lesson[9]}")
                                with col2:
                                    st.button(
                                        "Học ngay" if not lesson[7] else "Xem lại",
                                        key=f"learn_{lesson[0]}",
                                        on_click=lambda lid=lesson[0]: st.session_state.update({
                                            'current_lesson': lid,
                                            'selected_chapter_id': chapter[0]
                                        })
                                    )
                                st.progress(lesson[8], text=progress)
                                st.divider()

        # Hiển thị nội dung bài học nếu được chọn
                # Hiển thị nội dung bài học khi người dùng chọn
        if 'current_lesson' in st.session_state:
            lesson_id = st.session_state['current_lesson']
            lesson = conn.execute("""
                SELECT id, title, description, content_type, content, level, is_interactive
                FROM lessons
                WHERE id = ?
            """, (lesson_id,)).fetchone()

            if lesson:
                st.subheader(lesson[1])
                st.write(lesson[2] or "Không có mô tả")
                if lesson[5]:
                    st.caption(f"Độ khó: {lesson[5]}")

                # Nút quay lại danh sách bài học
                if st.button("← Quay lại danh sách bài học"):
                    del st.session_state['current_lesson']
                    st.rerun()

                # Hiển thị nội dung bài học
                if lesson[3] == "multiple":
                    content_blocks = json.loads(lesson[4])
                    for block in content_blocks:
                        block_type = block['type']
                        block_value = block['value']

                        with st.container(border=True):
                            if block_type == "text":
                                st.markdown(block_value)
                            elif block_type == "image":
                                try:
                                    st.image(block_value, use_container_width=True)
                                except:
                                    st.error(f"Không thể tải hình ảnh: {block_value}")
                            elif block_type == "audio":
                                try:
                                    st.audio(block_value)
                                except:
                                    st.error(f"Không thể tải audio: {block_value}")
                            elif block_type == "video":
                                try:
                                    st.video(block_value)
                                except:
                                    st.error(f"Không thể tải video: {block_value}")
                            elif block_type == "pdf":
                                st.components.v1.iframe(block_value, height=600, scrolling=True)
                            elif block_type == "embed":
                                st.components.v1.iframe(block_value, height=400, scrolling=True)
                            elif block_type == "file":
                                try:
                                    with open(block_value, "rb") as f:
                                        st.download_button(
                                            label=f"📥 Tải về {block['file_name']}",
                                            data=f,
                                            file_name=block['file_name'],
                                            mime="application/octet-stream",
                                            key=f"download_button_{i}"
                                        )
                                except:
                                    st.error(f"Không thể tải file: {block['file_name']}")

                # Hiển thị nội dung tương tác nếu có
                if lesson[6]:  # is_interactive
                    interactive_content = conn.execute("""
                        SELECT content_type, content_data
                        FROM interactive_content
                        WHERE lesson_id = ?
                    """, (lesson_id,)).fetchone()

                    if interactive_content:
                        content_type = interactive_content[0]
                        content_data = json.loads(interactive_content[1])['data']

                        st.subheader("📝 Nội dung tương tác")
                        if content_type == "quiz":
                            st.info("Câu hỏi trắc nghiệm")
                            if "quiz_answers" not in st.session_state:
                                st.session_state.quiz_answers = {}
                            if "quiz_submitted" not in st.session_state:
                                st.session_state.quiz_submitted = False

                            with st.form("quiz_form"):
                                for i, q in enumerate(content_data):
                                    st.markdown(f"**Câu hỏi {i+1}: {q['question']}**")
                                    answer = st.radio(
                                        f"Chọn đáp án cho câu hỏi {i+1}",
                                        options=list(q['options'].keys()),
                                        format_func=lambda x: f"{x}: {q['options'][x]}",
                                        key=f"quiz_{i}"
                                    )
                                    st.session_state.quiz_answers[i] = {
                                        'answer': answer,
                                        'correct': q['correct']
                                    }

                                if st.form_submit_button("Nộp bài"):
                                    st.session_state.quiz_submitted = True
                                    correct_count = sum(1 for i, ans in st.session_state.quiz_answers.items() 
                                                      if ans['answer'] == ans['correct'])
                                    st.success(f"Bạn trả lời đúng {correct_count}/{len(content_data)} câu hỏi!")
                                    # Cập nhật tiến độ
                                    progress = (correct_count / len(content_data)) * 100
                                    conn.execute("""
                                        INSERT OR REPLACE INTO user_learning_progress 
                                        (user_id, lesson_id, is_completed, progress_percent, last_accessed)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (
                                        st.session_state.user['id'],
                                        lesson_id,
                                        1 if correct_count == len(content_data) else 0,
                                        progress,
                                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    ))
                                    conn.commit()

                            if st.session_state.quiz_submitted:
                                st.subheader("Kết quả")
                                for i, q in enumerate(content_data):
                                    user_answer = st.session_state.quiz_answers.get(i, {})
                                    is_correct = user_answer.get('answer') == q['correct']
                                    st.markdown(f"**Câu {i+1}: {q['question']}**")
                                    st.markdown(f"- Bạn chọn: {user_answer.get('answer', 'Chưa trả lời')}: "
                                              f"{q['options'].get(user_answer.get('answer', ''), '')}")
                                    st.markdown(f"- Đáp án đúng: {q['correct']}: {q['options'][q['correct']]}")
                                    st.markdown(f"{'✅ Đúng' if is_correct else '❌ Sai'}")

                        elif content_type == "flashcard":
                            st.info("Flashcards")
                            for i, card in enumerate(content_data):
                                with st.expander(f"Thuật ngữ: {card['term']}"):
                                    st.markdown(f"**Định nghĩa**: {card['definition']}")

                        elif content_type == "exercise":
                            st.info("Bài tập")
                            for i, ex in enumerate(content_data):
                                st.markdown(f"**Bài tập {i+1}: {ex['instruction']}**")
                                st.code(ex['content'])
                                if ex['answer']:
                                    with st.expander("Xem đáp án"):
                                        st.markdown(ex['answer'])
                                # Cập nhật tiến độ khi xem bài tập
                                conn.execute("""
                                    INSERT OR REPLACE INTO user_learning_progress 
                                    (user_id, lesson_id, is_completed, progress_percent, last_accessed)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (
                                    st.session_state.user['id'],
                                    lesson_id,
                                    0,
                                    50,  # Giả định 50% tiến độ khi xem
                                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                ))
                                conn.commit()

                        elif content_type == "fill_blank":
                            st.info("Điền vào chỗ trống")
                            if "fill_blank_answers" not in st.session_state:
                                st.session_state.fill_blank_answers = {}
                            if "fill_blank_submitted" not in st.session_state:
                                st.session_state.fill_blank_submitted = False

                            with st.form("fill_blank_form"):
                                for i, fb in enumerate(content_data):
                                    st.markdown(f"**Bài {i+1}: {fb['instruction']}**")
                                    st.code(fb['content'])
                                    blanks = fb['content'].count("___")
                                    for j in range(blanks):
                                        st.session_state.fill_blank_answers[f"{i}_{j}"] = st.text_input(
                                            f"Điền vào chỗ trống {j+1}",
                                            key=f"fill_blank_{i}_{j}"
                                        )

                                if st.form_submit_button("Nộp bài"):
                                    st.session_state.fill_blank_submitted = True
                                    correct_count = 0
                                    total_blanks = 0
                                    for i, fb in enumerate(content_data):
                                        blanks = fb['content'].count("___")
                                        total_blanks += blanks
                                        for j in range(blanks):
                                            user_answer = st.session_state.fill_blank_answers.get(f"{i}_{j}", "").strip()
                                            if user_answer.lower() == fb['answers'][j].lower():
                                                correct_count += 1

                                    st.success(f"Bạn điền đúng {correct_count}/{total_blanks} chỗ trống!")
                                    progress = (correct_count / total_blanks) * 100
                                    conn.execute("""
                                        INSERT OR REPLACE INTO user_learning_progress 
                                        (user_id, lesson_id, is_completed, progress_percent, last_accessed)
                                        VALUES (?, ?, ?, ?, ?)
                                    """, (
                                        st.session_state.user['id'],
                                        lesson_id,
                                        1 if correct_count == total_blanks else 0,
                                        progress,
                                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                    ))
                                    conn.commit()

                            if st.session_state.fill_blank_submitted:
                                st.subheader("Kết quả")
                                for i, fb in enumerate(content_data):
                                    st.markdown(f"**Bài {i+1}: {fb['instruction']}**")
                                    st.code(fb['content'])
                                    blanks = fb['content'].count("___")
                                    for j in range(blanks):
                                        user_answer = st.session_state.fill_blank_answers.get(f"{i}_{j}", "")
                                        is_correct = user_answer.lower() == fb['answers'][j].lower()
                                        st.markdown(f"- Chỗ trống {j+1}: Bạn điền: {user_answer}")
                                        st.markdown(f"- Đáp án đúng: {fb['answers'][j]}")
                                        st.markdown(f"{'✅ Đúng' if is_correct else '❌ Sai'}")

                # Nút đánh dấu hoàn thành (nếu không phải bài học tương tác)
                if not lesson[6]:
                    if st.button("✅ Đánh dấu hoàn thành"):
                        conn.execute("""
                            INSERT OR REPLACE INTO user_learning_progress 
                            (user_id, lesson_id, is_completed, progress_percent, last_accessed)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            st.session_state.user['id'],
                            lesson_id,
                            1,
                            100,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        ))
                        conn.commit()
                        st.success("Bài học đã được đánh dấu hoàn thành!")
                        st.rerun()
       
            
            # Panel quản lý tiến độ học tập
            with st.expander("📝 Quản lý tiến độ học tập"):
                progress_data = conn.execute("""
                    SELECT is_completed, progress_percent, notes 
                    FROM user_learning_progress 
                    WHERE user_id = ? AND lesson_id = ?
                """, (st.session_state.user['id'], lesson_id)).fetchone() or (False, 0, "")
                
                with st.form("progress_form"):
                    progress = st.slider(
                        "Tiến độ hoàn thành (%)",
                        0, 100, 
                        value=progress_data[1]
                    )
                    
                    is_completed = st.checkbox(
                        "Đánh dấu hoàn thành",
                        value=progress_data[0]
                    )
                    
                    notes = st.text_area(
                        "Ghi chú cá nhân",
                        value=progress_data[2]
                    )
                    
                    if st.form_submit_button("Lưu tiến độ"):
                        try:
                            conn.execute("""
                                INSERT OR REPLACE INTO user_learning_progress (
                                    user_id, lesson_id, is_completed, 
                                    progress_percent, notes, last_accessed
                                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (
                                st.session_state.user['id'], 
                                lesson_id, 
                                is_completed, 
                                progress, 
                                notes
                            ))
                            conn.commit()
                            st.success("Đã cập nhật tiến độ học tập!")
                        except Exception as e:
                            st.error(f"Lỗi: {str(e)}")
    
    conn.close()                          

            
# Đăng xuất
if st.sidebar.button("🚪 Đăng xuất"):
    st.session_state.clear()
    st.rerun()
