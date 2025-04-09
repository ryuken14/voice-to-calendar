import time
import io
import os
import platform
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json
import openai
import streamlit as st
from streamlit_mic_recorder import mic_recorder
import base64
import tempfile

st.title("🎙 音声から予定を全自動登録")

# NOVAの音声ガイド（スケジュールを音声入力してください～）
st.components.v1.html(
    """
    <audio autoplay>
        <source src="data:audio/wav;base64,{0}" type="audio/wav">
    </audio>
    """.format(base64.b64encode(open("guide.wav", "rb").read()).decode()),
    height=0,
)
# st.write("\n🔊 スケジュールを音声入力してください。入力が終わったら終了ボタンを押してください。")

# 録音スタート
audio = mic_recorder(start_prompt="🎤 録音スタート", stop_prompt="⏹️ 録音ストップ")

if audio:
    st.audio(audio["bytes"], format="audio/wav")
    # st.success("✅ 音声が録音されました！")

    # 一時ファイルに保存して確認
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio["bytes"])
        filepath = f.name
        st.info(f"🔉 保存先: {filepath}")

    # st.audio(uploaded_file)
    st.success("音声ファイルを受信しました。文字起こし中...")
  
    # 環境変数からAPIキーを取得
    openai.api_key = os.environ.get("OPENAI_API_KEY")
  
    # --- Whisper 文字起こし ---
    with open(filepath, "rb") as f:
        transcript = openai.Audio.transcribe("whisper-1", file=f)
        text = transcript["text"]
        st.write("📝 文字起こし結果:", text)

    # --- ChatGPTで予定抽出 ---
    system_prompt = """
    以下の自然言語で表された予定から「件名（title）」「開始日時（start）」「終了日時（end）」「場所（location）」を抽出し、次のJSON形式で出力してください。
    フォーマット:
    {
    "title": "登山旅行",
    "start": "2025-05-10T07:00:00",
    "end": "2025-05-10T15:00:00",
    "location": "霧島連山"
    }
    """

    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
    )

    try:
        parsed = json.loads(res.choices[0].message.content)
        st.json(parsed)

        # --- Google Calendarに登録 ---
        creds = Credentials.from_authorized_user_file("token.json")
        service = build("calendar", "v3", credentials=creds)

        event = {
            'summary': parsed["title"],
            'location': parsed.get("location", ""),
            'start': {'dateTime': parsed["start"], 'timeZone': 'Asia/Tokyo'},
            'end': {'dateTime': parsed["end"], 'timeZone': 'Asia/Tokyo'},
        }

        event = service.events().insert(calendarId='primary', body=event).execute()
        st.success(f"✅ Googleカレンダーに登録しました！: {event.get('htmlLink')}")

    except Exception as e:
        st.error(f"❌ エラーが発生しました: {e}")
        st.code(res.choices[0].message.content)

