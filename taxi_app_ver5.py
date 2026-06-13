import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import unicodedata
import re
import googlemaps

# ==========================================
# 1. 設定・定数
# ==========================================
DB_NAME = "taxi_reservations.db"
GOOGLE_MAPS_API_KEY = "AIzaSyBreMKJGmPYDMnENhhb-MqUro_n9VMBWpI"
DEFAULT_ORIGIN = "東京都北区高島平４-５-１０"

try:
    gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
except Exception as e:
    st.error(f"Google Maps APIの初期化に失敗しました: {e}")

# ==========================================
# 2. データ操作・ユーティリティ層
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    sql_res = (
        "CREATE TABLE IF NOT EXISTS reservations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "customer_name TEXT NOT NULL, "
        "date TEXT NOT NULL, "
        "time TEXT NOT NULL, "
        "phone TEXT, "
        "pickup_location TEXT, "
        "destination TEXT, "
        "vehicle_type TEXT, "
        "status TEXT, "
        "notes TEXT, "
        "fare INTEGER DEFAULT 0, "
        "deleted INTEGER DEFAULT 0, "
        "assigned_to TEXT)"
    )
    c.execute(sql_res)
    
    c.execute("PRAGMA table_info(reservations)")
    columns = [column[1] for column in c.fetchall()]
    
    new_cols = {
        "assigned_to": "TEXT", 
        "distance": "REAL", 
        "duration": "TEXT", 
        "completion_time": "TEXT", 
        "in_hospital_assist": "INTEGER DEFAULT 0",
        "planned_fare": "INTEGER DEFAULT 0"
    }
    for col_name, col_type in new_cols.items():
        if col_name not in columns:
            try:
                c.execute(f"ALTER TABLE reservations ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass
            
    sql_users = (
        "CREATE TABLE IF NOT EXISTS users ("
        "username TEXT PRIMARY KEY, "
        "password TEXT NOT NULL, "
        "role TEXT NOT NULL)"
    )
    c.execute(sql_users)
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
            ("admin", "admin123", "Admin")
        )
        c.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
            ("staff", "staff123", "Operator")
        )
    conn.commit()
    conn.close()

def get_route_info(origin, destination):
    if not destination: 
        return {
            "std_dist": 0.0, 
            "std_time": "不明", 
            "avoid_dist": 0.0, 
            "avoid_time": "不明"
        }
    start_point = origin if origin and origin.strip() else DEFAULT_ORIGIN
    try:
        res_std = gmaps.directions(start_point, destination, mode="driving")
        if res_std:
            std_dist = round(res_std[0]['legs'][0]['distance']['value'] / 1000.0, 2)
            std_time = res_std[0]['legs'][0]['duration']['text']
        else:
            std_dist, std_time = 0.0, "不明"
        
        res_avoid = gmaps.directions(start_point, destination, mode="driving", avoid="tolls")
        if res_avoid:
            avoid_dist = round(res_avoid[0]['legs'][0]['distance']['value'] / 1000.0, 2)
            avoid_time = res_avoid[0]['legs'][0]['duration']['text']
        else:
            avoid_dist, avoid_time = 0.0, "不明"
            
        return {
            "std_dist": std_dist, 
            "std_time": std_time, 
            "avoid_dist": avoid_dist, 
            "avoid_time": avoid_time
        }
    except Exception as e:
        return {
            "std_dist": 0.0, 
            "std_time": "エラー", 
            "avoid_dist": 0.0, 
            "avoid_time": "エラー"
        }

def normalize_text(text):
    if not text: return ""
    return unicodedata.normalize('NFKC', str(text)).lower().strip()

def format_date(date_str):
    if not date_str: return ""
    clean_str = normalize_text(date_str)
    nums = re.sub(r'\D', '', clean_str)
    if len(nums) == 8: 
        return f"{nums[:4]}-{nums[4:6]}-{nums[6:]}"
    return clean_str

def format_time(time_str):
    if not time_str: return ""
    nums = re.sub(r'\D', '', str(time_str))
    if len(nums) == 3: return f"0{nums[:2]}:{nums[2:]}"
    elif len(nums) == 4: return f"{nums[:2]}:{nums[2:]}"
    return str(time_str).strip()

def get_weekday(date_str):
    """日付文字列(YYYY-MM-DD)から曜日(月〜日)を返す"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        return f"({weekdays[dt.weekday()]})"
    except:
        return ""

def get_usernames():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT username FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def add_reservation(
    name, 
    date, 
    time, 
    phone, 
    pickup, 
    dest, 
    v_type, 
    status, 
    notes, 
    planned_fare, 
    assigned_to=""
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    sql = (
        "INSERT INTO reservations (customer_name, date, time, phone, "
        "pickup_location, destination, vehicle_type, status, notes, "
        "assigned_to, distance, in_hospital_assist, planned_fare) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)"
    )
    params = (
        name, 
        date, 
        time, 
        phone, 
        pickup, 
        dest, 
        v_type, 
        status, 
        notes, 
        assigned_to, 
        planned_fare
    )
    c.execute(sql, params)
    conn.commit()
    conn.close()

def update_reservation(
    res_id, 
    name, 
    date, 
    time, 
    phone, 
    pickup, 
    dest, 
    v_type, 
    status, 
    notes, 
    fare, 
    assigned_to, 
    distance, 
    duration, 
    completion_time, 
    assist
):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    sql = (
        "UPDATE reservations SET customer_name=?, date=?, time=?, phone=?, "
        "pickup_location=?, destination=?, vehicle_type=?, status=?, notes=?, "
        "fare=?, assigned_to=?, distance=?, duration=?, completion_time=?, "
        "in_hospital_assist=? WHERE id=?"
    )
    params = (
        name, 
        date, 
        time, 
        phone, 
        pickup, 
        dest, 
        v_type, 
        status, 
        notes, 
        fare, 
        assigned_to, 
        distance, 
        duration, 
        completion_time, 
        assist, 
        res_id
    )
    c.execute(sql, params)
    conn.commit()
    conn.close()

def assign_reservation(res_id, username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reservations SET assigned_to = ? WHERE id = ?", (username, res_id))
    conn.commit()
    conn.close()

def get_all_reservations(include_deleted=False):
    conn = sqlite3.connect(DB_NAME)
    sql = "SELECT * FROM reservations"
    if not include_deleted: 
        sql += " WHERE deleted = 0"
    df = pd.read_sql_query(sql, conn)
    conn.close()
    if not df.empty:
        def make_sort_key(row):
            d = re.sub(r'\D', '', str(row['date']))
            t = re.sub(r'\D', '', str(row['time']))
            if len(t) == 3: t = '0' + t
            return d + t[:4] if d and t else "999999999999"
        df['sort_key'] = df.apply(make_sort_key, axis=1)
        df = df.sort_values(by='sort_key').drop(columns=['sort_key'])
    return df

def delete_reservation(res_id, physical=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if physical:
        c.execute("DELETE FROM reservations WHERE id = ?", (res_id,))
    else:
        c.execute("UPDATE reservations SET deleted = 1 WHERE id = ?", (res_id,))
    conn.commit()
    conn.close()

def restore_reservation(res_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE reservations SET deleted = 0 WHERE id = ?", (res_id,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    return df

def delete_user(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

def update_user(old_username, new_username, password, role):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE users SET username=?, password=?, role=? WHERE username=?", 
        (new_username, password, role, old_username)
    )
    conn.commit()
    conn.close()

# ==========================================
# 3. ページ層 (UIコンポーネント)
# ==========================================

def show_login():
    st.title("🔑 システムログイン")
    with st.form("login_form"):
        user = st.text_input("ユーザー名")
        pwd = st.text_input("パスワード", type="password")
        if st.form_submit_button("ログイン"):
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT role FROM users WHERE username=? AND password=?", (user, pwd))
            result = c.fetchone()
            conn.close()
            if result:
                st.session_state.logged_in = True
                st.session_state.username = user
                st.session_state.user_role = result[0]
                st.success(f"ログイン成功！ 権限: {result[0]}")
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが間違っています。")

def show_user_edit():
    st.title("👤 ユーザー情報の編集")
    users_df = get_all_users()
    user_row = users_df[users_df['username'] == st.session_state.edit_user_id]
    if not user_row.empty:
        target = user_row.iloc[0]
        with st.form("edit_user_form"):
            e_uname = st.text_input("ユーザー名", value=target['username'])
            e_upwd = st.text_input("パスワード", value=target['password'])
            e_urole = st.selectbox("権限", ["Admin", "Operator"], index=0 if target['role'] == "Admin" else 1)
            if st.form_submit_button("ユーザー情報を更新"):
                update_user(
                    st.session_state.edit_user_id, 
                    e_uname, 
                    e_upwd, 
                    e_urole
                )
                st.session_state.edit_user_id = None
                st.success("更新しました！")
                st.rerun()
        if st.button("⬅️ 戻る"):
            st.session_state.edit_user_id = None
            st.rerun()

def show_reservation_edit():
    st.title("📝 予約内容の編集・完了処理")
    df_full = get_all_reservations(include_deleted=True)
    res_id = int(st.session_state.edit_id)
    filtered = df_full[df_full['id'] == res_id]
    target_row = filtered.iloc[0] if not filtered.empty else None
    if target_row is not None:
        user_list = ["未割当"] + get_usernames()
        curr_ass = target_row['assigned_to'] if target_row['assigned_to'] else "未割当"
        route_info = get_route_info(target_row['pickup_location'], target_row['destination'])
        with st.form("edit_form"):
            c1, c2 = st.columns(2)
            with c1:
                e_name = st.text_input("名前", value=target_row['customer_name'])
                e_date = st.text_input("日付", value=target_row['date'])
                e_time = st.text_input("開始時間", value=target_row['time'])
                e_phone = st.text_input("電話番号", value=target_row['phone'])
            with c2:
                e_pickup = st.text_input("出発地", value=target_row['pickup_location'])
                e_dest = st.text_input("目的地", value=target_row['destination'])
                e_v_type = st.text_input("設備", value=target_row['vehicle_type'])
                if st.session_state.user_role == "Admin":
                    idx = user_list.index(curr_ass) if curr_ass in user_list else 0
                    e_assigned = st.selectbox("担当ドライバー", user_list, index=idx)
                else:
                    op_list = ["未割当", st.session_state.username]
                    idx = op_list.index(curr_ass) if curr_ass in op_list else 0
                    e_assigned = st.selectbox("担当ドライバー", op_list, index=idx)
            st.divider()
            st.subheader("💰 料金・距離計算")
            info_txt = (
                f"📍 **目安**\n\n"
                f"【下道優先】 {route_info['avoid_dist']} km / {route_info['avoid_time']}\n\n"
                f"【通常】 {route_info['std_dist']} km / {route_info['std_time']}"
            )
            st.info(info_txt)
            st.write(f"📝 **予定金額: {target_row['planned_fare']} 円**")
            col_fare, col_done = st.columns(2)
            with col_fare: 
                e_fare = st.number_input("確定金額 (円)", value=int(target_row['fare']))
            with col_done: 
                def_comp_t = target_row['completion_time'] or ""
                e_comp_t = st.text_input("終了予定時刻", value=def_comp_t)
            col_assist, col_status = st.columns(2)
            with col_assist: 
                e_assist = st.checkbox("院内介助あり", value=bool(target_row['in_hospital_assist']))
            with col_status:
                opts = ["仮予約", "確定", "完了", "キャンセル"]
                idx = opts.index(target_row['status']) if target_row['status'] in opts else 0
                e_status = st.selectbox("ステータス", opts, index=idx)
            e_notes = st.text_area("備考", value=target_row['notes'])
            if st.form_submit_button("更新して保存"):
                final_status = e_status if e_fare == 0 else "完了"
                final_ass = "" if e_assigned == "未割当" else e_assigned
                update_reservation(
                    res_id, 
                    normalize_text(e_name), 
                    format_date(e_date), 
                    format_time(normalize_text(e_time)), 
                    normalize_text(e_phone), 
                    normalize_text(e_pickup), 
                    normalize_text(e_dest), 
                    e_v_type, 
                    final_status, 
                    normalize_text(e_notes), 
                    e_fare, 
                    normalize_text(final_ass), 
                    route_info['avoid_dist'], 
                    route_info['avoid_time'], 
                    e_comp_t, 
                    1 if e_assist else 0
                )
                st.session_state.edit_id = None
                st.success("更新しました！")
                st.rerun()
        if st.button("⬅️ 戻る"):
            st.session_state.edit_id = None
            st.rerun()

def show_new_reservation():
    st.header("📅 新規予約の登録")
    if st.session_state.saved:
        st.success("✅ 予約を保存しました！編集画面で目安を確認し、確定金額を入力してください。")
        st.session_state.saved = False
    user_list = ["未割当"] + get_usernames()
    with st.form("res_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            res_name = st.text_input("利用者名")
            res_date = st.date_input("乗車日", datetime.now())
            res_time = st.text_input("乗車時間", value="10:00")
            res_phone = st.text_input("電話番号")
        with col2:
            res_pickup = st.text_input("出発地 (住所)")
            res_dest = st.text_input("目的地")
            sel = st.multiselect("必要設備", ["車椅子", "ストレッチャー"])
            res_v_type = ", ".join(sel) if sel else "なし"
            res_assigned = st.selectbox("担当ドライバー", user_list)
        res_plan_f = st.number_input("予定金額 (円)", value=0)
        res_status = st.selectbox("ステータス", ["仮予約", "確定", "完了", "キャンセル"])
        res_notes = st.text_area("備考")
        if st.form_submit_button("予約を保存する"):
            if not res_name.strip() or not res_pickup.strip() or not res_dest.strip():
                st.error("必須項目を入力してください")
            else:
                final_ass = "" if res_assigned == "未割当" else res_assigned
                add_reservation(
                    normalize_text(res_name), 
                    format_date(str(res_date)), 
                    format_time(normalize_text(res_time)), 
                    normalize_text(res_phone), 
                    normalize_text(res_pickup), 
                    normalize_text(res_dest), 
                    res_v_type, 
                    res_status, 
                    normalize_text(res_notes), 
                    res_plan_f, 
                    final_ass
                )
                st.session_state.saved = True
                st.toast("✅ 保存しました！")
                st.rerun()

def show_reservation_list():
    st.header("📋 現在の予約状況")
    df = get_all_reservations()
    active_df = df[~df['status'].isin(["完了", "キャンセル"])].copy()
    search_q = st.text_input("🔍 検索 (名前・出発地)")
    if search_q:
        mask_name = active_df['customer_name'].str.contains(search_q)
        mask_loc = active_df['pickup_location'].str.contains(search_q)
        active_df = active_df[mask_name | mask_loc]
    u_base = "https://www.google.com/maps/search/?api=1&query="
    
    if st.session_state.user_role == "Operator":
        my_df = active_df[active_df['assigned_to'] == st.session_state.username]
        open_df = active_df[active_df['assigned_to'] == ""]
        st.subheader("📅 自分の担当予約")
        current_date = None
        for _, row in my_df.iterrows():
            # 曜日付き日付ヘッダー
            day_str = get_weekday(row['date'])
            if row['date'] != current_date:
                st.markdown(f"### 🗓️ {row['date']} {day_str}")
                current_date = row['date']
            header = (
                f"{row['time']} {row['customer_name']}様 "
                f"[{row['pickup_location']} → {row['destination']}]"
            )
            with st.expander(header):
                st.write(f"**電話:** {row['phone']} | **車両:** {row['vehicle_type']} | **ステータス:** {row['status']}")
                st.write(f"**距離:** {row['distance']} km | **予定:** {row['planned_fare']}円 | **確定:** {row['fare']}円")
                l_s = f"[📍 出発地]({u_base}{row['pickup_location']})"
                l_e = f"[🏁 目的地]({u_base}{row['destination']})"
                st.markdown(f"{l_s} / {l_e}")
                if st.button(f"✏️ 編集・完了", key=f"edit_{row['id']}"):
                    st.session_state.edit_id = row['id']
                    st.rerun()
                if st.button(f"🗑 削除", key=f"del_{row['id']}"):
                    delete_reservation(row['id'])
                    st.rerun()
        st.divider()
        st.subheader("🚀 未割当予約")
        current_date = None
        for _, row in open_df.iterrows():
            day_str = get_weekday(row['date'])
            if row['date'] != current_date:
                st.markdown(f"### 🗓️ {row['date']} {day_str}")
                current_date = row['date']
            header = (
                f"{row['time']} {row['customer_name']}様 "
                f"[{row['pickup_location']} → {row['destination']}]"
            )
            with st.expander(header):
                st.write(f"**電話:** {row['phone']} | **車両:** {row['vehicle_type']} | **ステータス:** {row['status']}")
                st.write(f"**予定金額:** {row['planned_fare']}円")
                l_s = f"[📍 出発地]({u_base}{row['pickup_location']})"
                l_e = f"[🏁 目的地]({u_base}{row['destination']})"
                st.markdown(f"{l_s} / {l_e}")
                if st.button(f"🙋 担当する", key=f"take_{row['id']}"):
                    assign_reservation(row['id'], st.session_state.username)
                    st.rerun()
    elif st.session_state.user_role == "Admin":
        open_df = active_df[active_df['assigned_to'] == ""]
        ass_df = active_df[active_df['assigned_to'] != ""]
        st.subheader("⚠️ 未割当 (至急)")
        current_date = None
        for _, row in open_df.iterrows():
            day_str = get_weekday(row['date'])
            if row['date'] != current_date:
                st.markdown(f"### 🗓️ {row['date']} {day_str}")
                current_date = row['date']
            header = (
                f"【未割当】 {row['time']} {row['customer_name']}様 "
                f"[{row['pickup_location']} → {row['destination']}]"
            )
            with st.expander(header):
                st.write(f"**車両:** {row['vehicle_type']} | **ステータス:** {row['status']}")
                st.write(f"**予定金額:** {row['planned_fare']}円")
                l_s = f"[📍 出発地]({u_base}{row['pickup_location']})"
                l_e = f"[🏁 目的地]({u_base}{row['destination']})"
                st.markdown(f"{l_s} / {l_e}")
                if st.button(f"✏️ 編集・割当", key=f"edit_{row['id']}"):
                    st.session_state.edit_id = row['id']
                    st.rerun()
        st.divider()
        st.subheader("👤 ドライバー別状況")
        for user, group in ass_df.groupby('assigned_to'):
            st.markdown(f"**{user} さん** ({len(group)}件)")
            current_date = None
            for _, row in group.iterrows():
                day_str = get_weekday(row['date'])
                if row['date'] != current_date:
                    st.markdown(f"#### 🗓️ {row['date']} {day_str}")
                    current_date = row['date']
                header = (
                    f"{row['time']} {row['customer_name']}様 "
                    f"[{row['pickup_location']} → {row['destination']}]"
                )
                with st.expander(header):
                    st.write(f"**車両:** {row['vehicle_type']} | **ステータス:** {row['status']}")
                    st.write(f"**予定金額:** {row['planned_fare']}円")
                    l_s = f"[📍 出発地]({u_base}{row['pickup_location']})"
                    l_e = f"[🏁 目的地]({u_base}{row['destination']})"
                    st.markdown(f"{l_s} / {l_e}")
                    if st.button(f"✏️ 編集", key=f"edit_{row['id']}"):
                        st.session_state.edit_id = row['id']
                        st.rerun()

def show_history():
    st.header("✅ 完了・キャンセル履歴")
    df = get_all_reservations()
    if df.empty:
        st.info("データがありません.")
        return
    arch_df = df[df['status'].isin(["完了", "キャンセル"])].copy()
    csv = arch_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        "📥 全履歴CSV", 
        data=csv, 
        file_name=f"hist_{datetime.now().strftime('%Y%m%d')}.csv", 
        mime="text/csv"
    )
    if st.session_state.user_role == "Admin":
        st.subheader("📈 全体月別集計")
        arch_df['date_dt'] = pd.to_datetime(arch_df['date'], errors='coerce')
        arch_df['ym'] = arch_df['date_dt'].dt.to_period('M').astype(str)
        summ = []
        for m in sorted(arch_df['ym'].unique(), reverse=True):
            m_df = arch_df[arch_df['ym'] == m]
            summ.append({
                "年月": m, 
                "完了": len(m_df[m_df['status']=="完了"]), 
                "キャンセル": len(m_df[m_df['status']=="キャンセル"]), 
                "金額": m_df[m_df['status']=="完了"]['fare'].sum()
            })
        if summ: st.table(pd.DataFrame(summ))
        st.divider()
    if st.session_state.user_role == "Operator":
        st.subheader("📄 自分の履歴")
        my_h = arch_df[arch_df['assigned_to'] == st.session_state.username]
        for _, row in my_h.iterrows():
            with st.expander(f"{row['date']} {row['customer_name']}様 ({row['status']} / {row['fare']}円)"):
                st.write(f"**ルート:** {row['pickup_location']} → {row['destination']}")
                st.write(f"**距離:** {row['distance']} km | **時間:** {row['duration']}")
                if st.button(f"✏️ 再編集", key=f"reedit_{row['id']}"):
                    st.session_state.edit_id = row['id']
                    st.rerun()
    elif st.session_state.user_role == "Admin":
        st.subheader("👤 ドライバー別 実績")
        for user, group in arch_df.groupby('assigned_to'):
            u_lab = user if user else "未割当"
            tot_f = group[group['status']=='完了']['fare'].sum()
            st.markdown(f"**{u_lab} さん** ({len(group)}件 / 合計: {tot_f:,})")
            for _, row in group.iterrows():
                with st.expander(f"{row['date']} {row['customer_name']}様 ({row['status']} / {row['fare']}円)"):
                    st.write(f"**ルート:** {row['pickup_location']} → {row['destination']}")
                    if st.button(f"✏️ 再編集", key=f"reedit_{row['id']}"):
                        st.session_state.edit_id = row['id']
                        st.rerun()
                    if st.button(f"🗑 履歴削除", key=f"del_old_{row['id']}"):
                        delete_reservation(row['id'], True)
                        st.rerun()

def show_trash():
    st.header("♻️ 削除済みデータの復元")
    conn = sqlite3.connect(DB_NAME)
    d_df = pd.read_sql_query("SELECT * FROM reservations WHERE deleted = 1", conn)
    conn.close()
    if d_df.empty:
        st.info("ゴミ箱は空です.")
        return
    for _, row in d_df.iterrows():
        with st.expander(f"{row['date']} {row['time']} {row['customer_name']}様"):
            st.write(f"**ルート:** {row['pickup_location']} → {row['destination']}")
            if st.button(f"♻️ 復元する", key=f"res_{row['id']}"):
                restore_reservation(row['id'])
                st.success("復元しました！")
                st.rerun()

def show_user_management():
    st.header("👥 システムユーザー管理")
    with st.form("user_form"):
        col1, col2, col3 = st.columns(3)
        with col1: u_name = st.text_input("新ユーザー名")
        with col2: u_pwd = st.text_input("新パスワード", type="password")
        with col3: u_role = st.selectbox("権限", ["Admin", "Operator"])
        if st.form_submit_button("ユーザーを追加"):
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            try:
                c.execute(
                    "INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                    (u_name, u_pwd, u_role)
                )
                conn.commit()
                st.success("追加しました！")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("既に存在します。")
            finally:
                conn.close()
    st.divider()
    st.subheader("登録ユーザー一覧")
    users_df = get_all_users()
    for _, row in users_df.iterrows():
        with st.expander(f"👤 {row['username']} ({row['role']})"):
            if st.button(f"✏️ 編集", key=f"u_edit_{row['username']}"):
                st.session_state.edit_user_id = row['username']
                st.rerun()
            if st.button(f"🗑 削除", key=f"u_del_{row['username']}"):
                delete_user(row['username'])
                st.rerun()

# ==========================================
# 4. メイン司令塔 (Router)
# ==========================================
def main():
    st.set_page_config(page_title="介護タクシー管理", layout="wide")
    init_db()
    
    s1 = '<style>'
    s2 = 'html, body, [class*="st-"] { font-size: 16px !important; } '
    s3 = 'div[data-testid="stExpander"] { font-size: 18px !important; font-weight: bold !important; }'
    s4 = '</style>'
    st.markdown(s1 + s2 + s3 + s4, unsafe_allow_html=True)

    for key, val in {
        'logged_in': False, 'user_role': None, 'username': None,
        'edit_id': None, 'edit_user_id': None, 'choice': "予約一覧", 'saved': False
    }.items():
        if key not in st.session_state: st.session_state[key] = val

    if not st.session_state.logged_in:
        show_login()
        return

    with st.sidebar:
        st.header("🚀 メニュー")
        if st.button("📋 予約一覧", use_container_width=True):
            st.session_state.choice = "予約一覧"
            st.rerun()
        if st.button("📅 新規予約追加", type="primary", use_container_width=True):
            st.session_state.choice = "新規予約追加"
            st.rerun()
        if st.button("✅ 完了・キャンセル履歴", use_container_width=True):
            st.session_state.choice = "完了・キャンセル履歴"
            st.rerun()
        if st.session_state.user_role == "Admin":
            st.divider()
            st.subheader("⚙️ 管理者設定")
            if st.button("🗑 管理者用ゴミ箱", use_container_width=True):
                st.session_state.choice = "🗑 管理者用ゴミ箱"
                st.rerun()
            if st.button("👥 ユーザー管理", use_container_width=True):
                st.session_state.choice = "⚙️ ユーザー管理"
                st.rerun()
        st.divider()
        if st.button("🚪 ログアウト", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.session_state.user_role = None
            st.rerun()

    st.title(f"🚖 介護タクシー管理 ({st.session_state.user_role})")

    if st.session_state.edit_user_id:
        show_user_edit()
    elif st.session_state.edit_id:
        show_reservation_edit()
    elif st.session_state.choice == "新規予約追加":
        show_new_reservation()
    elif st.session_state.choice == "予約一覧":
        show_reservation_list()
    elif st.session_state.choice == "完了・キャンセル履歴":
        show_history()
    elif st.session_state.choice == "🗑 管理者用ゴミ箱":
        show_trash()
    elif st.session_state.choice == "⚙️ ユーザー管理":
        show_user_management()

if __name__ == '__main__':
    main()

