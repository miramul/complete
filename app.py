import os
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from instagrapi import Client
import json
from datetime import datetime

SENT_USERS_FILE = "sent_users.txt"

def delete_session_file(username):
    session_file = f"session_{username}.json"
    if os.path.exists(session_file):
        os.remove(session_file)
        print(f"セッションファイル {session_file} を削除しました。")

def login_with_cookie(username, password):
    if not username or not password:
        return None

    cl = Client()
    session_file = f"session_{username}.json"

    # 既存のセッションでログインを試みる
    if os.path.exists(session_file):
        try:
            cl.load_settings(session_file)
            cl.login(username, password)
            print(f"✅ {username} クッキーを使ってログイン成功！")
            return cl
        except Exception as e:
            print(f"⚠️ {username} クッキーの読み込みに失敗: {e}。セッションファイルを削除して再ログインします。")
            delete_session_file(username)

    # 通常のログインを試みる
    try:
        cl.login(username, password)
        cl.dump_settings(session_file)
        print(f"✅ {username} 通常のログイン成功！")
        return cl
    except Exception as e:
        error_msg = str(e).lower()
        if "checkpoint" in error_msg:
            print(f"❌ {username} ログイン失敗: セキュリティチェックポイントが検出されました。Instagram アプリでログインして確認してください。")
        elif "incorrect password" in error_msg or "invalid credentials" in error_msg:
            print(f"❌ {username} ログイン失敗: ユーザー名またはパスワードが間違っています。")
        elif "spam" in error_msg or "temporary block" in error_msg:
            print(f"❌ {username} ログイン失敗: アカウントが一時的にブロックされています。しばらく待ってから試してください。")
        else:
            print(f"❌ {username} ログイン失敗: {e}")
        return None

def get_user_followers_chunked(cl, username, chunks=2, chunk_size=50, max_retries=5):
    """改善されたフォロワー取得機能"""
    all_followers = []
    user_id = None
    
    # ユーザーIDを取得
    for attempt in range(max_retries):
        try:
            user_id = cl.user_id_from_username(username.strip())
            print(f"✅ {username} のユーザーID取得成功: {user_id}")
            break
        except Exception as e:
            error_msg = str(e).lower()
            print(f"⚠️ {username} のIDの取得に失敗 (試行 {attempt+1}): {error_msg}")
            
            if "not found" in error_msg:
                print(f"⚠️ ユーザー {username} が存在しないか、アクセスできません。正確なユーザー名を確認してください。")
                return []
            elif "rate limit" in error_msg or "too many requests" in error_msg:
                wait_time = 30 + random.randint(20, 60) * (attempt + 1)
                print(f"⚠️ レート制限に達しました。{wait_time}秒待機してから再試行します...")
                time.sleep(wait_time)
            else:
                wait_time = 15 + random.randint(5, 20) * (attempt + 1)
                print(f"⏱️ {wait_time}秒後にリトライします...")
                time.sleep(wait_time)
    
    if user_id is None:
        print(f"❌ {username} のユーザーIDが取得できませんでした")
        return []
    
    # より緩やかなチャンク取得
    for chunk in range(chunks):
        print(f"👥 {username} のフォロワー取得中... (チャンク {chunk+1}/{chunks})")
        
        # チャンク間の待機時間（最初のチャンクの前は待機しない）
        if chunk > 0:
            wait_time = 30 + random.randint(15, 45)
            print(f"⏱️ レート制限対策のため {wait_time}秒待機します...")
            time.sleep(wait_time)
        
        for attempt in range(max_retries):
            try:
                # 徐々に量を減らすことでレート制限を回避
                reduced_chunk_size = max(20, chunk_size // (attempt + 1))
                print(f"👥 {reduced_chunk_size}人のフォロワーを取得しています...")
                
                # APIからフォロワーを取得
                followers_chunk = cl.user_followers(user_id, amount=reduced_chunk_size)
                
                if not followers_chunk:
                    print(f"⚠️ フォロワーデータが空です。アカウントに問題があるか、フォロワーがいない可能性があります。")
                    if attempt < max_retries - 1:
                        wait_time = 20 + random.randint(10, 30)
                        print(f"⏱️ {wait_time}秒後に再試行します...")
                        time.sleep(wait_time)
                        continue
                    else:
                        break
                
                chunk_followers = list(followers_chunk.values())
                all_followers.extend(chunk_followers)
                
                print(f"✅ {username} のフォロワー {len(chunk_followers)}人 取得成功！ (チャンク {chunk+1})")
                break  # 成功したらリトライループを抜ける
                
            except Exception as e:
                error_msg = str(e).lower()
                print(f"⚠️ {username} のフォロワー取得に失敗 (チャンク {chunk+1}, 試行 {attempt+1}): {error_msg}")
                
                # エラーの種類に応じた処理
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    wait_time = 45 + random.randint(30, 90) * (attempt + 1)
                    print(f"⚠️ レート制限のため {wait_time}秒待機します...")
                elif "not found" in error_msg:
                    print(f"❌ ユーザー {username} が見つかりません。")
                    return all_followers
                elif "private" in error_msg:
                    print(f"❌ ユーザー {username} は非公開アカウントです。")
                    return all_followers
                else:
                    wait_time = 30 + random.randint(15, 45) * (attempt + 1)
                    print(f"⏱️ {wait_time}秒後にリトライします...")
                
                time.sleep(wait_time)
                
                if attempt == max_retries - 1:
                    print(f"❌ チャンク {chunk+1} のフォロワー取得に失敗しましたが、これまでに取得したフォロワーで続行します。")
    
    if all_followers:
        print(f"✅ 合計 {len(all_followers)}人のフォロワーを取得しました。")
    else:
        print(f"⚠️ フォロワーを取得できませんでした。API制限に達したかアカウントに問題がある可能性があります。")
    
    return all_followers

def get_user_following_chunked(cl, username, chunks=2, chunk_size=50, max_retries=5):
    """フォロー中のユーザーを取得する機能"""
    all_following = []
    user_id = None
    
    # ユーザーIDを取得
    for attempt in range(max_retries):
        try:
            user_id = cl.user_id_from_username(username.strip())
            print(f"✅ {username} のユーザーID取得成功: {user_id}")
            break
        except Exception as e:
            error_msg = str(e).lower()
            print(f"⚠️ {username} のIDの取得に失敗 (試行 {attempt+1}): {error_msg}")
            
            if "not found" in error_msg:
                print(f"⚠️ ユーザー {username} が存在しないか、アクセスできません。正確なユーザー名を確認してください。")
                return []
            elif "rate limit" in error_msg or "too many requests" in error_msg:
                wait_time = 30 + random.randint(20, 60) * (attempt + 1)
                print(f"⚠️ レート制限に達しました。{wait_time}秒待機してから再試行します...")
                time.sleep(wait_time)
            else:
                wait_time = 15 + random.randint(5, 20) * (attempt + 1)
                print(f"⏱️ {wait_time}秒後にリトライします...")
                time.sleep(wait_time)
    
    if user_id is None:
        print(f"❌ {username} のユーザーIDが取得できませんでした")
        return []
    
    # より緩やかなチャンク取得
    for chunk in range(chunks):
        print(f"👥 {username} のフォロー中ユーザー取得中... (チャンク {chunk+1}/{chunks})")
        
        # チャンク間の待機時間（最初のチャンクの前は待機しない）
        if chunk > 0:
            wait_time = 30 + random.randint(15, 45)
            print(f"⏱️ レート制限対策のため {wait_time}秒待機します...")
            time.sleep(wait_time)
        
        for attempt in range(max_retries):
            try:
                # 徐々に量を減らすことでレート制限を回避
                reduced_chunk_size = max(20, chunk_size // (attempt + 1))
                print(f"👥 {reduced_chunk_size}人のフォロー中ユーザーを取得しています...")
                
                # APIからフォロー中ユーザーを取得
                following_chunk = cl.user_following(user_id, amount=reduced_chunk_size)
                
                if not following_chunk:
                    print(f"⚠️ フォロー中ユーザーデータが空です。アカウントに問題があるか、フォロー中のユーザーがいない可能性があります。")
                    if attempt < max_retries - 1:
                        wait_time = 20 + random.randint(10, 30)
                        print(f"⏱️ {wait_time}秒後に再試行します...")
                        time.sleep(wait_time)
                        continue
                    else:
                        break
                
                chunk_following = list(following_chunk.values())
                all_following.extend(chunk_following)
                
                print(f"✅ {username} のフォロー中ユーザー {len(chunk_following)}人 取得成功！ (チャンク {chunk+1})")
                break  # 成功したらリトライループを抜ける
                
            except Exception as e:
                error_msg = str(e).lower()
                print(f"⚠️ {username} のフォロー中ユーザー取得に失敗 (チャンク {chunk+1}, 試行 {attempt+1}): {error_msg}")
                
                # エラーの種類に応じた処理
                if "rate limit" in error_msg or "too many requests" in error_msg:
                    wait_time = 45 + random.randint(30, 90) * (attempt + 1)
                    print(f"⚠️ レート制限のため {wait_time}秒待機します...")
                elif "not found" in error_msg:
                    print(f"❌ ユーザー {username} が見つかりません。")
                    return all_following
                elif "private" in error_msg:
                    print(f"❌ ユーザー {username} は非公開アカウントです。")
                    return all_following
                else:
                    wait_time = 30 + random.randint(15, 45) * (attempt + 1)
                    print(f"⏱️ {wait_time}秒後にリトライします...")
                
                time.sleep(wait_time)
                
                if attempt == max_retries - 1:
                    print(f"❌ チャンク {chunk+1} のフォロー中ユーザー取得に失敗しましたが、これまでに取得したユーザーで続行します。")
    
    if all_following:
        print(f"✅ 合計 {len(all_following)}人のフォロー中ユーザーを取得しました。")
    else:
        print(f"⚠️ フォロー中ユーザーを取得できませんでした。API制限に達したかアカウントに問題がある可能性があります。")
    
    return all_following

def save_users_to_file(users, filename, user_type):
    """ユーザー情報をJSONファイルに保存"""
    folder_path = "followers_data"
    
    # フォルダが存在しない場合は作成
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    
    filepath = os.path.join(folder_path, filename)
    
    # ユーザー情報を抽出して保存用の辞書リストを作成
    users_data = []
    for user in users:
        try:
            user_info = {
                "username": user.username,
                "full_name": user.full_name,
                "user_id": user.pk,
                "is_private": user.is_private,
                "follower_count": getattr(user, 'follower_count', 0),
                "following_count": getattr(user, 'following_count', 0),
                "media_count": getattr(user, 'media_count', 0),
                "biography": getattr(user, 'biography', ''),
                "external_url": getattr(user, 'external_url', '')
            }
            users_data.append(user_info)
        except Exception as e:
            print(f"⚠️ {user_type}情報の抽出中にエラー: {e}")
    
    # JSON形式で保存
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, ensure_ascii=False, indent=2)
    
    return filepath

# 共通ユーザーを見つけて保存する関数を追加
def find_and_save_common_users(first_following, first_followers, second_followers, timestamp):
    """3つのリストに共通するユーザーを見つけてJSONファイルに保存"""
    # ユーザー名をキーとしたディクショナリを作成
    first_following_dict = {user.username: user for user in first_following}
    first_followers_dict = {user.username: user for user in first_followers}
    second_followers_dict = {user.username: user for user in second_followers}
    
    # 3つのリストに共通するユーザー名を取得
    common_usernames = set(first_following_dict.keys()) & set(first_followers_dict.keys()) & set(second_followers_dict.keys())
    
    # 共通するユーザーオブジェクトのリストを作成
    common_users = [first_following_dict[username] for username in common_usernames]
    
    # 結果がない場合
    if not common_users:
        print("⚠️ 3つのリストに共通するユーザーが見つかりませんでした。")
        return None, 0
    
    # 共通ユーザーをJSONファイルに保存
    filename = f"common_users_{timestamp}.json"
    json_path = save_users_to_file(common_users, filename, "共通ユーザー")
    
    return json_path, len(common_users)

# DMの送信に関する機能
def load_sent_users():
    if os.path.exists(SENT_USERS_FILE):
        with open(SENT_USERS_FILE, "r", encoding="utf-8") as file:
            return set(file.read().splitlines())
    return set()

def save_sent_user(username):
    with open(SENT_USERS_FILE, "a", encoding="utf-8") as file:
        file.write(username + "\n")

def load_json_users(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return [user["username"] for user in data if "username" in user]
    except Exception as e:
        print(f"⚠️ JSONファイルの読み込みに失敗しました: {e}")
        return []

def follow_if_not_following(cl, username):
    try:
        user_id = cl.user_id_from_username(username)
        friendship = cl.user_info(user_id).friendship_status
        if not friendship.following:
            cl.user_follow(user_id)
            print(f"✅ {username} をフォローしました！")
            time.sleep(random.randint(600, 1200))
        else:
            print(f"➡️ {username} はすでにフォローしています。")
    except Exception as e:
        print(f"❌ {username} のフォローに失敗: {e}")

def export_instagram_data():
    # ログウィンドウをクリア
    log_text.delete(1.0, tk.END)
    
    username = username_entry.get("1.0", tk.END).strip()
    password = password_entry.get("1.0", tk.END).strip()
    target_accounts = [t.strip() for t in target_entry.get("1.0", tk.END).strip().split(',') if t.strip()]
    
    def log(message):
        log_text.insert(tk.END, message + "\n")
        log_text.see(tk.END)
        log_text.update()
        print(message)

    if not (username and password):
        messagebox.showerror("エラー", "ログイン情報を入力してください。")
        return
    
    if not target_accounts:
        messagebox.showerror("エラー", "対象アカウントを入力してください。")
        return
    
    # 少なくとも2つのアカウントが必要かチェック
    if len(target_accounts) < 2:
        messagebox.showerror("エラー", "少なくとも2つのアカウントを入力してください。")
        return

    show_loading("Instagramにログイン中...")
    log(f"🔑 {username} でInstagramにログイン中...")
    cl = login_with_cookie(username, password)
    hide_loading()

    if not cl:
        log("❌ ログインに失敗しました。ユーザー名とパスワードを確認してください。")
        messagebox.showerror("エラー", "ログインに失敗しました。")
        return
    
    log(f"✅ {username} としてログイン成功！")
    
    # 実行時のタイムスタンプを取得
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 対象アカウントのフォロワーとフォロー中のユーザーを取得
    all_followers = []
    all_following = []
    followers_files = []
    following_files = []
    
    # 1番目のターゲットアカウントのフォロー中リスト
    first_target_following = []
    # 1番目のターゲットアカウントのフォロワーリスト
    first_target_followers = []
    # 2番目のターゲットアカウントのフォロワーリスト
    second_target_followers = []
    
    for i, target in enumerate(target_accounts):
        # フォロワーを取得
        show_loading(f"{target} のフォロワーを取得中... ({i+1}/{len(target_accounts)})")
        log(f"👥 {target} のフォロワーを取得中...")
        
        # 対象アカウント間で十分な待機時間を設ける
        if i > 0:
            wait_time = 45 + random.randint(15, 45)
            log(f"⏱️ レート制限対策のため {wait_time}秒待機します...")
            time.sleep(wait_time)
        
        target_followers = get_user_followers_chunked(cl, target, chunks=2, chunk_size=50)
        
        if not target_followers:
            log(f"⚠️ {target} のフォロワーを取得できませんでした。")
        else:
            all_followers.extend(target_followers)
            
            # 1番目と2番目のターゲットアカウントのフォロワーを保存
            if i == 0:
                first_target_followers = target_followers
            elif i == 1:
                second_target_followers = target_followers
            
            # フォロワーをJSONファイルに保存
            filename = f"followers_{target}_{timestamp}.json"
            json_path = save_users_to_file(target_followers, filename, "フォロワー")
            followers_files.append(json_path)
            
            log(f"✅ {target} のフォロワー {len(target_followers)}人 をJSONファイルに保存しました。")
            log(f"📄 JSON: {json_path}")
        
        # 1番目のアカウントに対してのみフォロー中ユーザーを取得
        if i == 0:
            # フォロー中のユーザーを取得
            show_loading(f"{target} のフォロー中ユーザーを取得中... ({i+1}/{len(target_accounts)})")
            log(f"👥 {target} のフォロー中ユーザーを取得中...")
            
            # フォロワー取得とフォロー中ユーザー取得の間に待機時間を設ける
            wait_time = 30 + random.randint(10, 30)
            log(f"⏱️ レート制限対策のため {wait_time}秒待機します...")
            time.sleep(wait_time)
            
            target_following = get_user_following_chunked(cl, target, chunks=2, chunk_size=50)
            
            if not target_following:
                log(f"⚠️ {target} のフォロー中ユーザーを取得できませんでした。")
            else:
                all_following.extend(target_following)
                first_target_following = target_following
                
                # フォロー中ユーザーをJSONファイルに保存
                filename = f"following_{target}_{timestamp}.json"
                json_path = save_users_to_file(target_following, filename, "フォロー中")
                following_files.append(json_path)
                
                log(f"✅ {target} のフォロー中ユーザー {len(target_following)}人 をJSONファイルに保存しました。")
                log(f"📄 JSON: {json_path}")
    
    hide_loading()
    
    # 共通ユーザーを見つけて保存
    common_path = None
    common_count = 0
    
    show_loading("共通ユーザーを検索中...")
    log(f"🔍 3つのリストに共通するユーザーを検索中...")
    
    if first_target_following and first_target_followers and second_target_followers:
        common_path, common_count = find_and_save_common_users(
            first_target_following,
            first_target_followers,
            second_target_followers,
            timestamp
        )
        
        if common_path:
            log(f"✅ 共通ユーザー {common_count}人 をJSONファイルに保存しました。")
            log(f"📄 JSON: {common_path}")
        else:
            log(f"⚠️ 共通ユーザーは見つかりませんでした。")
    else:
        log(f"⚠️ 一部のデータが取得できなかったため、共通ユーザーの検索をスキップします。")
    
    hide_loading()
    
    # 結果を表示
    followers_saved = len(followers_files)
    following_saved = len(following_files)
    
    result_message = f"Instagram データ取得結果:\n\n"
    result_message += f"対象アカウント: {len(target_accounts)}件\n"
    result_message += f"取得したフォロワー: {len(all_followers)}人\n"
    result_message += f"取得したフォロー中ユーザー: {len(all_following)}人\n"
    
    if common_path:
        result_message += f"共通ユーザー: {common_count}人\n"
    
    result_message += f"\nファイル保存場所: {os.path.abspath('followers_data')}"
    
    log(result_message)
    messagebox.showinfo("結果", result_message)
    
    # 共通ユーザーにDMを送信するかどうか確認
    if common_path:
        send_dm_confirm = messagebox.askyesno("確認", "共通ユーザーにDMを送信しますか？")
        if send_dm_confirm:
            notebook.select(dm_tab)
            json_file_entry.delete(1.0, tk.END)
            json_file_entry.insert(tk.END, common_path)

    # ファイルを開くオプションを提供
    if followers_saved > 0 or following_saved > 0 or common_path:
        open_folder = messagebox.askyesno("確認", "データフォルダを開きますか？")
        if open_folder:
            # プラットフォームに依存しない方法でフォルダを開く
            folder_path = os.path.abspath("followers_data")
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(folder_path)
                elif os.name == 'posix':  # macOS & Linux
                    import subprocess
                    import sys
                    subprocess.Popen(['open', folder_path] if sys.platform == 'darwin' else ['xdg-open', folder_path])
            except Exception as e:
                log(f"⚠️ フォルダを開く際にエラーが発生しました: {e}")
                log(f"📂 手動でこのフォルダを開いてください: {folder_path}")

def send_dm():
    # ログウィンドウをクリア
    dm_log_text.delete(1.0, tk.END)
    
    def log(message):
        dm_log_text.insert(tk.END, message + "\n")
        dm_log_text.see(tk.END)
        dm_log_text.update()
        print(message)
    
    username = dm_username_entry.get("1.0", tk.END).strip()
    password = dm_password_entry.get("1.0", tk.END).strip()
    json_file_path = json_file_entry.get("1.0", tk.END).strip()
    dm_message = message_entry.get("1.0", tk.END).strip()

    if not (username and password and json_file_path and dm_message):
        messagebox.showerror("エラー", "すべての情報を入力してください。")
        return

    if not os.path.exists(json_file_path):
        messagebox.showerror("エラー", "指定されたJSONファイルが見つかりません。")
        return

    show_loading("Instagramにログイン中...")
    log(f"🔑 {username} でInstagramにログイン中...")
    cl = login_with_cookie(username, password)
    hide_loading()

    if not cl:
        log("❌ ログインに失敗しました。ユーザー名とパスワードを確認してください。")
        messagebox.showerror("エラー", "ログインに失敗しました。")
        return
    
    log(f"✅ {username} としてログイン成功！")

    sent_users = load_sent_users()
    all_target_users = load_json_users(json_file_path)
    
    if not all_target_users:
        log("⚠️ JSONファイルからユーザー名を読み込めませんでした。")
        messagebox.showerror("エラー", "JSONファイルからユーザー名を読み込めませんでした。")
        return
    
    # 既に送信済みのユーザーを除外
    new_target_users = [user for user in all_target_users if user not in sent_users]
    
    if not new_target_users:
        log("⚠️ 送信可能な新規ユーザーが見つかりませんでした。")
        messagebox.showerror("エラー", "送信可能な新規ユーザーが見つかりませんでした。")
        return

    success_count = int(success_count_entry.get("1.0", tk.END).strip() or "0")
    if success_count <= 0:
        success_count = len(new_target_users)

    # 処理するユーザー数を制限
    new_target_users = new_target_users[:success_count]
    
    success_users, failed_users = [], []
    progress_var.set(0)
    progress_bar["maximum"] = len(new_target_users)
    
    for i, user in enumerate(new_target_users):
        try:
            status_label.config(text=f"処理中: {user} ({i+1}/{len(new_target_users)})")
            root.update()
            log(f"🔄 {user} に処理を開始しています... ({i+1}/{len(new_target_users)})")
            
            follow_if_not_following(cl, user)
            user_info = cl.user_info_by_username(user.strip())
            user_id = user_info.pk
            profile_name = user_info.full_name if user_info.full_name else user
            personalized_message = f"{profile_name}様\n\n{dm_message}"
            
            log(f"💬 {user} にDMを送信中...")
            cl.direct_send(personalized_message, [user_id])
            
            wait_time = random.randint(1500, 2100)
            log(f"⏱️ 次のユーザーまで {wait_time/60:.1f}分待機しています...")
            time.sleep(wait_time)
            
            success_users.append(user.strip())
            save_sent_user(user.strip())
            log(f"✅ {user} へのDM送信成功！")
            
            progress_var.set(i + 1)
            root.update()
        except Exception as e:
            log(f"❌ {user} へのDM送信に失敗: {e}")
            failed_users.append(user.strip())
            time.sleep(60)

    result_message = f"DM送信結果:\n\n成功: {len(success_users)}件\n失敗: {len(failed_users)}件"
    status_label.config(text="完了しました。")
    log(f"🏁 処理完了\n{result_message}")
    messagebox.showinfo("結果", result_message)

def show_loading(text):
    loading_label.config(text=text)
    root.update()

def hide_loading():
    loading_label.config(text="")
    root.update()

def browse_json_file():
    file_path = filedialog.askopenfilename(
        title="JSONファイルを選択",
        filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
    )
    if file_path:
        json_file_entry.delete(1.0, tk.END)
        json_file_entry.insert(tk.END, file_path)

def import_settings():
    """設定ファイルからデータをインポート"""
    file_path = filedialog.askopenfilename(
        title="設定ファイルを選択",
        filetypes=[("JSON ファイル", "*.json"), ("全てのファイル", "*.*")]
    )
    
    if not file_path:
        return
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        # フォロワー取得設定を読み込み
        if 'username' in settings:
            username_entry.delete("1.0", tk.END)
            username_entry.insert("1.0", settings.get('username', ''))
        
        if 'password' in settings:
            password_entry.delete("1.0", tk.END)
            password_entry.insert("1.0", settings.get('password', ''))
        
        if 'target_accounts' in settings:
            target_entry.delete("1.0", tk.END)
            target_entry.insert("1.0", ', '.join(settings.get('target_accounts', [])))
        
        # DM送信設定を読み込み
        if 'dm_username' in settings:
            dm_username_entry.delete("1.0", tk.END)
            dm_username_entry.insert("1.0", settings.get('dm_username', ''))
        
        if 'dm_password' in settings:
            dm_password_entry.delete("1.0", tk.END)
            dm_password_entry.insert("1.0", settings.get('dm_password', ''))
        
        if 'dm_message' in settings:
            message_entry.delete("1.0", tk.END)
            message_entry.insert("1.0", settings.get('dm_message', ''))
        
        if 'success_count' in settings:
            success_count_entry.delete("1.0", tk.END)
            success_count_entry.insert("1.0", str(settings.get('success_count', '0')))
        
        messagebox.showinfo("成功", "設定をインポートしました。")
    except Exception as e:
        messagebox.showerror("エラー", f"設定のインポート中にエラーが発生しました: {e}")

def export_settings():
    """現在の設定をファイルにエクスポート"""
    file_path = filedialog.asksaveasfilename(
        title="設定ファイル保存",
        defaultextension=".json",
        filetypes=[("JSON ファイル", "*.json"), ("全てのファイル", "*.*")]
    )
    
    if not file_path:
        return
    
    try:
        settings = {
            'username': username_entry.get("1.0", tk.END).strip(),
            'password': password_entry.get("1.0", tk.END).strip(),
            'target_accounts': [t.strip() for t in target_entry.get("1.0", tk.END).strip().split(',') if t.strip()],
            'dm_username': dm_username_entry.get("1.0", tk.END).strip(),
            'dm_password': dm_password_entry.get("1.0", tk.END).strip(),
            'dm_message': message_entry.get("1.0", tk.END).strip(),
            'success_count': success_count_entry.get("1.0", tk.END).strip(),
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
        
        messagebox.showinfo("成功", "設定をエクスポートしました。")
    except Exception as e:
        messagebox.showerror("エラー", f"設定のエクスポート中にエラーが発生しました: {e}")

# メインウィンドウの設定
root = tk.Tk()
root.title("Instagram フォロワー・フォロー抽出＆DM送信ツール")
root.geometry("700x800")

# メニューバーの作成
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

file_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="ファイル", menu=file_menu)
file_menu.add_command(label="設定をインポート", command=import_settings)
file_menu.add_command(label="設定をエクスポート", command=export_settings)
file_menu.add_separator()
file_menu.add_command(label="終了", command=root.quit)

# タブの作成
notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

# フォロワー取得タブ
follower_tab = ttk.Frame(notebook, padding=20)
notebook.add(follower_tab, text="フォロワー取得")

# DM送信タブ
dm_tab = ttk.Frame(notebook, padding=20)
notebook.add(dm_tab, text="DM送信")

# フォロワー取得タブの内容
ttk.Label(follower_tab, text="📷 Instagram Username").pack(anchor="w")
username_entry = scrolledtext.ScrolledText(follower_tab, height=1, width=30)
username_entry.pack(fill=tk.X, pady=(0, 10))

ttk.Label(follower_tab, text="🔑 Instagram Password").pack(anchor="w")
password_entry = scrolledtext.ScrolledText(follower_tab, height=1, width=30)
password_entry.pack(fill=tk.X, pady=(0, 10))

ttk.Label(follower_tab, text="🎯 対象アカウント (カンマ区切り)").pack(anchor="w")
target_entry = scrolledtext.ScrolledText(follower_tab, height=2, width=30)
target_entry.pack(fill=tk.X, pady=(0, 10))

# 実行ボタン
execute_button = ttk.Button(follower_tab, text="フォロワー・フォロー取得開始", command=export_instagram_data)
execute_button.pack(pady=10)

# ローディングラベル
loading_label = ttk.Label(follower_tab, text="", foreground="blue")
loading_label.pack(pady=5)

# ログ表示エリア
ttk.Label(follower_tab, text="📝 ログ").pack(anchor="w")
log_text = scrolledtext.ScrolledText(follower_tab, height=30, width=60)
log_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

# DM送信タブの内容
ttk.Label(dm_tab, text="📷 Instagram Username").pack(anchor="w")
dm_username_entry = scrolledtext.ScrolledText(dm_tab, height=1, width=30)
dm_username_entry.pack(fill=tk.X, pady=(0, 10))

ttk.Label(dm_tab, text="🔑 Instagram Password").pack(anchor="w")
dm_password_entry = scrolledtext.ScrolledText(dm_tab, height=1, width=30)
dm_password_entry.pack(fill=tk.X, pady=(0, 10))

ttk.Label(dm_tab, text="📁 JSONファイル").pack(anchor="w")
json_file_frame = ttk.Frame(dm_tab)
json_file_frame.pack(fill=tk.X)

json_file_entry = scrolledtext.ScrolledText(json_file_frame, height=1, width=30)
json_file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
browse_button = ttk.Button(json_file_frame, text="参照...", command=browse_json_file)
browse_button.pack(side=tk.RIGHT, padx=(5, 0))

ttk.Label(dm_tab, text="💬 DM本文").pack(anchor="w")
message_entry = scrolledtext.ScrolledText(dm_tab, height=5, width=30)
message_entry.pack(fill=tk.X, pady=(0, 10))

ttk.Label(dm_tab, text="🔢 送信数 (空白または0で全て)").pack(anchor="w")
success_count_entry = scrolledtext.ScrolledText(dm_tab, height=1, width=30)
success_count_entry.pack(fill=tk.X, pady=(0, 10))
success_count_entry.insert(tk.END, "0")

progress_var = tk.DoubleVar()
ttk.Label(dm_tab, text="進捗状況:").pack(anchor="w", pady=(10, 0))
progress_bar = ttk.Progressbar(dm_tab, variable=progress_var, maximum=100)
progress_bar.pack(fill=tk.X, pady=(5, 10))

status_label = ttk.Label(dm_tab, text="")
status_label.pack(anchor="w")

# DM送信ボタン
send_button = ttk.Button(dm_tab, text="🚀 DM送信開始", command=send_dm)
send_button.pack(pady=10)

# DMログ表示エリア
ttk.Label(dm_tab, text="📝 ログ").pack(anchor="w")
dm_log_text = scrolledtext.ScrolledText(dm_tab, height=10, width=60)
dm_log_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

# フォロワータブのヘルプテキスト
follower_help_text = """
フォロワー取得の使い方:
1. Instagramのユーザー名とパスワードを入力してください。
2. 対象アカウント（フォロワーとフォローを取得したいアカウント）を入力してください。複数ある場合はカンマで区切ってください。
   少なくとも2つのアカウント名が必要です。
3. 「フォロワー・フォロー取得開始」ボタンをクリックしてください。
4. 処理が完了すると、JSONファイルに保存され、結果ダイアログが表示されます。
5. 3つのリスト（1番目のアカウントのフォロー、1番目のアカウントのフォロワー、2番目のアカウントのフォロワー）
   に共通するユーザーが自動的に検出され、別のJSONファイルに保存されます。
"""
ttk.Label(follower_tab, text=follower_help_text, wraplength=550, justify="left").pack(anchor="w")

# DMタブのヘルプテキスト
dm_help_text = """
DM送信の使い方:
1. Instagramのユーザー名とパスワードを入力してください。
2. 「参照」ボタンをクリックして、共通ユーザーが保存されたJSONファイルを選択してください。
   フォロワー取得タブから直接DM送信に移動した場合は、自動的に入力されています。
3. 送信するDMの本文を入力してください。ユーザー名は自動的に挿入されます。
4. 送信するユーザー数を制限する場合は、送信数を入力してください。空白または0の場合はすべてのユーザーに送信します。
5. 「DM送信開始」ボタンをクリックしてください。
6. 送信済みのユーザーには再送信されないように管理されます。
"""
ttk.Label(dm_tab, text=dm_help_text, wraplength=550, justify="left").pack(anchor="w")

# クレジット
credit_label = ttk.Label(root, text="Instagram Follower & DM Tool v2.0", foreground="gray")
credit_label.pack(side="bottom", pady=5)

# アプリ起動
if __name__ == "__main__":
    root.mainloop()
