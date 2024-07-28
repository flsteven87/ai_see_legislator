import openai
from dotenv import load_dotenv
import os
import json
import asyncio
import requests

class AssistantAPI:
    def __init__(self):
        load_dotenv()
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = openai.OpenAI()
        self.gazette_assistant_id = 'asst_Cu1eA3qYvbe1vTUMU34Ldlph'
        self.gazette_vector_stores_id = os.environ.get('gazette_vector_stores_id')

    def create_assistant(self, name, instructions, tools, model):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            tools=tools,
            model=model,
        )
        return assistant

    def create_vector_store(self, name):
        vector_store = self.client.beta.vector_stores.create(
            name=name,
        )
        return vector_store

    def upload_file(self, vector_store_id, file_streams):
        file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store_id, files=file_streams
        )
        return file_batch

    def list_files_in_vector_store(self, vector_store_id):
        files = self.client.beta.vector_stores.files.list(vector_store_id=vector_store_id)
        return files

    def link_vector_store(self, vector_store_id):
        assistant = self.client.beta.assistants.update(
            assistant_id=self.gazette_assistant_id,
            tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
        )

    def init_assistant(self):
        extract_basic_information ={
            "type": "function",
            "function": {
                "name": "extract_basic_information",
                "description": "Extracts the basic information from a legislative document，請以繁體中文提供相關的資訊。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_time": {
                            "type": "string",
                            "description": "The time when the meeting took place"
                        },
                        "meeting_location": {
                            "type": "string",
                            "description": "The location where the meeting took place"
                        },
                        "attendees": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of attendees"
                        },
                        "meeting_type": {
                            "type": "string",
                            "description": "The type of meeting"
                        },
                    },
                    "required": ["meeting_time", "meeting_location", "attendees", "meeting_type"]
                }
            }
        }

        assistant = self.create_assistant(
            name="台灣立法院公報解析",
            instructions="你是一位資深的立法院公報分析師，你的任務是分析臺灣立法院公報，並以繁體中文提供相關的資訊。",
            tools=[{"type": "file_search"}, extract_basic_information],
            model="gpt-4o-mini",
        )

        self.gazette_assistant_id = assistant.id

    def new_edition_gazette(self, edition_index):

        if edition_index < 10:
            edition_index = f'0{edition_index}'

        vector_store = self.create_vector_store(
            name=f"立法院公報第{edition_index}期",
        )

        file_paths = [os.path.join(f'./data/txt/第{edition_index}期/', file) for file in os.listdir(f'./data/txt/第{edition_index}期/') if file.endswith('.txt')]

        file_streams = [open(path, "rb") for path in file_paths]
        file_batch = self.upload_file(vector_store.id, file_streams)

        print(file_batch)

        self.link_vector_store(vector_store.id)

        # 列出文件並選擇第一個文件的 ID
        files = self.list_files_in_vector_store(vector_store.id)
        if files:
            first_file_id = files[0].id
            return first_file_id
        else:
            print("沒有文件被上傳")
            return None

    def create_thread(self, messages):
        thread = self.client.beta.threads.create(
            messages=messages, 
        )
        self.thread_id = thread.id
        return thread

    async def run_thread(self, thread_id, assistant_id, instructions):
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions=instructions,
        )

        run_complete = False
        while not run_complete:
            run = self.client.beta.threads.runs.poll(
                thread_id=thread_id,
                run_id=run.id,
            )
            print(f"Run status: {run.status}")

            if run.status == "requires_action":
                for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                    function_args = json.loads(tool_call.function.arguments)
                    meeting_time = function_args.get("meeting_time")
                    meeting_type = function_args.get("meeting_type")
                    meeting_location = function_args.get("meeting_location")
                    attendees = function_args.get("attendees")
                    print(f"Meeting time: {meeting_time}")
                    print(f"Meeting location: {meeting_location}")
                    print(f"Attendees: {attendees}")
                    print(f"Meeting type: {meeting_type}")

                    result = self.extract_basic_information(
                        meeting_time=meeting_time,
                        meeting_type=meeting_type,
                        meeting_location=meeting_location,
                        attendees=attendees
                    )

                    await self.client.beta.threads.runs.submitToolOutputs(
                        thread_id=thread_id,
                        run_id=run.id,
                        tool_outputs=[{'tool_call_id': tool_call.id, 'output': result}]
                    )
            run_complete = run.status in ["completed", "failed"]
        print("Run complete")

        headers = {
            'Authorization': f'Bearer {os.environ.get("OPENAI_API_KEY")}',
            'OpenAI-Beta': 'assistants=v2',
        }
        response = requests.get(
            f'https://api.openai.com/v1/threads/{thread_id}/messages',
            headers=headers
        )

        if response.status_code == 200:
            messages = response.json()["data"]
            for message in messages:
                message_info = self.extract_message_info(message)
                print(json.dumps(message_info, indent=2, ensure_ascii=False))
        else:
            print(f"Failed to retrieve messages: {response.status_code}, {response.text}")

    def extract_basic_information(self, meeting_time, meeting_type, meeting_location, attendees):
        return f"會議時間: {meeting_time}, 會議類型: {meeting_type}, 會議地點: {meeting_location}, 參加者: {', '.join(attendees)}"

    def extract_message_info(self, message):
        message_info = {
            "id": message["id"],
            "created_at": message["created_at"],
            "thread_id": message["thread_id"],
            "role": message["role"],
            "content": self.parse_content(message["content"]),
            "attachments": message["attachments"],
            "metadata": message["metadata"]
        }
        return message_info

    def parse_content(self, content):
        parsed_content = []
        for item in content:
            if item["type"] == "text":
                decoded_text = json.loads(f'"{item["text"]["value"]}"')
                parsed_content.append(decoded_text)
            elif item["type"] == "markdown":
                decoded_text = json.loads(f'"{item["markdown"]["value"]}"')
                parsed_content.append(decoded_text)
            # Handle other content types if necessary
        return "\n".join(parsed_content)

if __name__ == "__main__":

    edition = 67
    assistant_api = AssistantAPI()
    first_file_id = assistant_api.new_edition_gazette(edition)

    if first_file_id:
        messages = [
            {
                "role": "user",
                "content": f"你是一位熟悉台灣立法院運作的分析師，附檔第{edition}期的公報",
                "attachments": [
                    { "file_id": first_file_id, "tools": [{"type": "file_search"}, ] }
                ],
            }
        ]

        thread = assistant_api.create_thread(messages)

        print(thread.tool_resources.file_search)
        print(thread.id)
        thread_id = thread.id
        instructions = "請問這是什麼類型的會議？"

        asyncio.run(assistant_api.run_thread(thread_id=thread_id, assistant_id=assistant_api.gazette_assistant_id, instructions=instructions))