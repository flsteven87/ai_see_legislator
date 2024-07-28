from openai import OpenAI
import os
from dotenv import load_dotenv

# 加載 .env 文件
load_dotenv()

client = OpenAI()

# 讀取 /data/txt/第01期/LCIDC01_1130101_00001.txt
meeting_transcript = open(os.path.join(os.path.dirname(__file__), 'data/txt/第01期/LCIDC01_1130101_00001.txt'), 'r').read()

print(meeting_transcript)
print(len(meeting_transcript))

response = client.chat.completions.create(
  model="gpt-4o-mini",
  messages=[
    {"role": "system", "content": "你是一位熟知中華民國台灣立法院運作模式的專家."},
    {"role": "user", "content": "請問這是立法院當中哪一種會議?" + "\n\n" + meeting_transcript},
  ]
)

message = response.choices[0].message.content

print(message)