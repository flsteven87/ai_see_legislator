import openai
from dotenv import load_dotenv
import os
from openai import AssistantEventHandler
from typing_extensions import override
import json

class EventHandler(AssistantEventHandler):
    @override
    def on_event(self, event):
      # Retrieve events that are denoted with 'requires_action'
      # since these will have our tool_calls
      if event.event == 'thread.run.requires_action':
        run_id = event.data.id  # Retrieve the run ID from the event data
        self.handle_requires_action(event.data, run_id)
 
    def handle_requires_action(self, data, run_id):
      tool_outputs = []
        
      for tool in data.required_action.submit_tool_outputs.tool_calls:
        if tool.function.name == "get_current_temperature":
          tool_outputs.append({"tool_call_id": tool.id, "output": "57"})
        elif tool.function.name == "get_rain_probability":
          tool_outputs.append({"tool_call_id": tool.id, "output": "0.06"})
        
      # Submit all tool_outputs at the same time
      self.submit_tool_outputs(tool_outputs, run_id)
 
    def submit_tool_outputs(self, tool_outputs, run_id):
      # Use the submit_tool_outputs_stream helper
      with openai.OpenAI().beta.threads.runs.submit_tool_outputs_stream(
        thread_id=self.current_run.thread_id,
        run_id=self.current_run.id,
        tool_outputs=tool_outputs,
        event_handler=EventHandler(),
      ) as stream:
        for text in stream.text_deltas:
          print(text, end="", flush=True)
        print()

class AssistantAPI:
    def __init__(self):
        load_dotenv()
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        self.client = openai.OpenAI()
        self.gazette_assistant_id = os.environ.get('gazette_assistant_id')
        self.gazette_vector_stores_id = os.environ.get('gazette_vector_stores_id')
        self.file_id = 'file-rIxi4Fh5wM60MM8U8PaqryYL'

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
            model="gpt-4o",
        )

        self.gazette_assistant_id = assistant.id

    def new_edition_gazette(self, edition_index):

        if edition_index < 10:
            edition_index = f'0{edition_index}'

        # create vector store & upload files & link vector store
        vector_store = self.create_vector_store(
            name=f"立法院公報第{edition_index}期",
        )

        # file_paths 為./backend/media/第{edition_index}期/ 底下的所有 pdf 檔案路徑

        file_paths = [os.path.join(f'./media/第{edition_index}期/', file) for file in os.listdir(f'./media/第{edition_index}期/') if file.endswith('.pdf')]

        file_streams = [open(path, "rb") for path in file_paths]
        file_batch = self.upload_file(vector_store.id, file_streams)

        print(file_batch)

        self.link_vector_store(vector_store.id)

    def create_thread(self, messages):
        thread = self.client.beta.threads.create(
            messages=messages, 
            )
        self.thread_id = thread.id
        return thread

    def run_streaming_thread(self, thread_id, assistant_id, instructions):
        with self.client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions=instructions,
            event_handler=EventHandler(),
        ) as stream:
            stream.until_done()

    def run_thread(self, thread_id, assistant_id, instructions):
        
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id,
            instructions=instructions,
        )
        
        # Poll the run status
        while run.status != 'completed':
            run = self.client.beta.threads.runs.poll(
                thread_id=thread_id,
                run_id=run.id,
            )
            print(f"Run status: {run.status}")

            if run.required_action.submit_tool_outputs.tool_calls:
                for tool in run.required_action.submit_tool_outputs.tool_calls:
                    function_args = json.loads(tool.function.arguments)
                    meeting_time = function_args.get("meeting_time")
                    meeting_type = function_args.get("meeting_type")                  
                    meeting_location = function_args.get("meeting_location")
                    attendees = function_args.get("attendees")
                    print(f"Meeting time: {meeting_time}")
                    print(f"Meeting location: {meeting_location}")
                    print(f"Attendees: {attendees}")
                    print(f"Meeting type: {meeting_type}")
            

if __name__ == "__main__":

    assistant_api = AssistantAPI()
    # assistant_api.init_assistant()
    # assistant_api.new_edition_gazette(42)

    messages=[
        {
            "role": "user",
            "content": "你是一位熟悉台灣立法院運作的分析師，附檔是一份公報", # 整個thread的instructions
            # Attach the new file to the message.
            "attachments": [
                { "file_id": assistant_api.file_id, "tools": [{"type": "file_search"}, ] }
            ],
        }
    ]

    thread = assistant_api.create_thread(messages)
    
    # The thread now has a vector store with that file in its tool resources.
    print(thread.tool_resources.file_search)
    print(thread.id)

    thread_id = thread.id
    instructions = "請你將這份公報的基本資訊提取出來。"

    # assistant_api.run_streaming_thread(thread_id=thread_id, assistant_id=assistant_api.gazette_assistant_id, instructions=instructions)
    run = assistant_api.run_thread(thread_id=thread_id, assistant_id=assistant_api.gazette_assistant_id, instructions=instructions)
